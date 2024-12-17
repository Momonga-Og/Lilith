import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import requests
import logging
import os

# Set up logging to log every step the bot does
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix="/", intents=intents)

# Global Variables for Music
music_queue = []
current_song = None
voice_client = None

# New YouTube API configuration
YOUTUBE_API_URL = "https://youtube-mp36.p.rapidapi.com/dl"
HEADERS = {
    "x-rapidapi-key": "5e6976078bmsheb89f5f8d17f7d4p1b5895jsnb31e587ad8cc",
    "x-rapidapi-host": "youtube-mp36.p.rapidapi.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# --- Function to Stream Music from URL ---
async def stream_music_from_url(url, ctx):
    global voice_client

    if not voice_client:
        await ctx.author.voice.channel.connect()

    try:
        # Stream the audio directly from the URL using FFmpegPCMAudio
        voice_client.play(
            discord.FFmpegPCMAudio(url, **{'before_options': '-re'}),
            after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)
        )
        await ctx.send(f"🎶 Now playing: **{url}**")
    except Exception as e:
        logging.error(f"Error occurred while streaming audio: {e}")
        await ctx.send("❌ There was an error while streaming the audio.")

# --- Function to Play Next Song ---
async def play_next(ctx):
    global current_song, voice_client

    if music_queue:
        next_song = music_queue.pop(0)
        current_song = next_song

        file_url = next_song["file_url"]
        title = next_song["title"]

        # Stream the song from the URL directly
        await stream_music_from_url(file_url, ctx)
    else:
        current_song = None
        logging.info("Queue is empty.")
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
        querystring = {"id": url.split("v=")[-1]}  # Extract the video ID from the URL
        response = requests.get(YOUTUBE_API_URL, headers=HEADERS, params=querystring)

        # Print the raw response for debugging purposes
        logging.info(f"API Response: {response.json()}")  # Debugging line

        # Check if the API returned a valid audio URL
        data = response.json()
        if "link" not in data:
            logging.error(f"Could not fetch audio for the URL: {url}")
            await interaction.followup.send("❌ Could not fetch audio for this link.")
            return

        # Get the actual audio download URL from the response
        audio_url = data["link"]

        logging.info(f"Fetching audio from: {audio_url}")

        # Add to queue and stream directly
        music_queue.append({"file_url": audio_url, "title": data.get("title", "Unknown Title")})
        await interaction.followup.send(f"✅ Added **{data['title']}** to the queue.")

        if not voice_client.is_playing():
            await play_next(interaction.channel)

    except Exception as e:
        logging.error(f"Error occurred: {e}")
        await interaction.followup.send(f"❌ Error: {e}")

# --- Command to Stop Music ---
@bot.tree.command(name="stop", description="Stop the music and clear the queue")
async def stop(interaction: discord.Interaction):
    global music_queue

    if voice_client.is_playing():
        voice_client.stop()
    music_queue = []
    logging.info("Stopped the music and cleared the queue.")
    await interaction.response.send_message("⏹️ Stopped the music and cleared the queue.")

# --- Command to Skip Song ---
@bot.tree.command(name="skip", description="Skip the current song")
async def skip(interaction: discord.Interaction):
    if voice_client.is_playing():
        voice_client.stop()
        logging.info("Skipped the current song.")
        await interaction.response.send_message("⏭️ Skipped the current song.")
    else:
        logging.warning("No music is playing.")
        await interaction.response.send_message("❌ No music is playing.")

# --- Command to Pause Music ---
@bot.tree.command(name="pause", description="Pause the current song")
async def pause(interaction: discord.Interaction):
    if voice_client.is_playing():
        voice_client.pause()
        logging.info("Paused the current song.")
        await interaction.response.send_message("⏸️ Paused the music.")
    else:
        logging.warning("No music is playing.")
        await interaction.response.send_message("❌ No music is playing.")

# --- Command to Resume Music ---
@bot.tree.command(name="resume", description="Resume the paused song")
async def resume(interaction: discord.Interaction):
    if voice_client.is_paused():
        voice_client.resume()
        logging.info("Resumed the music.")
        await interaction.response.send_message("▶️ Resumed the music.")
    else:
        logging.warning("No music is paused.")
        await interaction.response.send_message("❌ No music is paused.")

# --- Event: On Ready ---
@bot.event
async def on_ready():
    await bot.tree.sync()
    logging.info(f"Logged in as {bot.user}")

# Run the bot
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
bot.run(DISCORD_BOT_TOKEN)
