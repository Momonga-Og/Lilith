import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os
import yt_dlp

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix="/", intents=intents)

# Global Variables for Music Queue and Player
music_queue = []
current_song = None
voice_client = None

# FFmpeg Options
FFMPEG_OPTIONS = {'options': '-vn'}

# --- Function to Play Next Song ---
async def play_next(ctx):
    global current_song, voice_client

    if music_queue:
        next_song = music_queue.pop(0)
        current_song = next_song

        url = next_song['url']
        voice_client.play(
            discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS),
            after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)
        )
        await ctx.send(f"🎶 Now playing: **{next_song['title']}**")
    else:
        current_song = None
        await ctx.send("🎵 Queue is empty. Add more songs!")

# --- Command to Play Music ---
@bot.tree.command(name="play", description="Play a song from a URL")
@app_commands.describe(url="Song URL from YouTube or SoundCloud")
async def play(interaction: discord.Interaction, url: str):
    global voice_client

    await interaction.response.defer()  # Defer response to prevent timeout

    # Connect to voice channel
    if interaction.user.voice is None:
        await interaction.followup.send("❌ You must be in a voice channel to play music.")
        return

    channel = interaction.user.voice.channel
    if not interaction.guild.voice_client:
        voice_client = await channel.connect()
    else:
        voice_client = interaction.guild.voice_client

    try:
        # Extract audio info using yt_dlp
        with yt_dlp.YoutubeDL({'format': 'bestaudio'}) as ydl:
            info = ydl.extract_info(url, download=False)
            audio_url = info['url']
            title = info.get('title', 'Unknown Title')

        # Add track to queue
        music_queue.append({'url': audio_url, 'title': title})
        await interaction.followup.send(f"✅ Added **{title}** to the queue.")

        # Play if nothing is playing
        if not voice_client.is_playing():
            await play_next(interaction.channel)

    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}")

# --- Command to Stop Music ---
@bot.tree.command(name="stop", description="Stop the music and clear the queue")
async def stop(interaction: discord.Interaction):
    global music_queue

    if voice_client:
        voice_client.stop()
        music_queue = []
        await interaction.response.send_message("⏹️ Stopped the music and cleared the queue.")
    else:
        await interaction.response.send_message("❌ No music is playing.")

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
