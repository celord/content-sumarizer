"""Render, name, de-duplicate and write Notes. Pure: no network."""

import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

import yaml

from app.models import Analysis, Transcript, VideoMetadata

MAX_SLUG = 60


def normalise_tags(tags: list[str]) -> list[str]:
    """Lowercase kebab-case, deduplicated, `tiktok` always first."""
    result = ["tiktok"]
    for tag in tags:
        kebab = re.sub(r"[^a-z0-9]+", "-", _ascii(tag).lower()).strip("-")
        if kebab and kebab not in result:
            result.append(kebab)
    return result


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", _ascii(title).lower()).strip("-")
    return slug[:MAX_SLUG].strip("-") or "untitled"


def normalise_url(url: str) -> str:
    parts = urlsplit(url.strip())
    return f"{parts.netloc.lower()}{parts.path.rstrip('/')}"


def render_note(
    meta: VideoMetadata, analysis: Analysis, transcript: Transcript, created: date
) -> str:
    frontmatter = {
        "title": meta.title,
        "source": meta.url,
        "author": meta.author,
        "published": meta.published.isoformat() if meta.published else None,
        "created": created.isoformat(),
        "duration": meta.duration,
        "platform": "tiktok",
        "type": "video-note",
        "language": transcript.language,
        "tags": normalise_tags(analysis.tags),
        "summary": analysis.summary_sentence,
    }
    yaml_text = yaml.safe_dump(
        frontmatter, sort_keys=False, allow_unicode=True, width=float("inf")
    )

    def bullets(items: list[str]) -> str:
        return "\n".join(f"- {item}" for item in items)

    sections = [
        f"## Summary\n\n{analysis.summary}",
        f"## Key ideas\n\n{bullets(analysis.key_ideas)}",
        f"## Insights\n\n{bullets(analysis.insights)}",
        f"## Actionable takeaways\n\n{bullets(analysis.takeaways)}",
    ]
    if analysis.quotes:
        sections.append(
            "## Quotes\n\n" + "\n\n".join(f"> {q}" for q in analysis.quotes)
        )
    quoted = "\n".join(f"> {line}" for line in transcript.text.splitlines())
    sections.append(f"## Transcript\n\n> [!note]- Transcript\n{quoted}")
    return f"---\n{yaml_text}---\n\n" + "\n\n".join(sections) + "\n"


def find_existing(vault_dir: Path, url: str) -> Path | None:
    """Return the Note whose frontmatter `source:` matches `url`."""
    wanted = normalise_url(url)
    for path in sorted(vault_dir.rglob("*.md")):
        source = _read_source(path)
        if source and normalise_url(source) == wanted:
            return path
    return None


def write_note(
    directory: Path,
    meta: VideoMetadata,
    analysis: Analysis,
    transcript: Transcript,
    processed: date,
) -> Path:
    """Write the Note into `directory` (created if missing); return its path."""
    directory.mkdir(parents=True, exist_ok=True)
    base = f"{processed.isoformat()} {slugify(meta.title)}"
    path = directory / f"{base}.md"
    n = 2
    while path.exists():
        path = directory / f"{base} ({n}).md"
        n += 1
    path.write_text(render_note(meta, analysis, transcript, processed), encoding="utf-8")
    return path


def _ascii(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def _read_source(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    try:
        data = yaml.safe_load(text[4:end])
    except yaml.YAMLError:
        return None
    source = data.get("source") if isinstance(data, dict) else None
    return source if isinstance(source, str) else None
