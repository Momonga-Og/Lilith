import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import yt_dlp
import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)
tree = bot.tree

# Dictionary to hold guild queues
guild_queues = {}
# Dictionary to hold the leave timer
leave_timers = {}

# Function to download YouTube audio
def download_audio(url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
        'nocheckcertificate': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info).replace('.webm', '.mp3').replace('.m4a', '.mp3')
            duration = info.get('duration', 0)  # Duration in seconds
            title = info.get('title', 'Unknown title')
            thumbnail = info.get('thumbnail', '')
            return filename, duration, title, thumbnail
    except yt_dlp.utils.DownloadError as e:
        print(f"Download error: {e}")
        return None, 0, 'Unknown title', ''
    except Exception as e:
        print(f"An error occurred: {e}")
        return None, 0, 'Unknown title', ''

class MusicBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.channel_map = {}  # To keep track of which channel to send feedback

    async def join_channel(self, interaction: discord.Interaction):
        if interaction.user.voice is None:
            await interaction.response.send_message("You need to be in a voice channel to use this command.")
            return None
        channel = interaction.user.voice.channel
        if interaction.guild.voice_client is None:
            vc = await channel.connect()
        else:
            vc = interaction.guild.voice_client
            await vc.move_to(channel)
        return vc

    async def play_next(self, guild_id):
        if guild_id in guild_queues and guild_queues[guild_id]:
            vc = self.bot.get_guild(guild_id).voice_client
            if vc is None or not vc.is_connected():
                print(f"Voice client is not connected for guild {guild_id}")
                return

            url, duration, title, thumbnail = guild_queues[guild_id].pop(0)
            loop = asyncio.get_event_loop()

            try:
                filename, duration, title, thumbnail = await loop.run_in_executor(None, download_audio, url)
                if filename is None:
                    channel = self.bot.get_channel(self.channel_map[guild_id])
                    await channel.send(f"Failed to download audio from {url}")
                    return

                def after_playing(error):
                    if error:
                        print(f"Error occurred: {error}")
                    fut = asyncio.run_coroutine_threadsafe(self.play_next(guild_id), self.bot.loop)
                    try:
                        fut.result()
                    except Exception as e:
                        print(f"Error in play_next: {e}")

                embed = discord.Embed(title="Now Playing", description=title, color=discord.Color.blue())
                embed.set_thumbnail(url=thumbnail)
                channel = self.bot.get_channel(self.channel_map[guild_id])
                await channel.send(embed=embed)

                vc.play(discord.FFmpegPCMAudio(executable="ffmpeg", source=filename), after=after_playing)
            except Exception as e:
                print(f"Error in play_next: {e}")
        else:
            # No more songs in the queue, set a timer to leave the voice channel
            if guild_id in leave_timers:
                leave_timers[guild_id].cancel()
            leave_timers[guild_id] = self.bot.loop.call_later(60, lambda: asyncio.create_task(self.leave_voice_channel(guild_id)))

    async def leave_voice_channel(self, guild_id):
        vc = self.bot.get_guild(guild_id).voice_client
        if vc is not None:
            await vc.disconnect()
            if guild_id in guild_queues:
                guild_queues.pop(guild_id)
            if guild_id in leave_timers:
                leave_timers.pop(guild_id)
            print(f"Left the voice channel in guild {guild_id} due to inactivity.")

    @app_commands.command(name="play", description="Play a song")
    @app_commands.describe(url="The URL of the song to play")
    async def play(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer()  # Defer the response to avoid the interaction timeout

        vc = await self.join_channel(interaction)
        if vc is None:
            return
        
        guild_id = interaction.guild.id
        guild_queues[guild_id] = []  # Clear the queue before adding the new song

        guild_queues[guild_id].append((url, 0, 'Unknown title', ''))  # Placeholder for duration, title, thumbnail
        
        # Map the interaction channel to the guild_id
        self.channel_map[guild_id] = interaction.channel.id
        
        if not vc.is_playing():
            await self.play_next(guild_id)
        
        await interaction.followup.send("Added song to the queue and will play it soon.")

    @app_commands.command(name="loop", description="Loop a song 10 times")
    @app_commands.describe(url="The URL of the song to loop")
    async def loop(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer()  # Defer the response to avoid the interaction timeout

        vc = await self.join_channel(interaction)
        if vc is None:
            return

        guild_id = interaction.guild.id
        guild_queues[guild_id] = []  # Clear the queue before adding the looped songs

        # Add the song to the queue 10 times
        for _ in range(10):
            guild_queues[guild_id].append((url, 0, 'Unknown title', ''))  # Placeholder for duration, title, thumbnail
        
        # Map the interaction channel to the guild_id
        self.channel_map[guild_id] = interaction.channel.id
        
        if not vc.is_playing():
            await self.play_next(guild_id)
        
        await interaction.followup.send("Added song to the queue to loop 10 times.")

    @app_commands.command(name="pause", description="Pause the current song")
    async def pause(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc is None or not vc.is_playing():
            await interaction.response.send_message("There is no song currently playing.")
            return
        vc.pause()
        await interaction.response.send_message("Paused the song.")

    @app_commands.command(name="resume", description="Resume the current song")
    async def resume(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc is None or not vc.is_paused():
            await interaction.response.send_message("There is no song currently paused.")
            return
        vc.resume()
        await interaction.response.send_message("Resumed the song.")

    @app_commands.command(name="skip", description="Skip the current song")
    async def skip(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc is None or not vc.is_playing():
            await interaction.response.send_message("There is no song currently playing.")
            return
        vc.stop()
        await interaction.response.send_message("Skipped the current song.")
        await self.play_next(interaction.guild.id)  # Play the next song in the queue

    @app_commands.command(name="queue", description="Show the current queue")
    async def queue(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        if guild_id not in guild_queues or not guild_queues[guild_id]:
            await interaction.response.send_message("The queue is empty.")
            return
        queue_list = "\n".join([f"{title} - {duration//60}:{duration%60:02d}" for url, duration, title, thumbnail in guild_queues[guild_id]])
        await interaction.response.send_message(f"Current queue:\n{queue_list}")

    @app_commands.command(name="clear", description="Clear the queue")
    async def clear(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        if guild_id in guild_queues:
            guild_queues[guild_id].clear()
        await interaction.response.send_message("Cleared the queue.")

    @app_commands.command(name="leave", description="Leave the voice channel")
    async def leave(self, interaction: discord.Interaction):
        if interaction.guild.voice_client is not None:
            await interaction.guild.voice_client.disconnect()
            guild_id = interaction.guild.id
            if guild_id in guild_queues:
                guild_queues.pop(guild_id)
            await interaction.response.send_message("Left the voice channel.")
        else:
            await interaction.response.send_message("I am not in a voice channel.")

@bot.event
async def on_ready():
    if not bot.cogs:
        await bot.add_cog(MusicBot(bot))
    await tree.sync()
    print(f'Logged in as {bot.user}!')

# Run the bot with the token from the environment variable
bot.run(os.getenv('DISCORD_BOT_TOKEN'))
