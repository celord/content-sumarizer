import os
from datetime import date
from unittest.mock import MagicMock, patch

import httpx
import pytest
from yt_dlp.utils import DownloadError

from app import tiktok, transcribe
from app.models import Transcript
from app.tiktok import VideoPrivate, VideoTooLong, VideoUnavailable, fetch_metadata
from app.transcribe import NoSpeech, get_transcript, vtt_to_text

URL = "https://www.tiktok.com/@someone/video/123"

INFO = {
    "webpage_url": URL,
    "title": "A title",
    "uploader": "someone",
    "upload_date": "20260102",
    "duration": 42,
}

VTT = """WEBVTT

1
00:00:00.000 --> 00:00:02.000
Hello <c>there</c>

2
00:00:02.000 --> 00:00:04.000
Hello there

3
00:00:04.000 --> 00:00:06.000
this is a test
"""


def fake_ydl(info=None, error=None):
    ydl = MagicMock()
    ydl.__enter__.return_value = ydl
    if error:
        ydl.extract_info.side_effect = error
    else:
        ydl.extract_info.return_value = info
    return patch("app.tiktok.YoutubeDL", return_value=ydl)


def test_fetch_metadata():
    with fake_ydl(INFO):
        meta = fetch_metadata(URL, 900)
    assert meta.title == "A title"
    assert meta.author == "someone"
    assert meta.published == date(2026, 1, 2)
    assert meta.duration == 42
    assert meta.url == URL


def test_too_long():
    with fake_ydl({**INFO, "duration": 901}), pytest.raises(VideoTooLong):
        fetch_metadata(URL, 900)


def test_private_video():
    with fake_ydl(error=DownloadError("This video is private")), pytest.raises(VideoPrivate):
        fetch_metadata(URL, 900)


def test_unavailable_video():
    with fake_ydl(error=DownloadError("HTTP 404")), pytest.raises(VideoUnavailable):
        fetch_metadata(URL, 900)


def test_vtt_to_text_strips_timing_and_repeats():
    assert vtt_to_text(VTT) == "Hello there this is a test"


def test_subtitles_path_skips_whisper():
    info = {"subtitles": {"eng-US": [{"ext": "vtt", "url": "http://x/sub.vtt"}]}}
    response = MagicMock(text=VTT)
    with (
        fake_ydl(info),
        patch("app.transcribe.httpx.get", return_value=response),
        patch("app.transcribe._whisper_transcript") as whisper,
    ):
        transcript = get_transcript(URL, "key")
    assert transcript == Transcript("Hello there this is a test", "eng-US")
    whisper.assert_not_called()


def test_whisper_fallback():
    with (
        fake_ydl({"subtitles": {}}),
        patch(
            "app.transcribe._whisper_transcript",
            return_value=Transcript("spoken words here", "english"),
        ) as whisper,
    ):
        transcript = get_transcript(URL, "key")
    assert transcript.text == "spoken words here"
    whisper.assert_called_once_with(URL, "key")


def test_groq_request_and_cleanup(tmp_path):
    seen = {}

    def fake_download(url, tmp):
        seen["dir"] = tmp
        audio = tmp / "audio.mp3"
        audio.write_bytes(b"x")
        return audio

    response = MagicMock()
    response.json.return_value = {"text": " hola mundo ", "language": "spanish"}
    with (
        patch("app.transcribe._download_audio", side_effect=fake_download),
        patch("app.transcribe.httpx.post", return_value=response) as post,
    ):
        transcript = transcribe._whisper_transcript(URL, "secret")
    assert transcript == Transcript("hola mundo", "spanish")
    assert post.call_args.kwargs["data"]["model"] == "whisper-large-v3-turbo"
    assert post.call_args.kwargs["headers"]["Authorization"] == "Bearer secret"
    assert not seen["dir"].exists()


def test_groq_http_error():
    response = MagicMock()
    response.raise_for_status.side_effect = httpx.HTTPError("boom")
    with (
        patch("app.transcribe._download_audio", side_effect=lambda u, t: _touch(t)),
        patch("app.transcribe.httpx.post", return_value=response),
        pytest.raises(transcribe.TranscriptionFailed),
    ):
        transcribe._whisper_transcript(URL, "k")


def _touch(tmp):
    path = tmp / "audio.mp3"
    path.write_bytes(b"x")
    return path


def test_no_speech():
    with (
        fake_ydl({"subtitles": {}}),
        patch("app.transcribe._whisper_transcript", return_value=Transcript(" ", None)),
        pytest.raises(NoSpeech),
    ):
        get_transcript(URL, "key")


@pytest.mark.skipif(
    not (os.environ.get("GROQ_API_KEY") and os.environ.get("TIKTOK_TEST_URL")),
    reason="needs GROQ_API_KEY and TIKTOK_TEST_URL",
)
def test_live():
    url = os.environ["TIKTOK_TEST_URL"]
    meta = fetch_metadata(url, 900)
    transcript = get_transcript(url, os.environ["GROQ_API_KEY"])
    assert meta.title
    assert transcript.text
