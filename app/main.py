import argparse
import sys

import asyncio
from app.plugins import platform_plugins
from app.core.summarizer import summarize_text
from app.core.utils import create_markdown_note
import app.util as util


async def get_platform(video_url: str):
    """
    Finds the appropriate platform for the given video URL.
    """
    for plugin in platform_plugins.values():
        if hasattr(plugin, "initialize") and not getattr(plugin, "initialized", False):
            await plugin.initialize()
            plugin.initialized = True
        if await plugin.can_handle_url(video_url):

            return plugin
    return None


async def main():
    util.init_logging()
    parser = argparse.ArgumentParser(description="Video Summarizer")
    parser.add_argument("video_url", help="The URL of the video to summarize.")
    args = parser.parse_args()

    video_url = args.video_url
    platform = await get_platform(video_url)

    if not platform:
        print(f"Error: Platform not supported for URL: {video_url}")
        sys.exit(1)

    try:
        title = await platform.get_video_title(video_url)
        transcription = await platform.get_transcription(video_url)
        summary = summarize_text(transcription)
        note_path = create_markdown_note(title, summary)
        print(f"Successfully created note: {note_path}")
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # When running with `python -m app.main`, if no URL is provided on the
    # command line, this block adds a default one for testing purposes.
    if len(sys.argv) == 1:
        sys.argv.append("https://www.tiktok.com/@maklelan/video/7355850487834545454")

    asyncio.run(main())
