"""X Links through pipeline.process, with FxTwitter faked at the HTTP layer."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
import yaml

from app import pipeline
from app.config import Settings
from app.errors import ContentPrivate, ContentUnavailable
from app.models import Analysis
from app.twitter import TweetFetchFailed

ANALYSIS = Analysis("One.", "Sum.", ["k"], ["i"], ["t"], ["Alpha", "beta", "gamma"])
TWEET = {
    "code": 200,
    "message": "OK",
    "tweet": {
        "id": "1800000000000000001",
        "url": "https://x.com/SomeOne/status/1800000000000000001",
        "text": "Sleep before midnight. It resets your focus for the whole next day, every day.",
        "created_timestamp": 1767312000,  # 2026-01-02
        "lang": "en",
        "author": {"screen_name": "SomeOne", "name": "Some One"},
        "quote": {
            "text": "What is the one habit that changed your work?",
            "author": {"screen_name": "asker"},
        },
        "media": {"photos": [{"url": "https://pbs.twimg.com/x.jpg"}]},
    },
}


def settings(tmp_path: Path) -> Settings:
    return Settings("tok", frozenset({1}), "a", "g", str(tmp_path))


def run(tmp_path, url, body=TWEET):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=body)

    real_client = httpx.Client
    analyze = MagicMock(return_value=ANALYSIS)
    with (
        patch("app.twitter.httpx.Client",
              side_effect=lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw)),
        patch("app.pipeline.analyze", analyze),
        patch("app.pipeline.get_transcript") as transcribe,
    ):
        result = pipeline.process(url, settings(tmp_path))
    transcribe.assert_not_called()
    return result, requests, analyze


def frontmatter(path: Path) -> dict:
    return yaml.safe_load(path.read_text().split("---\n")[1])


def test_tweet_becomes_note(tmp_path):
    result, requests, analyze = run(tmp_path, "https://x.com/SomeOne/status/1800000000000000001?s=20")

    assert requests[0].url.host == "api.fxtwitter.com"
    assert requests[0].url.path.endswith("/status/1800000000000000001")
    assert result.path.parent == tmp_path / "Inbox/Twitter"
    assert result.tags == ["twitter", "alpha", "beta", "gamma"]
    assert result.title == "@SomeOne: Sleep before midnight. It resets your focus for the whole…"

    fm = frontmatter(result.path)
    assert fm["platform"] == "twitter" and fm["type"] == "tweet-note"
    assert fm["source"] == "https://x.com/SomeOne/status/1800000000000000001"
    assert fm["author"] == "SomeOne"
    assert fm["published"] == "2026-01-02"
    assert "duration" not in fm
    assert fm["tags"][0] == "twitter"

    body = result.path.read_text()
    assert "## Tweet" in body
    assert "Sleep before midnight." in body
    assert "What is the one habit that changed your work?" in body
    assert "twimg" not in body

    source, meta = analyze.call_args.args[0], analyze.call_args.args[1]
    assert "@asker" in source.text and "Sleep before midnight." in source.text
    assert meta.platform.slug == "twitter"


@pytest.mark.parametrize("again", [
    "https://twitter.com/SomeOne/status/1800000000000000001",
    "https://mobile.twitter.com/other_name/status/1800000000000000001/",
    "https://x.com/i/status/1800000000000000001?s=46",
])
def test_same_tweet_under_any_url_is_duplicate(tmp_path, again):
    first, _, _ = run(tmp_path, "https://x.com/SomeOne/status/1800000000000000001")
    second, requests, _ = run(tmp_path, again)
    assert second.duplicate and second.path == first.path
    assert requests == []


def test_short_tweet_title_not_truncated(tmp_path):
    body = json.loads(json.dumps(TWEET))
    body["tweet"]["text"] = "gm\nfriends"
    del body["tweet"]["quote"]
    result, _, _ = run(tmp_path, "https://x.com/SomeOne/status/1800000000000000001", body)
    assert result.title == "@SomeOne: gm friends"


def failing(tmp_path, handler):
    real_client = httpx.Client
    with (
        patch("app.twitter.httpx.Client",
              side_effect=lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw)),
        patch("app.pipeline.analyze") as analyze,
    ):
        try:
            pipeline.process("https://x.com/SomeOne/status/1800000000000000001", settings(tmp_path))
        finally:
            analyze.assert_not_called()
            assert not list(tmp_path.rglob("*.md"))


def respond(status, body):
    return lambda request: httpx.Response(status, json=body)


def test_deleted_tweet_is_unavailable(tmp_path):
    with pytest.raises(ContentUnavailable):
        failing(tmp_path, respond(404, {"code": 404, "message": "NOT_FOUND", "tweet": None}))


def test_protected_tweet_is_private(tmp_path):
    with pytest.raises(ContentPrivate):
        failing(tmp_path, respond(401, {"code": 401, "message": "PRIVATE_TWEET", "tweet": None}))


@pytest.mark.parametrize("handler", [
    respond(500, {"code": 500, "message": "API_FAIL"}),
    respond(200, {"code": 200, "message": "OK"}),  # no tweet
    lambda request: httpx.Response(200, text="<html>oops</html>"),
    lambda request: (_ for _ in ()).throw(httpx.ConnectTimeout("slow", request=request)),
])
def test_fetch_failures_raise_tweet_fetch_failed(tmp_path, handler):
    with pytest.raises(TweetFetchFailed):
        failing(tmp_path, handler)
