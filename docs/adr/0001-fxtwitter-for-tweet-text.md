# Use the FxTwitter API to fetch tweet text

X Links are text tweets, and yt-dlp only handles video. The official X API charges for reading tweets, and the syndication endpoint is undocumented and needs a token workaround. We fetch tweet text, author, date and any quoted tweet from the public FxTwitter JSON API (`api.fxtwitter.com/status/<id>`): it's free and needs no key.

## Consequences

- We depend on a third-party service that could go down or change. When it fails, the bot replies "couldn't fetch tweet, try later".
- All FxTwitter calls sit behind one fetch function, so switching to the X API later only touches that function.
- Fetching a whole author thread is out of scope; only the tweet in the Link is fetched.
