"""Run one Link through duplicate check, metadata, Transcript, Analysis and Note writing."""

import logging
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import anthropic

from app.analyze import analyze
from app.config import Settings
from app.note import find_existing, normalise_tags, write_note
from app.models import platform_for
from app.video import fetch_metadata
from app.transcribe import get_transcript

logger = logging.getLogger(__name__)

# Failures surface as the typed errors of the stages: FetchError subclasses
# (ContentPrivate, ContentUnavailable, VideoTooLong, NoSpeech, TranscriptionFailed)
# and AnalysisError.


@dataclass(frozen=True)
class Result:
    path: Path
    title: str
    tags: list[str]
    duplicate: bool = False


def process(url: str, settings: Settings) -> Result:
    """Blocking. Returns the new (or already existing) Note, or raises a typed stage error."""
    started = time.monotonic()

    def stage(name: str, detail: str = "") -> None:
        logger.info("%s: %s (%.1fs)%s", url, name, time.monotonic() - started,
                    f" {detail}" if detail else "")

    platform = platform_for(url)
    if platform is None:
        raise ValueError(f"Unsupported Link: {url}")
    vault = Path(settings.vault_path)
    if existing := find_existing(vault, url):
        stage("duplicate", existing.name)
        return _duplicate(existing)

    stage("fetching metadata")
    meta = fetch_metadata(url, platform, settings.max_duration_seconds)
    stage("metadata", f"title={meta.title!r} duration={meta.duration}s")
    # Short links only resolve to their canonical URL after the metadata fetch.
    if meta.url != url and (existing := find_existing(vault, meta.url)):
        stage("duplicate", existing.name)
        return _duplicate(existing)

    stage("transcribing", f"stt={settings.stt_base_url or 'groq'}")
    transcript = get_transcript(
        url, settings.groq_api_key, base_url=settings.stt_base_url, model=settings.stt_model
    )
    stage("transcript", f"chars={len(transcript.text)} language={transcript.language}")
    stage("analyzing", f"model={settings.llm_model}")
    analysis = analyze(
        transcript,
        meta,
        settings.note_language,
        client=None if settings.llm_base_url else anthropic.Anthropic(api_key=settings.anthropic_api_key),
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
    )
    stage("analysis", f"tags={len(analysis.tags)}")
    path = write_note(
        vault / settings.note_folder / platform.folder, meta, analysis, transcript, date.today()
    )
    stage("note written", str(path))
    return Result(path=path, title=meta.title, tags=normalise_tags(analysis.tags, platform))

def _duplicate(path: Path) -> Result:
    return Result(path=path, title=path.stem, tags=[], duplicate=True)
