"""Telegram bot: filter messages, queue Links, process them one at a time."""

import asyncio
import logging
import re
from pathlib import Path

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from app import pipeline
from app.analyze import AnalysisError
from app.config import Settings
from app.errors import ContentPrivate, ContentUnavailable
from app.models import platform_for
from app.transcribe import NoSpeech, TranscriptionFailed
from app.twitter import NoTweetText, TweetFetchFailed
from app.video import VideoTooLong

logger = logging.getLogger(__name__)

URL = re.compile(r"https?://\S+", re.IGNORECASE)
QUEUE_KEY = "queue"
WORKER_KEY = "worker"


def extract_links(text: str) -> list[str]:
    """Links of any supported Platform, in order, without duplicates."""
    urls = (m.group().rstrip(".,;:!?)]}>\"'") for m in URL.finditer(text))
    return list(dict.fromkeys(u for u in urls if platform_for(u)))


def error_message(exc: Exception) -> str:
    """One short human message per error type."""
    if isinstance(exc, ContentPrivate):
        return "This content is private."
    if isinstance(exc, VideoTooLong):
        return f"Video is too long ({exc.duration}s, limit {exc.limit}s)."
    if isinstance(exc, NoSpeech):
        return "No speech found, skipped."
    if isinstance(exc, ContentUnavailable):
        return "This content is unavailable (removed or unreachable)."
    if isinstance(exc, NoTweetText):
        return "This tweet has no text, skipped."
    if isinstance(exc, TweetFetchFailed):
        return "Couldn't fetch tweet, try later."
    if isinstance(exc, TranscriptionFailed):
        return "Download failed."
    if isinstance(exc, AnalysisError):
        return "Model error, try again later."
    return "Something went wrong."


def format_result(result: pipeline.Result, vault: str) -> str:
    name = str(Path(result.path).relative_to(vault)) if vault else result.path.name
    if result.duplicate:
        return f"Already saved: {name}"
    tags = " ".join(f"#{t}" for t in result.tags)
    return f"{result.title}\n{tags}\n{name}"


def build_application(settings: Settings) -> Application:
    app = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(_start_worker)
        .post_shutdown(_stop_worker)
        .build()
    )
    app.bot_data["settings"] = settings
    app.add_handler(MessageHandler(filters.TEXT, _on_message))
    return app


async def _on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    settings: Settings = context.application.bot_data["settings"]
    if message is None or not message.text:
        return
    if message.chat_id not in settings.allowed_chat_ids:
        logger.warning("ignored message from chat %s (not in ALLOWED_CHAT_IDS)", message.chat_id)
        return
    urls = extract_links(message.text)
    if not urls:
        return
    queue: asyncio.Queue = context.application.bot_data[QUEUE_KEY]
    logger.info("received %d link(s) from chat %s, queue length %d: %s",
                len(urls), message.chat_id, queue.qsize(), " ".join(urls))
    try:
        await message.set_reaction("👀")  # must be one of Telegram's allowed reaction emoji
    except Exception:
        logger.warning("could not react to message", exc_info=True)
    for url in urls:
        queue.put_nowait((message, url))


async def _start_worker(app: Application) -> None:
    queue: asyncio.Queue = asyncio.Queue()
    app.bot_data[QUEUE_KEY] = queue
    app.bot_data[WORKER_KEY] = asyncio.create_task(_worker(queue, app.bot_data["settings"]))


async def _stop_worker(app: Application) -> None:
    # Startup can fail (e.g. a bad token) before the worker exists.
    task: asyncio.Task | None = app.bot_data.get(WORKER_KEY)
    if task is not None:
        task.cancel()


async def _worker(queue: asyncio.Queue, settings: Settings) -> None:
    """Process queued Links one at a time; blocking work runs in a thread."""
    while True:
        message, url = await queue.get()
        try:
            logger.info("%s: started", url)
            result = await asyncio.to_thread(pipeline.process, url, settings)
            reply = format_result(result, settings.vault_path)
            logger.info("%s: done", url)
        except Exception as exc:
            logger.exception("processing %s failed", url)
            reply = error_message(exc)
        try:
            await message.reply_text(reply)
        except Exception:
            logger.exception("could not reply for %s", url)
        finally:
            queue.task_done()
