"""Analysis: turn a Transcript into an Analysis.

Two providers: Anthropic (tool use, the default) and any OpenAI-compatible
chat completions API such as OpenRouter or NVIDIA NIM (JSON in the reply text,
because many free models there do not support tool calls).
"""

import json
import os
import re

import anthropic
import httpx

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
    base_url: str | None = None,
    api_key: str | None = None,
    http: httpx.Client | None = None,
) -> Analysis:
    """Analyze a Transcript. Retries once on malformed output, then raises AnalysisError.

    With base_url set, calls that OpenAI-compatible API instead of Anthropic.
    """
    model = model or os.environ.get("LLM_MODEL") or DEFAULT_LLM_MODEL
    system = SYSTEM_PROMPT.format(language=language)
    user = USER_TEMPLATE.format(
        title=metadata.title,
        author=metadata.author,
        duration=metadata.duration,
        transcript=transcript.text,
    )

    if base_url:
        http = http or httpx.Client(timeout=120)

        def call() -> object:
            return _call_openai_compatible(http, base_url, api_key, model, system, user)

    else:
        client = client or anthropic.Anthropic()

        def call() -> object:
            return _call_anthropic(client, model, system, user)

    problem = "no response"
    for _ in range(MAX_ATTEMPTS):
        try:
            return _parse(call(), transcript.text)
        except ValueError as exc:
            problem = str(exc)
    raise AnalysisError(f"Malformed analysis after {MAX_ATTEMPTS} attempts: {problem}")


def _call_anthropic(client: anthropic.Anthropic, model: str, system: str, user: str) -> object:
    response = client.messages.create(
        model=model,
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": user}],
        tools=[TOOL],
        tool_choice={"type": "tool", "name": TOOL["name"]},
    )
    block = next((b for b in response.content if b.type == "tool_use"), None)
    if block is None:
        raise ValueError("model returned no tool call")
    return block.input


OPENAI_MAX_TOKENS = 8192

# An example object, not a JSON Schema: small models copy a schema's
# {"type": ..., "properties": ...} wrapper instead of filling it in.
JSON_INSTRUCTION = (
    "Reply with only a JSON object, no other text, with exactly these keys:\n"
    + json.dumps(
        {
            "summary_sentence": "<one sentence>",
            "summary": "<one paragraph>",
            "key_ideas": ["<idea>", "..."],
            "insights": ["<insight>", "..."],
            "takeaways": ["<takeaway>", "..."],
            "quotes": ["<verbatim line from the transcript, or leave the list empty>"],
            "tags": ["<tag>", "... 3 to 7 tags"],
        },
        indent=2,
    )
)


def _call_openai_compatible(
    http: httpx.Client,
    base_url: str,
    api_key: str | None,
    model: str,
    system: str,
    user: str,
) -> object:
    try:
        response = http.post(
            base_url.rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
            json={
                "model": model,
                # Reasoning models spend part of this budget thinking before they answer.
                "max_tokens": OPENAI_MAX_TOKENS,
                "messages": [
                    {"role": "system", "content": system + "\n\n" + JSON_INSTRUCTION},
                    {"role": "user", "content": user},
                ],
            },
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise AnalysisError(f"LLM request failed: {exc}") from exc
    try:
        choice = response.json()["choices"][0]
        content = choice["message"]["content"] or ""
    except (ValueError, KeyError, IndexError, TypeError):
        raise ValueError("response has no message content") from None
    if choice.get("finish_reason") == "length" and "}" not in content:
        raise ValueError(f"reply cut off at max_tokens={OPENAI_MAX_TOKENS}")
    # Models often wrap JSON in a code fence or add text around it.
    start, end = content.find("{"), content.rfind("}")
    if start == -1 or end < start:
        raise ValueError("reply holds no JSON object")
    try:
        return json.loads(content[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"reply is not valid JSON: {exc}") from None


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
