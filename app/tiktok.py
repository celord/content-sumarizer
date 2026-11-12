"""TikTok metadata via yt-dlp (no download)."""

from datetime import date, datetime
from typing import Any

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from app.models import VideoMetadata


class TikTokError(Exception):
    """Base class for TikTok fetch failures."""


class VideoPrivate(TikTokError):
    """The video is private."""


class VideoUnavailable(TikTokError):
    """The video is removed, region-locked or otherwise unreachable."""


class VideoTooLong(TikTokError):
    """The video is longer than MAX_DURATION_SECONDS."""

    def __init__(self, duration: int, limit: int):
        super().__init__(f"Video is {duration}s long, limit is {limit}s")
        self.duration = duration
        self.limit = limit


def extract_info(url: str, *, download: bool = False, **opts: Any) -> dict[str, Any]:
    """Run yt-dlp on url, mapping its failures to typed errors."""
    params = {"quiet": True, "no_warnings": True, "noplaylist": True, **opts}
    try:
        with YoutubeDL(params) as ydl:
            return ydl.extract_info(url, download=download)
    except DownloadError as exc:
        if "private" in str(exc).lower():
            raise VideoPrivate(str(exc)) from exc
        raise VideoUnavailable(str(exc)) from exc


def fetch_metadata(url: str, max_duration_seconds: int) -> VideoMetadata:
    info = extract_info(url)
    duration = int(info.get("duration") or 0)
    if duration > max_duration_seconds:
        raise VideoTooLong(duration, max_duration_seconds)
    return VideoMetadata(
        url=info.get("webpage_url") or url,
        title=info.get("title") or "",
        author=info.get("uploader") or info.get("channel") or "",
        published=_parse_date(info.get("upload_date")),
        duration=duration,
    )


def _parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y%m%d").date()
    except ValueError:
        return None
