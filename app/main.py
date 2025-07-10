import argparse
import sys
from urllib.parse import urlparse
from app.plugins import platform_plugins
from app.core.summarizer import summarize_text
from app.core.utils import create_markdown_note

def get_platform_from_url(video_url: str):
    """
    Determines the platform from the video URL.
    """
    parsed_url = urlparse(video_url)
    domain = parsed_url.netloc.lower()

    if 'youtube.com' in domain or 'youtu.be' in domain:
        return 'youtube'
    elif 'tiktok.com' in domain:
        return 'tiktok'
    elif 'x.com' in domain or 'twitter.com' in domain:
        return 'x'
    return None

def main():
    parser = argparse.ArgumentParser(description="Video Summarizer")
    parser.add_argument("video_url", help="The URL of the video to summarize.")
    args = parser.parse_args()

    video_url = args.video_url
    platform_name = get_platform_from_url(video_url)

    if not platform_name or platform_name not in platform_plugins:
        print(f"Error: Platform not supported for URL: {video_url}")
        sys.exit(1)

    platform = platform_plugins[platform_name]

    try:
        title = platform.get_video_title(video_url)
        transcription = platform.get_transcription(video_url)
        summary = summarize_text(transcription)
        note_path = create_markdown_note(title, summary)
        print(f"Successfully created note: {note_path}")
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
