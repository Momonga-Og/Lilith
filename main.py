import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import yt_dlp
import os

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)
tree = bot.tree

# Dictionary to hold user playlists
user_playlists = {}

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
            return filename
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

class MusicBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_clients = {}

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

    @app_commands.command(name="play", description="Play a song")
    @app_commands.describe(url="The URL of the song to play")
    async def play(self, interaction: discord.Interaction, url: str):
        vc = await self.join_channel(interaction)
        if vc is None:
            return
        filename = download_audio(url)
        if filename is None:
            await interaction.response.send_message(f"Failed to download audio from {url}")
            return
        vc.play(discord.FFmpegPCMAudio(executable="ffmpeg", source=filename))
        user_id = interaction.user.id
        if user_id not in user_playlists:
            user_playlists[user_id] = []
        user_playlists[user_id].append(url)
        await interaction.response.send_message("Playing song and added to your playlist.")

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

    @app_commands.command(name="leave", description="Leave the voice channel")
    async def leave(self, interaction: discord.Interaction):
        if interaction.guild.voice_client is not None:
            await interaction.guild.voice_client.disconnect()
            await interaction.response.send_message("Left the voice channel.")
        else:
            await interaction.response.send_message("I am not in a voice channel.")

    async def get_video_info(self, url):
        ydl_opts = {
            'format': 'best',
            'quiet': True,
            'extract_flat': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            return info_dict

@bot.event
async def on_ready():
    if not bot.cogs:
        await bot.add_cog(MusicBot(bot))
    await tree.sync()
    print(f'Logged in as {bot.user}!')

# Token should be stored securely
bot.run('YOUR_DISCORD_BOT_TOKEN')
