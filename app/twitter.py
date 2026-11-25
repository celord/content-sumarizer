"""Tweet text via the public FxTwitter JSON API. See docs/adr/0001-fxtwitter-for-tweet-text.md."""

import re
from datetime import UTC, datetime

import httpx

from app.errors import ContentPrivate, ContentUnavailable, FetchError
from app.models import TWITTER, Metadata, SourceText

API_BASE = "https://api.fxtwitter.com"
HTTP_TIMEOUT = 20
# FxTwitter answers 403 to the default python-httpx User-Agent.
USER_AGENT = "content-summarizer-bot/1.0"
TITLE_CHARS = 60
STATUS_ID = re.compile(r"/status/(\d+)")


NO_LANGUAGE = {"und", "zxx", "qme", "qht", "qst"}  # X codes for "no linguistic content"


class NoTweetText(FetchError):
    """The tweet has no text to analyse (media only)."""


class TweetFetchFailed(FetchError):
    """FxTwitter is down, timed out or returned something unexpected."""


def tweet_id(url: str) -> str:
    match = STATUS_ID.search(url)
    if match is None:
        raise ValueError(f"Not a tweet Link: {url}")
    return match.group(1)


def fetch_tweet(url: str) -> tuple[Metadata, SourceText]:
    """Metadata (canonical x.com URL) and Source Text (tweet plus any quoted tweet)."""
    try:
        with httpx.Client(
            timeout=HTTP_TIMEOUT, follow_redirects=True, headers={"User-Agent": USER_AGENT}
        ) as http:
            response = http.get(f"{API_BASE}/status/{tweet_id(url)}")
    except httpx.HTTPError as exc:
        raise TweetFetchFailed(f"FxTwitter request failed: {exc}") from exc
    if response.status_code == 404:
        raise ContentUnavailable("Tweet not found or deleted")
    if response.status_code in (401, 403):
        raise ContentPrivate("Tweet is from a protected account")
    if 400 <= response.status_code < 500 and response.status_code != 429:
        raise ContentUnavailable(f"FxTwitter refused the Link: {response.status_code}")
    try:
        response.raise_for_status()
        tweet = response.json()["tweet"]
        handle = tweet["author"]["screen_name"]
        status_id = tweet["id"]
    except (httpx.HTTPStatusError, ValueError, KeyError, TypeError) as exc:
        raise TweetFetchFailed(
            f"Unexpected FxTwitter response: {response.status_code} {response.text[:300]}"
        ) from exc

    text = tweet.get("text") or ""
    source = text
    quote_text = ""
    if quote := tweet.get("quote"):
        quoted = (quote.get("author") or {}).get("screen_name") or "unknown"
        quote_text = quote.get("text") or ""
        source += f"\n\nQuoting @{quoted}:\n{quote_text}"
    if not (text.strip() or quote_text.strip()):
        raise NoTweetText("Tweet has no text")
    timestamp = tweet.get("created_timestamp")
    lang = tweet.get("lang")
    meta = Metadata(
        url=f"https://x.com/{handle}/status/{status_id}",
        title=f"@{handle}: {_shorten(text)}",
        author=handle,
        published=datetime.fromtimestamp(timestamp, UTC).date() if timestamp else None,
        platform=TWITTER,
    )
    return meta, SourceText(text=source, language=None if lang in NO_LANGUAGE else lang)


def _shorten(text: str) -> str:
    flat = " ".join(text.split())
    if len(flat) <= TITLE_CHARS:
        return flat
    cut = flat[:TITLE_CHARS]
    return (cut.rsplit(" ", 1)[0] if " " in cut else cut).rstrip(" ,.;:") + "…"
