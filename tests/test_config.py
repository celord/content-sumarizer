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
