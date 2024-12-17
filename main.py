import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import requests
import os

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="/", intents=intents)

# Global Variables for Music Queue and Player
music_queue = []
current_song = None
voice_client = None

# Invidious API Instance
INVIDIOUS_INSTANCE = "https://vid.puffyan.us"

# FFmpeg Options
FFMPEG_OPTIONS = {
    'options': '-vn'
}


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
@bot.tree.command(name="play", description="Play a song from a URL or search by name")
@app_commands.describe(search="YouTube URL or search query")
async def play(interaction: discord.Interaction, search: str):
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
        # Check if search is a URL or search query
        if search.startswith("http"):
            video_id = search.split("v=")[-1]  # Extract video ID from URL
        else:
            # Search YouTube via Invidious
            search_url = f"{INVIDIOUS_INSTANCE}/api/v1/search?q={search}&type=video"
            response = requests.get(search_url)
            results = response.json()

            if not results:
                await interaction.followup.send("❌ No results found for your query.")
                return

            video_id = results[0]["videoId"]  # Use the first video result
            title = results[0]["title"]

        # Get video stream URL using Invidious API
        video_url = f"{INVIDIOUS_INSTANCE}/latest_version?id={video_id}&itag=251"  # itag=251 for audio
        music_queue.append({'url': video_url, 'title': title or f"Video {video_id}"})

        await interaction.followup.send(f"✅ Added **{title}** to the queue.")

        if not voice_client.is_playing():
            await play_next(interaction.channel)

    except Exception as e:
        await interaction.followup.send(f"❌ Error retrieving video: {e}")


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


# --- Command to View Queue ---
@bot.tree.command(name="queue", description="View the music queue")
async def queue(interaction: discord.Interaction):
    if music_queue:
        queue_list = "\n".join([f"{i + 1}. {song['title']}" for i, song in enumerate(music_queue)])
        await interaction.response.send_message(f"🎶 **Music Queue:**\n{queue_list}")
    else:
        await interaction.response.send_message("🎵 The music queue is empty.")


# --- Event: On Ready ---
@bot.event
async def on_ready():
    await bot.tree.sync()  # Sync slash commands
    print(f"✅ Logged in as {bot.user}")


# Run the bot
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
bot.run(DISCORD_BOT_TOKEN)
