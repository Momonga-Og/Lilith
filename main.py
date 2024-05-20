import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
import asyncio
import json
import yt_dlp
import os

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)
tree = bot.tree

# Dictionary to hold user playlists
user_playlists = {}

# Log file to store user playlists
log_file = 'user_playlists.json'

# Load user playlists from the log file
def load_playlists():
    global user_playlists
    try:
        with open(log_file, 'r') as file:
            user_playlists = json.load(file)
    except FileNotFoundError:
        user_playlists = {}


# Save user playlists to the log file
def save_playlists():
    with open(log_file, 'w') as file:
        json.dump(user_playlists, file)

class ScrollableSuggestions(View):
    def __init__(self, suggestions):
        super().__init__()
        self.suggestions = suggestions
        self.page = 0
        self.max_page = (len(suggestions) - 1) // 5

        self.update_buttons()

    def update_buttons(self):
        self.clear_items()

        for suggestion in self.suggestions[self.page * 5:(self.page + 1) * 5]:
            self.add_item(Button(label=suggestion, style=discord.ButtonStyle.secondary))

        if self.page > 0:
            self.add_item(Button(label="Previous", style=discord.ButtonStyle.primary, custom_id="prev"))

        if self.page < self.max_page:
            self.add_item(Button(label="Next", style=discord.ButtonStyle.primary, custom_id="next"))

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.data["custom_id"] == "prev":
            self.page -= 1
        elif interaction.data["custom_id"] == "next":
            self.page += 1

        self.update_buttons()
        await interaction.response.edit_message(view=self)

class MusicBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_clients = {}
        load_playlists()

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

async def get_audio_url(self, url: str):
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'default_search': 'ytsearch',
        'noplaylist': True,
        'extract_flat': 'in_playlist',
        'source_address': '0.0.0.0',  # bind to ipv4 since ipv6 addresses cause issues sometimes
        'socket_timeout': 10,  # set a timeout for socket connections
        'retries': 3,  # number of retries in case of failure
        'ffmpeg_location': 'ffmpeg',  # specify path to your FFmpeg binary
        'nocheckcertificate': True  # ignore certificate errors (use with caution)
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if 'entries' in info:
                info = info['entries'][0]
            return info['url']
    except yt_dlp.DownloadError as e:
        print(f"Download error: {e}")
        return None


    @app_commands.command(name="suggest", description="Get suggestions")
    async def suggest_command(self, ctx):
        suggestions = ["suggestion1", "suggestion2", "suggestion3", "suggestion4", "suggestion5", "suggestion6", "suggestion7", "suggestion8", "suggestion9", "suggestion10"]
        view = ScrollableSuggestions(suggestions)
        await ctx.send("Here are your suggestions:", view=view)

    @app_commands.command(name="play", description="Play music from a URL or resume the current music")
    async def play(self, interaction: discord.Interaction, url: str = None):
        vc = await self.join_channel(interaction)
        if vc is None:
            return

        if url:
            vc.stop()
            audio_url = await self.get_audio_url(url)
            if audio_url:
                vc.play(discord.FFmpegPCMAudio(executable="ffmpeg", source=audio_url))
                while vc.is_playing():
                    await asyncio.sleep(1)
                await interaction.response.send_message(f"Finished playing: {url}")
            else:
                await interaction.response.send_message(f"Failed to retrieve audio from URL: {url}")
        else:
            vc.resume()
            await interaction.response.send_message("Resumed the music.")

    @app_commands.command(name="play_p", description="Play your playlist")
    async def play_p(self, interaction: discord.Interaction):
        await interaction.response.defer()  # Acknowledge the interaction to avoid timeout

        user_id = interaction.user.id
        if user_id not in user_playlists or not user_playlists[user_id]:
            await interaction.followup.send("Your playlist is empty.")
            return

        vc = await self.join_channel(interaction)
        if vc is None:
            return

        for url in user_playlists[user_id]:
            vc.stop()
            audio_url = await self.get_audio_url(url)
            if audio_url:
                vc.play(discord.FFmpegPCMAudio(executable="ffmpeg", source=audio_url))
                while vc.is_playing():
                    await asyncio.sleep(1)

        await interaction.followup.send("Finished playing your playlist.")

    @app_commands.command(name="add", description="Add a song to your playlist")
    @app_commands.describe(url="The URL of the song to add")
    async def add(self, interaction: discord.Interaction, url: str):
        user_id = interaction.user.id
        if user_id not in user_playlists:
            user_playlists[user_id] = []
        user_playlists[user_id].append(url)
        save_playlists()
        await interaction.response.send_message(f"Added {url} to your playlist.")

    @app_commands.command(name="showplist", description="Show your playlist")
    async def show_playlist(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        if user_id not in user_playlists or not user_playlists[user_id]:
            await interaction.response.send_message("Your playlist is empty.")
            return

        playlist_embed = discord.Embed(
            title="Your Playlist",
            description="Here are the tracks in your playlist:",
            color=discord.Color.blue()
        )

        for index, url in enumerate(user_playlists[user_id], start=1):
            playlist_embed.add_field(
                name=f"Track {index}",
                value=url,
                inline=False
            )

        await interaction.response.send_message(embed=playlist_embed)

    @app_commands.command(name="skip", description="Skip to the next song in the playlist")
    async def skip(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await interaction.response.send_message("Skipped to the next song.")
        else:
            await interaction.response.send_message("No song is currently playing.")

    @app_commands.command(name="stop", description="Stop the music")
    async def stop(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await interaction.response.send_message("Stopped the music.")
        else:
            await interaction.response.send_message("No song is currently playing.")

    @app_commands.command(name="remove", description="Remove a song from your playlist")
    @app_commands.describe(url="The URL of the song to remove")
    async def remove(self, interaction: discord.Interaction, url: str):
        user_id = interaction.user.id
        if user_id in user_playlists and url in user_playlists[user_id]:
            user_playlists[user_id].remove(url)
            save_playlists()
            await interaction.response.send_message(f"Removed {url} from your playlist.")
        else:
            await interaction.response.send_message(f"{url} is not in your playlist.")

    @app_commands.command(name="resume", description="Resume the music")
    async def resume(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and not vc.is_playing():
            vc.resume()
            await interaction.response.send_message("Resumed the music.")
        else:
            await interaction.response.send_message("No song is currently paused.")

    @app_commands.command(name="join", description="Join a voice channel")
    async def join(self, interaction: discord.Interaction):
        vc = await self.join_channel(interaction)
        if not vc:
            await interaction.response.send_message("Failed to join the voice channel.")
            return

        await interaction.response.send_message("Joined the voice channel!")

    @app_commands.command(name="leave", description="Leave the voice channel")
    async def leave(self, interaction: discord.Interaction):
        if interaction.guild.voice_client is not None:
            await interaction.guild.voice_client.disconnect()
            await interaction.response.send_message("Left the voice channel.")
        else:
            await interaction.response.send_message("I am not in a voice channel.")

async def setup():
    await bot.add_cog(MusicBot(bot))

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}!')
    try:
        await tree.sync()
    except Exception as e:
        print(f"Error during sync: {e}")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandInvokeError):
        await ctx.send("There was an error trying to execute that command.")
        print(f"Error during command invocation: {error}")

@bot.event
async def on_error(event, *args, **kwargs):
    print(f"Error in event {event}: {args[0]}")

async def main():
    async with bot:
        await setup()
        await bot.start(DISCORD_BOT_TOKEN)

asyncio.run(main())

bot.run(DISCORD_BOT_TOKEN)
