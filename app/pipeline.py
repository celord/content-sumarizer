"""Run one Link through duplicate check, metadata, Transcript, Analysis and Note writing."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import anthropic

from app.analyze import analyze
from app.config import Settings
from app.note import find_existing, normalise_tags, write_note
from app.tiktok import fetch_metadata
from app.transcribe import get_transcript

# Failures surface as the typed errors of the stages: TikTokError subclasses
# (VideoPrivate, VideoUnavailable, VideoTooLong, NoSpeech, TranscriptionFailed)
# and AnalysisError.


@dataclass(frozen=True)
class Result:
    path: Path
    title: str
    tags: list[str]
    duplicate: bool = False


def process(url: str, settings: Settings) -> Result:
    """Blocking. Returns the new (or already existing) Note, or raises a typed stage error."""
    vault = Path(settings.vault_path)
    if existing := find_existing(vault, url):
        return _duplicate(existing)

    meta = fetch_metadata(url, settings.max_duration_seconds)
    # Short links only resolve to their canonical URL after the metadata fetch.
    if meta.url != url and (existing := find_existing(vault, meta.url)):
        return _duplicate(existing)

    transcript = get_transcript(
        url, settings.groq_api_key, base_url=settings.stt_base_url, model=settings.stt_model
    )
    analysis = analyze(
        transcript,
        meta,
        settings.note_language,
        client=None if settings.llm_base_url else anthropic.Anthropic(api_key=settings.anthropic_api_key),
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
    )
    path = write_note(
        vault / settings.note_subfolder, meta, analysis, transcript, date.today()
    )
    return Result(path=path, title=meta.title, tags=normalise_tags(analysis.tags))


def _duplicate(path: Path) -> Result:
    return Result(path=path, title=path.stem, tags=[], duplicate=True)
