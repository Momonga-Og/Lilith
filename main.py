import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
import os
import requests

# ========= Configuration =========
TOKEN = os.getenv('DISCORD_BOT_TOKEN')  # Fetch the bot token from the environment variable
INVIDIOUS_INSTANCE = "https://invidious.snopyta.org"
DOWNLOAD_FOLDER = "downloads"

# ========= Global Variables =======
queue = []
current_track_index = -1  # Tracks the index of the current song in the queue
voice_client = None

# ========= Bot Setup ============
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = app_commands.CommandTree(bot)


def fetch_audio_url_from_invidious(search_query):
    """
    Fetch the audio URL using Invidious by searching with a query.
    """
    try:
        print(f"[INFO] Searching for '{search_query}' on Invidious...")
        response = requests.get(f"{INVIDIOUS_INSTANCE}/api/v1/search", params={"q": search_query, "type": "video"})
        response.raise_for_status()
        videos = response.json()
        if videos:
            video_id = videos[0]["videoId"]
            print(f"[INFO] Found video: {videos[0]['title']} (ID: {video_id})")
            return f"https://www.youtube.com/watch?v={video_id}"
        else:
            return None
    except Exception as e:
        print(f"[ERROR] Failed to search on Invidious: {e}")
        return None


async def play_next_song(ctx):
    """
    Play the next song in the queue.
    """
    global current_track_index, voice_client
    current_track_index += 1

    if current_track_index >= len(queue):
        await ctx.send("Queue finished. No more songs to play.")
        current_track_index = -1  # Reset the queue
        return

    song_url = queue[current_track_index]
    await play_song(ctx, song_url)


async def play_song(ctx, url):
    """
    Download and play a song in the voice channel.
    """
    global voice_client
    if not voice_client or not voice_client.is_connected():
        if ctx.author.voice:
            voice_client = await ctx.author.voice.channel.connect()
        else:
            await ctx.send("You need to be in a voice channel to play music!")
            return

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(DOWNLOAD_FOLDER, 'song.%(ext)s'),
        'quiet': True,
        'noplaylist': True
    }

    try:
        await ctx.send(f"Playing: {url}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            audio_url = info['url']

        voice_client.play(discord.FFmpegPCMAudio(audio_url), after=lambda e: asyncio.run_coroutine_threadsafe(play_next_song(ctx), bot.loop))
    except Exception as e:
        await ctx.send(f"Error playing song: {e}")
        print(e)


# ========= Slash Commands =========

@tree.command(name="play", description="Play a song by URL or name.")
async def play(interaction: discord.Interaction, query: str):
    await interaction.response.send_message("Adding song to queue...", ephemeral=True)

    if "youtube.com" in query or "youtu.be" in query:
        url = query
    else:
        url = fetch_audio_url_from_invidious(query)

    if not url:
        await interaction.followup.send("Could not find the song.")
        return

    queue.append(url)
    await interaction.followup.send(f"Added to queue: {url}")

    # If no song is currently playing, play the song
    if current_track_index == -1:
        ctx = await bot.get_context(interaction)
        await play_next_song(ctx)


@tree.command(name="skip", description="Skip to the next song.")
async def skip(interaction: discord.Interaction):
    global voice_client
    if voice_client and voice_client.is_playing():
        voice_client.stop()
        await interaction.response.send_message("Skipped to the next song!")
    else:
        await interaction.response.send_message("No song is playing!")


@tree.command(name="stop", description="Stop the music and clear the queue.")
async def stop(interaction: discord.Interaction):
    global voice_client, queue, current_track_index
    if voice_client:
        voice_client.stop()
        await voice_client.disconnect()
    queue.clear()
    current_track_index = -1
    await interaction.response.send_message("Stopped music and cleared the queue.")


@tree.command(name="pause", description="Pause the current song.")
async def pause(interaction: discord.Interaction):
    global voice_client
    if voice_client and voice_client.is_playing():
        voice_client.pause()
        await interaction.response.send_message("Paused the music.")
    else:
        await interaction.response.send_message("No song is playing!")


@tree.command(name="resume", description="Resume paused music.")
async def resume(interaction: discord.Interaction):
    global voice_client
    if voice_client and voice_client.is_paused():
        voice_client.resume()
        await interaction.response.send_message("Resumed the music.")
    else:
        await interaction.response.send_message("No song is paused!")


@tree.command(name="queue", description="Show the current queue.")
async def show_queue(interaction: discord.Interaction):
    if queue:
        songs = "\n".join([f"{i+1}. {url}" for i, url in enumerate(queue)])
        await interaction.response.send_message(f"Current Queue:\n{songs}")
    else:
        await interaction.response.send_message("The queue is empty.")


# ========= Bot Events =========

@bot.event
async def on_ready():
    await tree.sync()
    print(f"Logged in as {bot.user.name}")


# ========= Run Bot ============
if __name__ == "__main__":
    if not os.path.exists(DOWNLOAD_FOLDER):
        os.makedirs(DOWNLOAD_FOLDER)
    bot.run(TOKEN)
