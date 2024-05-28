import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import yt_dlp
import os
from dotenv import load_dotenv
import json
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s:%(name)s:%(message)s')
file_handler = logging.FileHandler('bot.log')
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s:%(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


load_dotenv()  # Load environment variables from .env file

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True  # Enable voice state intent

bot = commands.Bot(command_prefix='!', intents=intents)
tree = bot.tree

# Dictionary to hold guild queues
guild_queues = {}
# Dictionary to hold the leave timer
leave_timers = {}

# Path to JSON files
USER_PLAYLISTS_FILE = 'user_playlists.json'
PLAYLISTS_FILE = 'playlists.json'

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Function to load data from a JSON file
def load_json(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            try:
                return json.load(file)
            except json.JSONDecodeError:
                # Handle empty or malformed file by returning an empty dictionary
                return {}
    return {}

# Function to save data to a JSON file
def save_json(data, file_path):
    with open(file_path, 'w') as file:
        json.dump(data, file, indent=4)

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

    async def register_song(self, user_id, user_name, song_title, song_url):
        logger.info(f"Registering song: {song_title} by {user_name} (ID: {user_id})")
        user_playlists = load_json(USER_PLAYLISTS_FILE)
        playlists = load_json(PLAYLISTS_FILE)

        # Register user playlist
        if user_id not in user_playlists:
            user_playlists[user_id] = {'user_name': user_name, 'songs': []}
        user_playlists[user_id]['songs'].append({'title': song_title, 'url': song_url})

        # Register in global playlists
        if song_title not in playlists:
            playlists[song_title] = []
        playlists[song_title].append({'user_id': user_id, 'user_name': user_name, 'url': song_url})

        # Save the updated data
        save_json(user_playlists, USER_PLAYLISTS_FILE)
        save_json(playlists, PLAYLISTS_FILE)
        logger.info(f"Song registered successfully: {song_title} by {user_name} (ID: {user_id})")

    @app_commands.command(name="play", description="Play a song")
    @app_commands.describe(url="The URL of the song to play")
    async def play(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer()

        vc = await self.join_channel(interaction)
        if vc is None:
            return
        
        guild_id = interaction.guild.id
        guild_queues[guild_id] = []

        guild_queues[guild_id].append((url, 0, 'Unknown title', ''))

        self.channel_map[guild_id] = interaction.channel.id
        
        if not vc.is_playing():
            await self.play_next(guild_id)
        
        await interaction.followup.send("Added song to the queue and will play it soon.")

        # Register song information
        user_id = interaction.user.id
        user_name = interaction.user.name
        song_title = 'Unknown title'  # Placeholder until the title is fetched during download
        logger.info(f"Calling register_song for user: {user_name} (ID: {user_id}) with URL: {url}")
        await self.register_song(user_id, user_name, song_title, url)

    @app_commands.command(name="loop", description="Loop a song 10 times")
    @app_commands.describe(url="The URL of the song to loop")
    async def loop(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer()

        vc = await self.join_channel(interaction)
        if vc is None:
            return

        guild_id = interaction.guild.id
        guild_queues[guild_id] = []

        for _ in range(10):
            guild_queues[guild_id].append((url, 0, 'Unknown title', ''))

        self.channel_map[guild_id] = interaction.channel.id

        if not vc.is_playing():
            await self.play_next(guild_id)

        await interaction.followup.send("Added song to the queue to loop 10 times.")

        # Register song information
        user_id = interaction.user.id
        user_name = interaction.user.name
        song_title = 'Unknown title'  # Placeholder until the title is fetched during download
        logger.info(f"Calling register_song for user: {user_name} (ID: {user_id}) with URL: {url}")
        await self.register_song(user_id, user_name, song_title, url)

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

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # Check if the bot was kicked from the voice channel
        if member == self.bot.user and before.channel is not None and after.channel is None:
            guild_id = before.channel.guild.id
            if guild_id in self.channel_map:
                channel = self.bot.get_channel(self.channel_map[guild_id])
                # Find out who caused the bot to be kicked
                for other_member in before.channel.members:
                    if other_member.guild_permissions.move_members:
                        # We assume the user with the permission to move members is the one who kicked the bot
                        await channel.send(f"I was kicked from the voice channel by {other_member.display_name}.")
                        break

@bot.event
async def on_ready():
    if not bot.cogs:
        await bot.add_cog(MusicBot(bot))
    await tree.sync()
    print(f'Logged in as {bot.user}!')

# Run the bot with the token from the environment variable
bot.run(os.getenv('DISCORD_BOT_TOKEN'))
