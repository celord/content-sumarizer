import os
from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_LLM_MODEL = "claude-haiku-5-5"
DEFAULT_NOTE_SUBFOLDER = "Inbox/TikTok"
DEFAULT_NOTE_LANGUAGE = "English"
DEFAULT_MAX_DURATION_SECONDS = 900

REQUIRED_VARS = (
    "TELEGRAM_BOT_TOKEN",
    "ALLOWED_CHAT_IDS",
    "VAULT_PATH",
)


class ConfigError(Exception):
    """The environment does not hold a valid configuration."""


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    allowed_chat_ids: frozenset[int]
    anthropic_api_key: str | None
    groq_api_key: str | None
    vault_path: str
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    stt_base_url: str | None = None
    stt_model: str | None = None
    llm_model: str = DEFAULT_LLM_MODEL
    note_subfolder: str = DEFAULT_NOTE_SUBFOLDER
    note_language: str = DEFAULT_NOTE_LANGUAGE
    max_duration_seconds: int = DEFAULT_MAX_DURATION_SECONDS


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """Build Settings from env (defaults to os.environ). Empty values count as unset."""
    source = os.environ if env is None else env

    def get(name: str) -> str | None:
        value = source.get(name, "").strip()
        return value or None

    missing = [name for name in REQUIRED_VARS if get(name) is None]
    # LLM_BASE_URL switches Analysis to an OpenAI-compatible API (OpenRouter, NVIDIA NIM,
    # local Ollama). Its key is optional because a local server takes none.
    if not get("LLM_BASE_URL") and get("ANTHROPIC_API_KEY") is None:
        missing.append("ANTHROPIC_API_KEY")
    # STT_BASE_URL switches speech-to-text from Groq to a local Whisper server.
    if not get("STT_BASE_URL") and get("GROQ_API_KEY") is None:
        missing.append("GROQ_API_KEY")
    if missing:
        raise ConfigError("Missing required environment variables: " + ", ".join(missing))

    return Settings(
        telegram_bot_token=get("TELEGRAM_BOT_TOKEN"),
        allowed_chat_ids=_parse_chat_ids(get("ALLOWED_CHAT_IDS")),
        anthropic_api_key=get("ANTHROPIC_API_KEY"),
        groq_api_key=get("GROQ_API_KEY"),
        vault_path=get("VAULT_PATH"),
        llm_base_url=get("LLM_BASE_URL"),
        llm_api_key=get("LLM_API_KEY"),
        stt_base_url=get("STT_BASE_URL"),
        stt_model=get("STT_MODEL"),
        llm_model=get("LLM_MODEL") or DEFAULT_LLM_MODEL,
        note_subfolder=get("NOTE_SUBFOLDER") or DEFAULT_NOTE_SUBFOLDER,
        note_language=get("NOTE_LANGUAGE") or DEFAULT_NOTE_LANGUAGE,
        max_duration_seconds=_parse_positive_int(
            "MAX_DURATION_SECONDS", get("MAX_DURATION_SECONDS"), DEFAULT_MAX_DURATION_SECONDS
        ),
    )


def _parse_chat_ids(raw: str) -> frozenset[int]:
    try:
        ids = frozenset(int(part) for part in raw.split(",") if part.strip())
    except ValueError:
        raise ConfigError(
            f"ALLOWED_CHAT_IDS must be a comma-separated list of integers, got {raw!r}"
        ) from None
    if not ids:
        raise ConfigError("ALLOWED_CHAT_IDS must contain at least one chat id")
    return ids


def _parse_positive_int(name: str, raw: str | None, default: int) -> int:
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from None
    if value <= 0:
        raise ConfigError(f"{name} must be greater than 0, got {value}")
    return value
