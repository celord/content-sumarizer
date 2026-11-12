import os
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.analyze import AnalysisError, analyze
from app.models import Analysis, Transcript, VideoMetadata

META = VideoMetadata("https://www.tiktok.com/@a/video/1", "Title", "a", date(2026, 1, 2), 30)
TRANSCRIPT = Transcript("Sleep before midnight. It resets your focus for the day.", "en")

VALID = {
    "summary_sentence": "Sleep before midnight to reset focus.",
    "summary": "The creator says early sleep restores focus.",
    "key_ideas": ["Sleep early"],
    "insights": ["Midnight is the cutoff the creator names"],
    "takeaways": ["Set a 11pm alarm"],
    "quotes": ["It resets your focus for the day.", "Invented line"],
    "tags": ["Sleep", "#focus", "Habits"],
}


def reply(data=None, *, tool=True):
    block = SimpleNamespace(type="tool_use", input=data) if tool else SimpleNamespace(type="text")
    return SimpleNamespace(content=[block])


def client_with(*responses):
    client = MagicMock()
    client.messages.create.side_effect = list(responses)
    return client


def test_valid_response_is_parsed():
    client = client_with(reply(VALID))
    result = analyze(TRANSCRIPT, META, "English", client=client, model="m")
    assert isinstance(result, Analysis)
    assert result.summary_sentence == VALID["summary_sentence"]
    assert result.tags == ["sleep", "focus", "habits"]
    assert result.quotes == ["It resets your focus for the day."]  # invented quote dropped
    kwargs = client.messages.create.call_args.kwargs
    assert kwargs["model"] == "m"
    assert "English" in kwargs["system"]
    assert "Sleep before midnight" in kwargs["messages"][0]["content"]


def test_model_defaults_from_env(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "custom-model")
    client = client_with(reply(VALID))
    analyze(TRANSCRIPT, META, "English", client=client)
    assert client.messages.create.call_args.kwargs["model"] == "custom-model"


def test_malformed_then_valid_retries_once():
    bad = {**VALID, "tags": ["only-one"]}
    client = client_with(reply(bad), reply(VALID))
    assert analyze(TRANSCRIPT, META, "English", client=client, model="m").tags
    assert client.messages.create.call_count == 2


@pytest.mark.parametrize("first", [reply({"summary": 1}), reply(tool=False)])
def test_malformed_twice_raises(first):
    client = client_with(first, reply({}))
    with pytest.raises(AnalysisError):
        analyze(TRANSCRIPT, META, "English", client=client, model="m")
    assert client.messages.create.call_count == 2


@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="needs ANTHROPIC_API_KEY")
def test_live_analysis():
    result = analyze(TRANSCRIPT, META, "English")
    assert result.summary_sentence and 3 <= len(result.tags) <= 7
