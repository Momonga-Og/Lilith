import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import requests
import os
import uuid

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix="/", intents=intents)

# Global Variables for Music
music_queue = []
current_song = None
voice_client = None
TEMP_FOLDER = "./temp_music/"

# Ensure temporary folder exists
os.makedirs(TEMP_FOLDER, exist_ok=True)

# YouTube API configuration
YOUTUBE_API_URL = "https://youtube-mp36.p.rapidapi.com/dl"
HEADERS = {
    "x-rapidapi-key": "5e6976078bmsheb89f5f8d17f7d4p1b5895jsnb31e587ad8cc",
    "x-rapidapi-host": "youtube-mp36.p.rapidapi.com"
}

# --- Function to Play Next Song ---
async def play_next(ctx):
    global current_song, voice_client

    if music_queue:
        next_song = music_queue.pop(0)
        current_song = next_song

        file_path = next_song["file_path"]
        title = next_song["title"]

        # Play using FFmpegPCMAudio
        source = discord.FFmpegPCMAudio(file_path)
        voice_client.play(source)

        await ctx.send(f"🎶 Now playing: **{title}**")

        # Wait for the music to finish
        while voice_client.is_playing():
            await asyncio.sleep(1)

        # Cleanup and play next
        os.remove(file_path)
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
        # Fetch audio download URL from YouTube API
        video_id = url.split("v=")[-1]
        querystring = {"id": video_id}
        response = requests.get(YOUTUBE_API_URL, headers=HEADERS, params=querystring)
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

        # Add to queue and play
        music_queue.append({"file_path": file_path, "title": title})
        await interaction.followup.send(f"✅ Added **{title}** to the queue.")

        if not voice_client.is_playing():
            await play_next(interaction.channel)

    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}")

# --- Command to Stop Music ---
@bot.tree.command(name="stop", description="Stop the music and clear the queue")
async def stop(interaction: discord.Interaction):
    global music_queue

    voice_client.stop()
    music_queue = []
    await interaction.response.send_message("⏹️ Stopped the music and cleared the queue.")

# --- Command to Skip Song ---
@bot.tree.command(name="skip", description="Skip the current song")
async def skip(interaction: discord.Interaction):
    if voice_client and voice_client.is_playing():
        voice_client.stop()
        await interaction.response.send_message("⏭️ Skipped the current song.")
    else:
        await interaction.response.send_message("❌ No music is playing.")

# --- Command to Pause Music ---
@bot.tree.command(name="pause", description="Pause the current song")
async def pause(interaction: discord.Interaction):
    if voice_client and voice_client.is_playing():
        voice_client.pause()
        await interaction.response.send_message("⏸️ Paused the music.")
    else:
        await interaction.response.send_message("❌ No music is playing.")

# --- Command to Resume Music ---
@bot.tree.command(name="resume", description="Resume the paused song")
async def resume(interaction: discord.Interaction):
    if voice_client and voice_client.is_paused():
        voice_client.resume()
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
