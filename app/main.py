import logging
import sys

from app.bot import build_application
from app.config import ConfigError, load_settings

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # httpx logs every request URL at INFO, and Telegram URLs contain the bot token.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        settings = load_settings()
    except ConfigError as exc:
        logger.error("%s", exc)
        sys.exit(1)
    logger.info("starting")
    build_application(settings).run_polling()


if __name__ == "__main__":
    main()
