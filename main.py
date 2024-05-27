import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import yt_dlp
import os
import concurrent.futures
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)
tree = bot.tree

# Dictionary to hold guild queues
guild_queues = {}

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
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info).replace('.webm', '.mp3').replace('.m4a', '.mp3')
            duration = info.get('duration', 0)  # Duration in seconds
            return filename, duration
    except Exception as e:
        print(f"An error occurred: {e}")
        return None, 0

class MusicBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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

            url, duration = guild_queues[guild_id].pop(0)
            loop = asyncio.get_event_loop()

            try:
                filename, duration = await loop.run_in_executor(None, download_audio, url)
                if filename is None:
                    await self.bot.get_guild(guild_id).text_channels[0].send(f"Failed to download audio from {url}")
                    return

                def after_playing(error):
                    if error:
                        print(f"Error occurred: {error}")
                    fut = asyncio.run_coroutine_threadsafe(self.play_next(guild_id), self.bot.loop)
                    try:
                        fut.result()
                    except Exception as e:
                        print(f"Error in play_next: {e}")

                vc.play(discord.FFmpegPCMAudio(executable="ffmpeg", source=filename), after=after_playing)
            except Exception as e:
                print(f"Error in play_next: {e}")

    @app_commands.command(name="play", description="Play a song")
    @app_commands.describe(url="The URL of the song to play")
    async def play(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer()  # Defer the response to avoid the interaction timeout
        vc = await self.join_channel(interaction)
        if vc is None:
            return
        
        guild_id = interaction.guild.id
        if guild_id not in guild_queues:
            guild_queues[guild_id] = []
        
        guild_queues[guild_id].append((url, 0))  # Placeholder for duration
        
        if not vc.is_playing():
            await self.play_next(guild_id)
        
        await interaction.followup.send("Added song to the queue and will play it soon.")

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

    @app_commands.command(name="queue", description="Show the current queue")
    async def queue(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        if guild_id not in guild_queues or not guild_queues[guild_id]:
            await interaction.response.send_message("The queue is empty.")
            return
        queue_list = "\n".join([f"{url} - {duration//60}:{duration%60:02d}" for url, duration in guild_queues[guild_id]])
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
