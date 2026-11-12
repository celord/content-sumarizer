import asyncio
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app import bot, pipeline
from app.analyze import AnalysisError
from app.config import Settings
from app.models import Analysis, Transcript, VideoMetadata
from app.tiktok import VideoPrivate, VideoTooLong, VideoUnavailable
from app.transcribe import NoSpeech, TranscriptionFailed

URL = "https://www.tiktok.com/@someone/video/123"
META = VideoMetadata(url=URL, title="A title", author="someone", published=date(2026, 1, 2), duration=42)
TRANSCRIPT = Transcript(text="hello there this is a test", language="en")
ANALYSIS = Analysis("One.", "Sum.", ["k"], ["i"], ["t"], ["Alpha", "beta", "gamma"])


def settings(tmp_path: Path) -> Settings:
    return Settings("tok", frozenset({1}), "a", "g", str(tmp_path))


def test_extract_urls():
    text = "look https://vm.tiktok.com/ZMabc/, and (https://www.tiktok.com/@a/video/1). also https://example.com/x"
    assert bot.extract_tiktok_urls(text) == [
        "https://vm.tiktok.com/ZMabc/",
        "https://www.tiktok.com/@a/video/1",
    ]
    assert bot.extract_tiktok_urls("no link, nottiktok.com/x") == []


@pytest.mark.parametrize(
    "exc, fragment",
    [
        (VideoPrivate("x"), "private"),
        (VideoTooLong(1000, 900), "too long"),
        (NoSpeech("x"), "No speech"),
        (VideoUnavailable("x"), "Download failed"),
        (TranscriptionFailed("x"), "Download failed"),
        (AnalysisError("x"), "Model error"),
        (RuntimeError("x"), "went wrong"),
    ],
)
def test_error_message(exc, fragment):
    assert fragment in bot.error_message(exc)


def make_update(chat_id: int, text: str | None):
    message = MagicMock(chat_id=chat_id, text=text)
    message.set_reaction = AsyncMock()
    message.reply_text = AsyncMock()
    context = MagicMock()
    context.application.bot_data = {"settings": Settings("t", frozenset({1}), "a", "g", "/v"), "queue": asyncio.Queue()}
    return MagicMock(effective_message=message), context, message


async def test_allowlist_and_enqueue():
    update, context, message = make_update(2, f"hi {URL}")
    await bot._on_message(update, context)
    message.set_reaction.assert_not_called()
    assert context.application.bot_data["queue"].empty()

    update, context, message = make_update(1, "no link here")
    await bot._on_message(update, context)
    assert context.application.bot_data["queue"].empty()

    update, context, message = make_update(1, f"hi {URL}")
    await bot._on_message(update, context)
    message.set_reaction.assert_awaited_once_with("⏳")
    assert context.application.bot_data["queue"].get_nowait() == (message, URL)


async def test_worker_replies_for_result_and_error(tmp_path):
    s = settings(tmp_path)
    queue: asyncio.Queue = asyncio.Queue()
    ok, bad = MagicMock(), MagicMock()
    ok.reply_text = AsyncMock()
    bad.reply_text = AsyncMock()
    result = pipeline.Result(tmp_path / "Inbox" / "n.md", "T", ["tiktok", "x"])
    with patch("app.bot.pipeline.process", side_effect=[result, VideoPrivate("p")]):
        task = asyncio.create_task(bot._worker(queue, s))
        queue.put_nowait((ok, "u1"))
        queue.put_nowait((bad, "u2"))
        await asyncio.wait_for(queue.join(), 5)
        task.cancel()
    assert ok.reply_text.await_args.args[0] == "T\n#tiktok #x\nInbox/n.md"
    assert "private" in bad.reply_text.await_args.args[0]


def patch_stages(**overrides):
    stages = {
        "fetch_metadata": MagicMock(return_value=META),
        "get_transcript": MagicMock(return_value=TRANSCRIPT),
        "analyze": MagicMock(return_value=ANALYSIS),
        **overrides,
    }
    return stages, [patch(f"app.pipeline.{k}", v) for k, v in stages.items()]


def run_process(tmp_path, **overrides):
    stages, patches = patch_stages(**overrides)
    for p in patches:
        p.start()
    try:
        return stages, pipeline.process(URL, settings(tmp_path))
    finally:
        for p in patches:
            p.stop()


def test_process_writes_note(tmp_path):
    stages, result = run_process(tmp_path)
    assert not result.duplicate
    assert result.path.parent == tmp_path / "Inbox/TikTok"
    assert result.path.exists()
    assert result.tags == ["tiktok", "alpha", "beta", "gamma"]
    assert result.title == "A title"


def test_process_duplicate_stops_early(tmp_path):
    _, first = run_process(tmp_path)
    stages, second = run_process(tmp_path)
    assert second.duplicate and second.path == first.path
    stages["fetch_metadata"].assert_not_called()


def test_process_duplicate_after_short_link_resolution(tmp_path):
    run_process(tmp_path)
    stages, patches = patch_stages()
    for p in patches:
        p.start()
    try:
        result = pipeline.process("https://vm.tiktok.com/ZMabc/", settings(tmp_path))
    finally:
        for p in patches:
            p.stop()
    assert result.duplicate
    stages["get_transcript"].assert_not_called()


def test_process_propagates_stage_errors_and_writes_nothing(tmp_path):
    with pytest.raises(NoSpeech):
        run_process(tmp_path, get_transcript=MagicMock(side_effect=NoSpeech("x")))
    assert not list(tmp_path.rglob("*.md"))
