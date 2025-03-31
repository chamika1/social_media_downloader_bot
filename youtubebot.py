import subprocess
import json
import asyncio
import time
import logging
from io import BytesIO
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackContext, MessageHandler, filters

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()  # This will print logs to console
    ]
)
logger = logging.getLogger(__name__)

# Add an initial log message to verify logging is working
logger.info("Bot logging initialized")

# Initialize global variables
tracks = []  # Initialize tracks globally
downloading = False  # Flag to indicate if a download is in progress


# Function to handle /start command
async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(
        "🎉 Welcome to the Video & Playlist Downloader!\n"
        "Use /help to see available options.")


# Function to handle /help command
async def help_command(update: Update, context: CallbackContext) -> None:
    help_text = ("📜 Available commands:\n"
                 "/start - Start the bot\n"
                 "/help - Show available commands\n"
                 "/download_video <url> - Download a single video\n"
                 "/download_playlist <playlist_url> - Load a playlist\n"
                 "/stop - Stop the current download")
    await update.message.reply_text(help_text)


# Function to download media (video or audio)
def download_media(url, audio_only=False):
    try:
        logger.info(f"Starting download for URL: {url} (audio_only={audio_only})")
        if audio_only:
            command = [
                'python', '-m', 'yt_dlp', 
                '--cookies', 'cookies.txt',  # Add cookies file
                '-f', 'bestaudio', '-x', 
                '--audio-format', 'mp3', 
                '-o', '-', 
                url
            ]
        else:
            command = [
                'python', '-m', 'yt_dlp',
                '--cookies', 'cookies.txt',  # Add cookies file
                '-o', '-', 
                url
            ]

        logger.info(f"Executing command: {' '.join(command)}")
        
        # Use shell=False since we're using python -m
        result = subprocess.run(command, capture_output=True, shell=False)
        
        logger.info(f"Command completed with return code: {result.returncode}")
        
        if result.returncode == 0:
            logger.info("Download completed successfully")
            return BytesIO(result.stdout)
        else:
            error_message = result.stderr.decode()
            logger.error(f"Download failed with error: {error_message}")
            print(f"Error output: {error_message}")  # Console output for debugging
            return error_message
    except Exception as e:
        logger.error(f"Exception during download: {str(e)}", exc_info=True)
        print(f"Exception occurred: {str(e)}")  # Console output for debugging
        return f"Error: {str(e)}"


# Function to show a loading animation
async def show_loading_animation(update: Update, message: str) -> None:
    loading_message = await update.message.reply_text(message)
    loading_text = message  # Initialize loading text

    for _ in range(3):
        await asyncio.sleep(0.5)
        new_loading_text = message + "." * (_ % 3)

        if new_loading_text != loading_text:  # Check if the text has changed
            loading_text = new_loading_text
            await loading_message.edit_text(loading_text)

    return loading_message


# Asynchronous wrapper for the download
async def async_download(update: Update, url: str, audio_only: bool):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, download_media, url, audio_only)


# Command to stop the current download
async def stop_download(update: Update, context: CallbackContext) -> None:
    global downloading
    downloading = False  # Set the flag to indicate stopping the download
    await update.message.reply_text("🛑 Download stopped.")


# Command to download a single video
async def download_video_command(update: Update,
                                 context: CallbackContext) -> None:
    global downloading
    downloading = True  # Set downloading flag

    if len(context.args) < 1:
        await update.message.reply_text("⚠️ Usage: /download_video <url>")
        return

    url = context.args[0]
    loading_message = await show_loading_animation(
        update, "⌛ Downloading video... Please wait.")

    start_time = time.time()  # Start timing

    media_file = await async_download(update, url, audio_only=False)
    downloading = False  # Reset downloading flag

    response_time = time.time() - start_time  # Calculate response time

    if isinstance(media_file, str):
        await loading_message.reply_text(f"❌ {media_file}")
    else:
        try:
            media_file.seek(0)
            await loading_message.edit_text(
                f"✅ Download successful in {response_time:.2f} seconds! Sending..."
            )
            await update.message.reply_video(
                video=media_file,
                caption="🌟 Enjoy your cinematic experience! 📽️\n"
                f"— {context.bot.name} 🎉")
        except Exception as e:
            await update.message.reply_text(f"❌ Error sending file: {e}")


