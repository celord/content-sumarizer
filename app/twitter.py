"""Tweet text via the public FxTwitter JSON API. See docs/adr/0001-fxtwitter-for-tweet-text.md."""

import re
from datetime import UTC, datetime

import httpx

from app.models import TWITTER, Metadata, SourceText

API_BASE = "https://api.fxtwitter.com"
HTTP_TIMEOUT = 20
TITLE_CHARS = 60
STATUS_ID = re.compile(r"/status/(\d+)")


def tweet_id(url: str) -> str:
    match = STATUS_ID.search(url)
    if match is None:
        raise ValueError(f"Not a tweet Link: {url}")
    return match.group(1)


def fetch_tweet(url: str) -> tuple[Metadata, SourceText]:
    """Metadata (canonical x.com URL) and Source Text (tweet plus any quoted tweet)."""
    with httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=True) as http:
        response = http.get(f"{API_BASE}/status/{tweet_id(url)}")
    response.raise_for_status()
    tweet = response.json()["tweet"]

    handle = tweet["author"]["screen_name"]
    text = tweet.get("text") or ""
    source = text
    if quote := tweet.get("quote"):
        source += f"\n\nQuoting @{quote['author']['screen_name']}:\n{quote.get('text') or ''}"
    timestamp = tweet.get("created_timestamp")
    meta = Metadata(
        url=f"https://x.com/{handle}/status/{tweet['id']}",
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
