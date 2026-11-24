"""Shared domain types. See GLOSSARY.md."""

import re
from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class Platform:
    slug: str  # frontmatter `platform` and first tag
    folder: str  # Notes go into <note folder>/<folder>
    note_type: str  # frontmatter `type`
    source_heading: str  # Note section holding the Source Text
    url_pattern: re.Pattern[str]


TIKTOK = Platform(
    slug="tiktok",
    folder="TikTok",
    note_type="video-note",
    source_heading="Transcript",
    url_pattern=re.compile(r"https?://(?:[\w-]+\.)?tiktok\.com/", re.IGNORECASE),
)
TWITTER = Platform(
    slug="twitter",
    folder="Twitter",
    note_type="tweet-note",
    source_heading="Tweet",
    url_pattern=re.compile(
        r"https?://(?:www\.|mobile\.)?(?:twitter|x)\.com/\w+/status/\d+", re.IGNORECASE
    ),
)
PLATFORMS = (TIKTOK, TWITTER)


def platform_for(url: str) -> Platform | None:
    return next((p for p in PLATFORMS if p.url_pattern.match(url)), None)


@dataclass(frozen=True)
class Metadata:
    url: str
    title: str
    author: str
    published: date | None
    platform: Platform
    duration: int | None = None  # seconds; videos only


@dataclass(frozen=True)
class SourceText:
    """What an Analysis is made from. For a video this is its Transcript."""

    text: str
    language: str | None


@dataclass(frozen=True)
class Analysis:
    summary_sentence: str
    summary: str
    key_ideas: list[str]
    insights: list[str]
    takeaways: list[str]
    tags: list[str]
    quotes: list[str] = field(default_factory=list)
