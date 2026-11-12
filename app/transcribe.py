"""Transcript: TikTok subtitles when present, otherwise Groq Whisper."""

import re
import subprocess
import tempfile
from pathlib import Path

import httpx

from app.models import Transcript
from app.tiktok import TikTokError, extract_info

GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_MODEL = "whisper-large-v3-turbo"
GROQ_MAX_BYTES = 25 * 1024 * 1024
MIN_SPEECH_CHARS = 10
HTTP_TIMEOUT = 120


class NoSpeech(TikTokError):
    """The video has no usable speech (photo carousel, music only)."""


class TranscriptionFailed(TikTokError):
    """Audio download, conversion or speech-to-text failed."""


def get_transcript(url: str, groq_api_key: str) -> Transcript:
    info = extract_info(url)
    transcript = _subtitle_transcript(info) or _whisper_transcript(url, groq_api_key)
    if len(transcript.text) < MIN_SPEECH_CHARS:
        raise NoSpeech("No speech found")
    return transcript


def _subtitle_transcript(info: dict) -> Transcript | None:
    tracks = info.get("subtitles") or {}
    for lang, formats in tracks.items():
        vtt = next((f for f in formats if f.get("ext") == "vtt" and f.get("url")), None)
        if vtt is None:
            continue
        try:
            response = httpx.get(vtt["url"], timeout=HTTP_TIMEOUT, follow_redirects=True)
            response.raise_for_status()
        except httpx.HTTPError:
            continue
        text = vtt_to_text(response.text)
        if text:
            return Transcript(text=text, language=lang)
    return None


def vtt_to_text(vtt: str) -> str:
    """Strip WebVTT headers, cue ids, timings and tags; collapse repeated lines."""
    lines: list[str] = []
    in_note = False
    for raw in vtt.splitlines():
        line = raw.strip()
        if not line:
            in_note = False
            continue
        if in_note or line.startswith(("WEBVTT", "Kind:", "Language:", "STYLE", "REGION")):
            continue
        if line.startswith("NOTE"):
            in_note = True
            continue
        if "-->" in line:
            continue
        line = re.sub(r"<[^>]+>", "", line).strip()
        if line and not re.fullmatch(r"\d+", line) and (not lines or lines[-1] != line):
            lines.append(line)
    return " ".join(lines)


def _whisper_transcript(url: str, groq_api_key: str) -> Transcript:
    with tempfile.TemporaryDirectory() as tmp:
        audio = _download_audio(url, Path(tmp))
        if audio.stat().st_size > GROQ_MAX_BYTES:
            raise TranscriptionFailed("Compressed audio exceeds the 25 MB Whisper limit")
        return _groq_transcribe(audio, groq_api_key)


def _download_audio(url: str, tmp: Path) -> Path:
    try:
        info = extract_info(
            url,
            download=True,
            format="bestaudio/best",
            outtmpl=str(tmp / "source.%(ext)s"),
        )
    except TikTokError as exc:
        raise TranscriptionFailed(f"Audio download failed: {exc}") from exc
    if not info:
        raise TranscriptionFailed("Audio download failed")
    sources = [p for p in tmp.glob("source.*")]
    if not sources:
        raise TranscriptionFailed("Audio download produced no file")
    out = tmp / "audio.mp3"
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", str(sources[0]), "-vn", "-ac", "1", "-ar", "16000",
         "-b:a", "32k", str(out)],
        capture_output=True,
    )
    if result.returncode != 0 or not out.exists():
        raise TranscriptionFailed("ffmpeg conversion failed")
    return out


def _groq_transcribe(audio: Path, api_key: str) -> Transcript:
    try:
        with audio.open("rb") as fh:
            response = httpx.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                data={"model": GROQ_MODEL, "response_format": "verbose_json"},
                files={"file": (audio.name, fh, "audio/mpeg")},
                timeout=HTTP_TIMEOUT,
            )
        response.raise_for_status()
        body = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise TranscriptionFailed(f"Groq transcription failed: {exc}") from exc
    return Transcript(text=(body.get("text") or "").strip(), language=body.get("language"))
