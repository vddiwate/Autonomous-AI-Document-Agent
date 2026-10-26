import os
import sys
import logging
from pathlib import Path
from app.config import settings

LOGS_DIR = settings.BASE_DIR if hasattr(settings, "BASE_DIR") else Path(__file__).resolve().parent.parent.parent
LOG_PATH = LOGS_DIR / "logs"
os.makedirs(LOG_PATH, exist_ok=True)
LOG_FILE = LOG_PATH / "app.log"

def setup_logging():
    """
    Configures centralized logging for both terminal console and persistent file logs.
    Ensures real-time visibility for pipeline monitoring.
    """
    log_format = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicates
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # 1. Console Stream Handler (immediate stdout flush)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
    console_handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))
    root_logger.addHandler(console_handler)

    # 2. File Handler (saves to logs/app.log)
    file_handler = logging.FileHandler(str(LOG_FILE), encoding="utf-8")
    file_handler.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
    file_handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))
    root_logger.addHandler(file_handler)

    logging.info(f"Logging initialized. Log file: {LOG_FILE}")