# Function to download a playlist
async def download_playlist_command(update: Update,
                                    context: CallbackContext) -> None:
    global downloading
    downloading = True  # Set downloading flag

    if len(context.args) < 1:
        await update.message.reply_text(
            "⚠️ Usage: /download_playlist <playlist_url>")
        return

    playlist_url = context.args[0]
    loading_message = await show_loading_animation(
        update, "⌛ Loading playlist... Please wait.")

    command = ['yt-dlp', '--flat-playlist', '-J', playlist_url]
    result = subprocess.run(command, capture_output=True)

    if result.returncode != 0:
        await update.message.reply_text(
            f"❌ Failed to load playlist: {playlist_url}")
        downloading = False  # Reset downloading flag
        return

    global tracks
    tracks = json.loads(result.stdout)["entries"]

    track_list_text = "🎶 Available tracks:\n" + "\n".join(
        [f"{i + 1}: {track['title']}" for i, track in enumerate(tracks)])

    await loading_message.edit_text(track_list_text)
    await update.message.reply_text(
        "🔢 Enter the track number to download, '0' for all, or 'back' to return."
    )


# Handle track selection for downloading
async def handle_track_selection(update: Update,
                                 context: CallbackContext) -> None:
    global downloading

    if not downloading:
        await update.message.reply_text(
            "⚠️ No download in progress. Use /download_playlist to start.")
        return

    user_input = update.message.text.strip()

    if user_input.lower() == "back":
        await update.message.reply_text(
            "🔙 Back to main menu. Use /help for options.")
        return

    if user_input == "0":
        if not tracks:
            await update.message.reply_text(
                "⚠️ No tracks loaded. Please load a playlist first.")
            return

        for i, track in enumerate(tracks):
            if not downloading:  # Check if the download was stopped
                await update.message.reply_text("🛑 Download stopped.")
                break

            await update.message.reply_text(
                f"📥 Downloading '{track['title']}'...")
            audio_only = "music.youtube.com" in track['url']
            loading_message = await show_loading_animation(
                update, "⌛ Downloading track... Please wait.")

            media_file = await async_download(update, track['url'], audio_only)

            if not downloading:  # Check again if the download was stopped
                await update.message.reply_text("🛑 Download stopped.")
                break

            if isinstance(media_file, str):
                await update.message.reply_text(f"❌ {media_file}")
            else:
                media_file.seek(0)
                try:
                    if audio_only:
                        await update.message.reply_audio(
                            audio=media_file,
                            filename='audio.mp3',
                            caption="🎵 Enjoy your audio!")
                    else:
                        await update.message.reply_video(
                            video=media_file,
                            filename=f"{track['title']}.mp4",
                            caption="🌟 Enjoy your cinematic experience! 📽️\n"
                            f"— {context.bot.name} 🎉")
                except Exception as e:
                    await update.message.reply_text(
                        f"❌ Error sending file: {e}")

    else:
        try:
            track_index = int(user_input) - 1
            if 0 <= track_index < len(tracks):
                track = tracks[track_index]

                await update.message.reply_text(
                    f"📥 Downloading '{track['title']}'...")
                audio_only = "music.youtube.com" in track['url']
                loading_message = await show_loading_animation(
                    update, "⌛ Downloading track... Please wait.")

                media_file = await async_download(update, track['url'],
                                                  audio_only)

                if not downloading:  # Check if the download was stopped
                    await update.message.reply_text("🛑 Download stopped.")
                    return

                if isinstance(media_file, str):
                    await update.message.reply_text(f"❌ {media_file}")
                else:
                    media_file.seek(0)
                    try:
                        if audio_only:
                            await update.message.reply_audio(
                                audio=media_file,
                                filename='audio.mp3',
                                caption="🎵 Enjoy your audio!")
                        else:
                            await update.message.reply_video(
                                video=media_file,
                                filename=f"{track['title']}.mp4",
                                caption="🌟 Enjoy your Video! 📽️\n"
                                f"— {context.bot.name} 🎉")
                    except Exception as e:
                        await update.message.reply_text(
                            f"❌ Error sending file: {e}")
            else:
                await update.message.reply_text("⚠️ Invalid track index.")
        except ValueError:
            await update.message.reply_text(
                "⚠️ Please enter a valid number or 'back.'")


# Main function to initialize and run the bot
def main():
    try:
        logger.info("Starting bot...")
        application = ApplicationBuilder().token(
            "7612893886:AAFi1odrdIYztAivNcannNnSdK24e3aL9JE").build()

        # Register command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(
            CommandHandler("download_video", download_video_command))
        application.add_handler(
            CommandHandler("download_playlist", download_playlist_command))
        application.add_handler(CommandHandler("stop", stop_download))
        application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND,
                           handle_track_selection))

        logger.info("Bot started successfully")
        application.run_polling()
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)


if __name__ == "__main__":
    main()
