import logging


def init_logging():
    """
    Initializes the logging configuration for the application.
    """
    logger = logging.getLogger("app")
    logger.setLevel(logging.INFO)
    if not logger.hasHandlers():
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        logger.addHandler(handler)
    return logger
