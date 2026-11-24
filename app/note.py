"""Render, name, de-duplicate and write Notes. Pure: no network."""

import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

import yaml

from app.models import TWITTER, Analysis, Metadata, Platform, SourceText
from app.twitter import tweet_id

MAX_SLUG = 60


def normalise_tags(tags: list[str], platform: Platform) -> list[str]:
    """Lowercase kebab-case, deduplicated, the Platform tag always first."""
    result = [platform.slug]
    for tag in tags:
        kebab = re.sub(r"[^a-z0-9]+", "-", _ascii(tag).lower()).strip("-")
        if kebab and kebab not in result:
            result.append(kebab)
    return result


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", _ascii(title).lower()).strip("-")
    return slug[:MAX_SLUG].strip("-") or "untitled"


def normalise_url(url: str) -> str:
    """Duplicate-check key: host and path; a tweet is keyed by its ID alone."""
    if TWITTER.url_pattern.match(url.strip()):
        return f"x.com/status/{tweet_id(url)}"
    parts = urlsplit(url.strip())
    return f"{parts.netloc.lower()}{parts.path.rstrip('/')}"


def render_note(
    meta: Metadata, analysis: Analysis, source: SourceText, created: date
) -> str:
    frontmatter = {
        "title": meta.title,
        "source": meta.url,
        "author": meta.author,
        "published": meta.published.isoformat() if meta.published else None,
        "created": created.isoformat(),
        "duration": meta.duration,
        "platform": meta.platform.slug,
        "type": meta.platform.note_type,
        "language": source.language,
        "tags": normalise_tags(analysis.tags, meta.platform),
        "summary": analysis.summary_sentence,
    }
    if meta.duration is None:
        del frontmatter["duration"]
    yaml_text = yaml.safe_dump(
        frontmatter, sort_keys=False, allow_unicode=True, width=float("inf")
    )

    def bullets(items: list[str]) -> str:
        return "\n".join(f"- {item}" for item in items)

    sections = [
        f"## Summary\n\n{analysis.summary}",
        f"## Key ideas\n\n{bullets(analysis.key_ideas)}",
    ]
    if analysis.insights:
        sections.append(f"## Insights\n\n{bullets(analysis.insights)}")
    if analysis.takeaways:
        sections.append(f"## Actionable takeaways\n\n{bullets(analysis.takeaways)}")
    if analysis.quotes:
        sections.append(
            "## Quotes\n\n" + "\n\n".join(f"> {q}" for q in analysis.quotes)
        )
    heading = meta.platform.source_heading
    quoted = "\n".join(f"> {line}" for line in source.text.splitlines())
    sections.append(f"## {heading}\n\n> [!note]- {heading}\n{quoted}")
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
    meta: Metadata,
    analysis: Analysis,
    source: SourceText,
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
    path.write_text(render_note(meta, analysis, source, processed), encoding="utf-8")
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
