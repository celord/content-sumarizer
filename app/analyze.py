"""Analysis: turn a Transcript into an Analysis with Claude (tool use)."""

import os
import re

import anthropic

from app.analyze_prompt import SYSTEM_PROMPT, USER_TEMPLATE
from app.models import Analysis, Transcript, VideoMetadata

DEFAULT_LLM_MODEL = "claude-haiku-5-5"
MAX_ATTEMPTS = 2  # first try plus one retry on malformed output
MIN_TAGS, MAX_TAGS = 3, 7

_STR_LIST = {"type": "array", "items": {"type": "string"}}
TOOL = {
    "name": "record_analysis",
    "description": "Record the analysis of the video transcript.",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary_sentence": {"type": "string"},
            "summary": {"type": "string"},
            "key_ideas": _STR_LIST,
            "insights": _STR_LIST,
            "takeaways": _STR_LIST,
            "quotes": _STR_LIST,
            "tags": _STR_LIST,
        },
        "required": [
            "summary_sentence",
            "summary",
            "key_ideas",
            "insights",
            "takeaways",
            "quotes",
            "tags",
        ],
    },
}


class AnalysisError(Exception):
    """The model did not return a valid analysis."""


def analyze(
    transcript: Transcript,
    metadata: VideoMetadata,
    language: str,
    *,
    client: anthropic.Anthropic | None = None,
    model: str | None = None,
) -> Analysis:
    """Analyze a Transcript. Retries once on malformed output, then raises AnalysisError."""
    client = client or anthropic.Anthropic()
    model = model or os.environ.get("LLM_MODEL") or DEFAULT_LLM_MODEL
    user = USER_TEMPLATE.format(
        title=metadata.title,
        author=metadata.author,
        duration=metadata.duration,
        transcript=transcript.text,
    )

    problem = "no response"
    for _ in range(MAX_ATTEMPTS):
        response = client.messages.create(
            model=model,
            max_tokens=2048,
            system=SYSTEM_PROMPT.format(language=language),
            messages=[{"role": "user", "content": user}],
            tools=[TOOL],
            tool_choice={"type": "tool", "name": TOOL["name"]},
        )
        block = next((b for b in response.content if b.type == "tool_use"), None)
        if block is None:
            problem = "model returned no tool call"
            continue
        try:
            return _parse(block.input, transcript.text)
        except ValueError as exc:
            problem = str(exc)
    raise AnalysisError(f"Malformed analysis after {MAX_ATTEMPTS} attempts: {problem}")


def _parse(data: object, transcript_text: str) -> Analysis:
    if not isinstance(data, dict):
        raise ValueError("tool input is not an object")

    def text(key: str) -> str:
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} must be a non-empty string")
        return value.strip()

    def items(key: str, *, required: bool = True) -> list[str]:
        value = data.get(key, [])
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise ValueError(f"{key} must be a list of strings")
        cleaned = [v.strip() for v in value if v.strip()]
        if required and not cleaned:
            raise ValueError(f"{key} must not be empty")
        return cleaned

    tags = _unique([_kebab(t) for t in items("tags")])
    if not MIN_TAGS <= len(tags) <= MAX_TAGS:
        raise ValueError(f"tags must hold {MIN_TAGS} to {MAX_TAGS} entries, got {len(tags)}")

    haystack = _squash(transcript_text)
    quotes = [q for q in items("quotes", required=False) if _squash(q) in haystack]

    return Analysis(
        summary_sentence=text("summary_sentence"),
        summary=text("summary"),
        key_ideas=items("key_ideas"),
        insights=items("insights"),
        takeaways=items("takeaways"),
        tags=tags,
        quotes=quotes,
    )


def _kebab(tag: str) -> str:
    return re.sub(r"[^\w]+", "-", tag.lower().lstrip("#")).strip("-")


def _unique(values: list[str]) -> list[str]:
    return [v for v in dict.fromkeys(values) if v]


def _squash(value: str) -> str:
    return " ".join(value.lower().split())
