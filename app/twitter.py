"""Tweet text via the public FxTwitter JSON API. See docs/adr/0001-fxtwitter-for-tweet-text.md."""

import re
from datetime import UTC, datetime

import httpx

from app.errors import ContentPrivate, ContentUnavailable, FetchError
from app.models import TWITTER, Metadata, SourceText

API_BASE = "https://api.fxtwitter.com"
HTTP_TIMEOUT = 20
TITLE_CHARS = 60
STATUS_ID = re.compile(r"/status/(\d+)")


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
        with httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=True) as http:
            response = http.get(f"{API_BASE}/status/{tweet_id(url)}")
    except httpx.HTTPError as exc:
        raise TweetFetchFailed(f"FxTwitter request failed: {exc}") from exc
    if response.status_code == 404:
        raise ContentUnavailable("Tweet not found or deleted")
    if response.status_code in (401, 403):
        raise ContentPrivate("Tweet is from a protected account")
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
    if quote := tweet.get("quote"):
        quoted = (quote.get("author") or {}).get("screen_name") or "unknown"
        source += f"\n\nQuoting @{quoted}:\n{quote.get('text') or ''}"
    timestamp = tweet.get("created_timestamp")
    meta = Metadata(
        url=f"https://x.com/{handle}/status/{status_id}",
        title=f"@{handle}: {_shorten(text)}",
        author=handle,
        published=datetime.fromtimestamp(timestamp, UTC).date() if timestamp else None,
        platform=TWITTER,
    )
    return meta, SourceText(text=source, language=tweet.get("lang"))


def _shorten(text: str) -> str:
    flat = " ".join(text.split())
    if len(flat) <= TITLE_CHARS:
        return flat
    cut = flat[:TITLE_CHARS]
    return (cut.rsplit(" ", 1)[0] if " " in cut else cut).rstrip(" ,.;:") + "…"
