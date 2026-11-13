from datetime import date

import yaml

from app.models import Analysis, Transcript, VideoMetadata
from app.note import find_existing, normalise_tags, render_note, slugify, write_note

DAY = date(2026, 11, 12)


def meta(title="Hello", url="https://www.tiktok.com/@a/video/1"):
    return VideoMetadata(url=url, title=title, author="a", published=date(2026, 1, 2), duration=30)


def analysis(**kw):
    base = dict(
        summary_sentence="One.",
        summary="Para.",
        key_ideas=["k1", "k2"],
        insights=["i1"],
        takeaways=["t1"],
        tags=["Cooking Tips", "cooking-tips", "TikTok"],
        quotes=["Be bold"],
    )
    return Analysis(**{**base, **kw})


TR = Transcript(text="line one\n\nline three", language="en")


def frontmatter(text):
    return yaml.safe_load(text.split("---\n")[1])


def test_yaml_escaping_roundtrip():
    title = 'He said: "wow" #1 - it\'s: great'
    fm = frontmatter(render_note(meta(title), analysis(summary_sentence="a: b"), TR, DAY))
    assert fm["title"] == title
    assert fm["summary"] == "a: b"
    assert fm["created"] == "2026-11-12"
    assert fm["platform"] == "tiktok" and fm["type"] == "video-note"


def test_tag_normalisation():
    assert normalise_tags(["Cooking Tips", "cooking-tips", "TikTok", " AI_tools! ", ""]) == [
        "tiktok", "cooking-tips", "ai-tools"
    ]


def test_tiktok_first_in_note():
    fm = frontmatter(render_note(meta(), analysis(tags=["zzz"]), TR, DAY))
    assert fm["tags"] == ["tiktok", "zzz"]


def test_no_quotes_omits_section():
    assert "## Quotes" not in render_note(meta(), analysis(quotes=[]), TR, DAY)
    assert "## Quotes" in render_note(meta(), analysis(), TR, DAY)


def test_transcript_callout_prefixes_every_line():
    body = render_note(meta(), analysis(), TR, DAY).split("> [!note]-")[1]
    assert body.splitlines()[1:] == ["> line one", "> ", "> line three"]


def test_slug_is_safe_and_short():
    slug = slugify("Ça va? / Ünïcode: " + "x" * 100)
    assert len(slug) <= 60
    assert slug.startswith("ca-va-unicode-")
    assert all(c.isalnum() or c == "-" for c in slug)
    assert slugify("!!!") == "untitled"


def test_filename_collision(tmp_path):
    d = tmp_path / "Inbox" / "TikTok"
    p1 = write_note(d, meta(), analysis(), TR, DAY)
    p2 = write_note(d, meta(), analysis(), TR, DAY)
    p3 = write_note(d, meta(), analysis(), TR, DAY)
    assert p1.name == "2026-11-12 hello.md"
    assert p2.name == "2026-11-12 hello (2).md"
    assert p3.name == "2026-11-12 hello (3).md"


def test_find_existing_normalises_url(tmp_path):
    path = write_note(tmp_path / "sub", meta(), analysis(), TR, DAY)
    (tmp_path / "junk.md").write_text("no frontmatter")
    (tmp_path / "bad.md").write_text("---\n: [\n---\n")
    assert find_existing(tmp_path, "https://www.tiktok.com/@a/video/1/?utm=x#f") == path
    assert find_existing(tmp_path, "https://www.tiktok.com/@a/video/2") is None
