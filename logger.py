"""Centralized logging setup for the stock bot."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def get_logger() -> logging.Logger:
    """Create and return the app logger.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger("StockBot")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    log_dir = Path(__file__).resolve().parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(module)s] → %(message)s")

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        filename=log_dir / "bot.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.propagate = False
    return logger


LOGGER = get_logger()
