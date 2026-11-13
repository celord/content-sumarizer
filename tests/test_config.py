import pytest

from app.config import ConfigError, load_settings

BASE_ENV = {
    "TELEGRAM_BOT_TOKEN": "123:token",
    "ALLOWED_CHAT_IDS": "111,-100222",
    "ANTHROPIC_API_KEY": "sk-ant-test",
    "GROQ_API_KEY": "gsk-test",
    "VAULT_PATH": "/vault",
}


def test_defaults_apply_when_optional_vars_unset():
    settings = load_settings(BASE_ENV)

    assert settings.telegram_bot_token == "123:token"
    assert settings.allowed_chat_ids == frozenset({111, -100222})
    assert settings.anthropic_api_key == "sk-ant-test"
    assert settings.groq_api_key == "gsk-test"
    assert settings.vault_path == "/vault"
    assert settings.llm_model == "claude-haiku-5-5"
    assert settings.note_subfolder == "Inbox/TikTok"
    assert settings.note_language == "English"
    assert settings.max_duration_seconds == 900


def test_optional_vars_override_defaults():
    env = {
        **BASE_ENV,
        "LLM_MODEL": "claude-sonnet-5-5",
        "NOTE_SUBFOLDER": "Clips",
        "NOTE_LANGUAGE": "Spanish",
        "MAX_DURATION_SECONDS": "300",
    }

    settings = load_settings(env)

    assert settings.llm_model == "claude-sonnet-5-5"
    assert settings.note_subfolder == "Clips"
    assert settings.note_language == "Spanish"
    assert settings.max_duration_seconds == 300


def test_missing_required_vars_are_all_named():
    env = {"TELEGRAM_BOT_TOKEN": "123:token"}

    with pytest.raises(ConfigError) as exc:
        load_settings(env)

    message = str(exc.value)
    for name in ("ALLOWED_CHAT_IDS", "ANTHROPIC_API_KEY", "GROQ_API_KEY", "VAULT_PATH"):
        assert name in message
    assert "TELEGRAM_BOT_TOKEN" not in message


def test_empty_value_counts_as_missing():
    env = {**BASE_ENV, "GROQ_API_KEY": "   "}

    with pytest.raises(ConfigError, match="GROQ_API_KEY"):
        load_settings(env)


def test_empty_optional_value_falls_back_to_default():
    env = {**BASE_ENV, "LLM_MODEL": "", "MAX_DURATION_SECONDS": ""}

    settings = load_settings(env)

    assert settings.llm_model == "claude-haiku-5-5"
    assert settings.max_duration_seconds == 900


def test_chat_ids_tolerate_whitespace():
    settings = load_settings({**BASE_ENV, "ALLOWED_CHAT_IDS": " 1 , -2 ,3 "})

    assert settings.allowed_chat_ids == frozenset({1, -2, 3})


@pytest.mark.parametrize("raw", ["abc", "1,two", ",", " , "])
def test_invalid_chat_ids_rejected(raw):
    with pytest.raises(ConfigError, match="ALLOWED_CHAT_IDS"):
        load_settings({**BASE_ENV, "ALLOWED_CHAT_IDS": raw})


@pytest.mark.parametrize("raw", ["abc", "1.5"])
def test_non_integer_duration_rejected(raw):
    with pytest.raises(ConfigError, match="MAX_DURATION_SECONDS must be an integer"):
        load_settings({**BASE_ENV, "MAX_DURATION_SECONDS": raw})


@pytest.mark.parametrize("raw", ["0", "-5"])
def test_non_positive_duration_rejected(raw):
    with pytest.raises(ConfigError, match="MAX_DURATION_SECONDS must be greater than 0"):
        load_settings({**BASE_ENV, "MAX_DURATION_SECONDS": raw})


def test_error_message_does_not_leak_secret_values():
    env = {**BASE_ENV, "TELEGRAM_BOT_TOKEN": "", "ANTHROPIC_API_KEY": "sk-ant-secret"}

    with pytest.raises(ConfigError) as exc:
        load_settings(env)

    assert "sk-ant-secret" not in str(exc.value)


def test_openai_compatible_provider_does_not_need_anthropic_key():
    env = {**BASE_ENV, "ANTHROPIC_API_KEY": "", "LLM_BASE_URL": "https://openrouter.ai/api/v1"}
    assert load_settings(env).llm_api_key is None  # local servers take no key
    settings = load_settings({**env, "LLM_API_KEY": "or-key"})
    assert settings.llm_base_url == "https://openrouter.ai/api/v1"
    assert settings.llm_api_key == "or-key"
    assert settings.anthropic_api_key is None


def test_local_stt_does_not_need_groq_key():
    env = {**BASE_ENV, "GROQ_API_KEY": "", "STT_BASE_URL": "http://whisper:8000/v1"}
    settings = load_settings({**env, "STT_MODEL": "deepdml/faster-whisper-large-v3-turbo-ct2"})
    assert settings.groq_api_key is None
    assert settings.stt_base_url == "http://whisper:8000/v1"
    assert settings.stt_model == "deepdml/faster-whisper-large-v3-turbo-ct2"
