from app.plugins.base_platform import BasePlatform
import whisper
import moviepy as mp
import tempfile
import os
import logging
import yt_dlp

log = logging.getLogger("app.plugins.tiktok")


class TikTok(BasePlatform):
    """
    Provides transcription services for TikTok videos.
    """

    def __init__(self, model_name="base"):
        self.model = None
        self.model_name = model_name

    async def initialize(self):
        """
        Initializes the Whisper model.
        """
        self.model = whisper.load_model(self.model_name)

    async def can_handle_url(self, video_url: str) -> bool:
        """
        Determines if the platform can handle the given video URL.
        """
        return "tiktok.com" in video_url

    async def get_transcription(self, video_url: str) -> str:
        """
        Retrieve the transcription for a TikTok video.
        """
        video_path = None
        audio_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=True) as temp_video_file:
                video_path = temp_video_file.name

            ydl_opts = {
                "outtmpl": video_path,
                "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio_file:
                audio_path = temp_audio_file.name

            video_clip = mp.VideoFileClip(video_path)
            video_clip.audio.write_audiofile(audio_path)
            log.info(f"Extracted audio to {audio_path}")
            video_clip.close()

            result = self.model.transcribe(audio_path)
            log.info(f"Transcription result: {result}")
            return result.get("text", "") if isinstance(result, dict) else ""

        except Exception as e:
            log.exception(f"Error processing TikTok video: {video_url}")
            return ""
        finally:
            if video_path and os.path.exists(video_path):
                os.remove(video_path)
            if audio_path and os.path.exists(audio_path):
                os.remove(audio_path)

    async def get_video_title(self, video_url: str) -> str:
        """
        Retrieves the title of a TikTok video.
        """
        try:
            log.info(f"Fetching title for TikTok video: {video_url}")
            with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
                info_dict = ydl.extract_info(video_url, download=False)
                return info_dict.get("title", "")
        except Exception as e:
            log.exception(f"Error fetching TikTok video data for url: {video_url}")
            return ""
