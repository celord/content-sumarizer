"""Shared domain types. See GLOSSARY.md."""

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class VideoMetadata:
    url: str
    title: str
    author: str
    published: date | None
    duration: int  # seconds


@dataclass(frozen=True)
class Transcript:
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
