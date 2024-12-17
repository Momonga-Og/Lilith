import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import requests
import os
import uuid
import subprocess
import pygame

# Use a dummy audio driver for headless environments
os.environ["SDL_AUDIODRIVER"] = "dummy"

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix="/", intents=intents)

# Initialize Pygame Mixer
pygame.mixer.init()

# Global Variables for Music
music_queue = []
current_song = None
voice_client = None
TEMP_FOLDER = "./temp_music/"

# Ensure temporary folder exists
os.makedirs(TEMP_FOLDER, exist_ok=True)

# New YouTube API configuration
YOUTUBE_API_URL = "https://youtube-mp310.p.rapidapi.com/download/mp3"
HEADERS = {
    "x-rapidapi-key": "5e6976078bmsheb89f5f8d17f7d4p1b5895jsnb31e587ad8cc",
    "x-rapidapi-host": "youtube-mp310.p.rapidapi.com"
}

# --- Function to Re-encode MP3 using FFmpeg ---
def reencode_mp3(input_path, output_path):
    subprocess.run(["ffmpeg", "-i", input_path, "-codec:a", "libmp3lame", "-qscale:a", "2", output_path])

# --- Function to Check Downloaded File Size ---
def check_file_size(file_path):
    return os.path.getsize(file_path)

# --- Function to Play Next Song ---
async def play_next(ctx):
    global current_song, voice_client

    if music_queue:
        next_song = music_queue.pop(0)
        current_song = next_song

        file_path = next_song["file_path"]
        title = next_song["title"]

        # Check if the file size is reasonable (for example, it should be > 1MB)
        if check_file_size(file_path) < 1024 * 1024:
            await ctx.send(f"❌ The file is too small to be a valid audio file: **{title}**")
            os.remove(file_path)
            return

        # Re-encode the file to ensure compatibility
        reencoded_file = file_path.replace(".mp3", "_reencoded.mp3")
        reencode_mp3(file_path, reencoded_file)

        # Play using pygame
        pygame.mixer.music.load(reencoded_file)
        pygame.mixer.music.play()

        await ctx.send(f"🎶 Now playing: **{title}**")

        # Wait for the music to finish
        while pygame.mixer.music.get_busy():
            await asyncio.sleep(1)

        # Cleanup and play next
        os.remove(reencoded_file)  # Remove the re-encoded file
        os.remove(file_path)  # Remove the original file
        await play_next(ctx)
    else:
        current_song = None
        await ctx.send("🎵 Queue is empty. Add more songs!")

# --- Command to Play Music ---
@bot.tree.command(name="play", description="Play a song from a YouTube link")
@app_commands.describe(url="YouTube video URL")
async def play(interaction: discord.Interaction, url: str):
    global voice_client

    await interaction.response.defer()

    # Check if user is in a voice channel
    if interaction.user.voice is None:
        await interaction.followup.send("❌ You must be in a voice channel to play music.")
        return

    channel = interaction.user.voice.channel
    if not interaction.guild.voice_client:
        voice_client = await channel.connect()
    else:
        voice_client = interaction.guild.voice_client

    try:
        # Send the request to the new API with the provided URL
        querystring = {"url": url}
        response = requests.get(YOUTUBE_API_URL, headers=HEADERS, params=querystring)

        # Print the raw response for debugging purposes
        print(f"API Response: {response.json()}")  # Debugging line

        # Check if the API returned a valid audio URL
        data = response.json()
        if "link" not in data:
            await interaction.followup.send("❌ Could not fetch audio for this link.")
            return

        audio_url = data["link"]
        title = data["title"]
        file_path = os.path.join(TEMP_FOLDER, f"{uuid.uuid4()}.mp3")

        # Download the audio file
        with requests.get(audio_url, stream=True) as r:
            with open(file_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

        # Ensure the file size is reasonable before proceeding
        if check_file_size(file_path) < 1024 * 1024:
            await interaction.followup.send(f"❌ The file for **{title}** is too small to be a valid audio file.")
            os.remove(file_path)
            return

        # Add to queue and play
        music_queue.append({"file_path": file_path, "title": title})
        await interaction.followup.send(f"✅ Added **{title}** to the queue.")

        if not pygame.mixer.music.get_busy():
            await play_next(interaction.channel)

    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}")

# --- Command to Stop Music ---
@bot.tree.command(name="stop", description="Stop the music and clear the queue")
async def stop(interaction: discord.Interaction):
    global music_queue

    pygame.mixer.music.stop()
    music_queue = []
    await interaction.response.send_message("⏹️ Stopped the music and cleared the queue.")

# --- Command to Skip Song ---
@bot.tree.command(name="skip", description="Skip the current song")
async def skip(interaction: discord.Interaction):
    if pygame.mixer.music.get_busy():
        pygame.mixer.music.stop()
        await interaction.response.send_message("⏭️ Skipped the current song.")
    else:
        await interaction.response.send_message("❌ No music is playing.")

# --- Command to Pause Music ---
@bot.tree.command(name="pause", description="Pause the current song")
async def pause(interaction: discord.Interaction):
    if pygame.mixer.music.get_busy():
        pygame.mixer.music.pause()
        await interaction.response.send_message("⏸️ Paused the music.")
    else:
        await interaction.response.send_message("❌ No music is playing.")

# --- Command to Resume Music ---
@bot.tree.command(name="resume", description="Resume the paused song")
async def resume(interaction: discord.Interaction):
    if pygame.mixer.music.get_pos() != -1:
        pygame.mixer.music.unpause()
        await interaction.response.send_message("▶️ Resumed the music.")
    else:
        await interaction.response.send_message("❌ No music is paused.")

# --- Event: On Ready ---
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Logged in as {bot.user}")

# Run the bot
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
bot.run(DISCORD_BOT_TOKEN)
