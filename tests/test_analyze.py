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


def openai_http(*contents):
    """httpx client that answers chat completions with the given message contents in order."""
    import httpx

    replies = iter(contents)
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": next(replies)}}]})

    return httpx.Client(transport=httpx.MockTransport(handler)), seen


def test_openai_compatible_provider_parses_fenced_json():
    import json

    http, seen = openai_http("Here you go:\n```json\n" + json.dumps(VALID) + "\n```")
    result = analyze(
        TRANSCRIPT, META, "English",
        model="meta/llama-3.3-70b-instruct", base_url="https://integrate.api.nvidia.com/v1/",
        api_key="k", http=http,
    )
    assert result.tags == ["sleep", "focus", "habits"]
    request = seen[0]
    assert str(request.url) == "https://integrate.api.nvidia.com/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer k"
    body = json.loads(request.content)
    assert body["model"] == "meta/llama-3.3-70b-instruct"
    assert "JSON" in body["messages"][0]["content"]


def test_openai_compatible_provider_retries_on_non_json_then_fails():
    http, seen = openai_http("sorry, no", "still no")
    with pytest.raises(AnalysisError, match="no JSON"):
        analyze(TRANSCRIPT, META, "English", model="m", base_url="https://x/v1", api_key="k", http=http)
    assert len(seen) == 2


def test_openai_compatible_provider_http_error_raises_analysis_error():
    import httpx

    http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(429)))
    with pytest.raises(AnalysisError, match="request failed"):
        analyze(TRANSCRIPT, META, "English", model="m", base_url="https://x/v1", api_key="k", http=http)
