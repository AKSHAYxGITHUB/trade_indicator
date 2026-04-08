"""Application configuration and constants for the stock bot."""

from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()


def _parse_allowed_users(raw_value: str) -> list[int]:
    """Parse comma-separated Telegram user IDs from environment.

    Args:
        raw_value: Comma-separated user ID values.

    Returns:
        List of integer user IDs. Invalid entries are ignored.
    """
    user_ids: list[int] = []
    for item in (raw_value or "").split(","):
        item = item.strip()
        if not item:
            continue
        if item.isdigit():
            user_ids.append(int(item))
    return user_ids


TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
ALLOWED_USER_IDS = _parse_allowed_users(os.getenv("ALLOWED_USERS", ""))

NSE_SUFFIX = ".NS"
BSE_SUFFIX = ".BO"
DEFAULT_EXCHANGE = os.getenv("DEFAULT_EXCHANGE", "NSE")
DEFAULT_PERIOD = "3mo"
DEFAULT_INTERVAL = os.getenv("DEFAULT_INTERVAL", "1d")
MAX_HISTORY_PERIOD = os.getenv("MAX_HISTORY_PERIOD", "6mo")
ALERT_CHECK_INTERVAL_MINUTES = int(os.getenv("ALERT_CHECK_INTERVAL_MINUTES", "30"))

RSI_PERIOD = 14
RSI_OVERSOLD = 35
RSI_OVERBOUGHT = 65
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
BB_PERIOD = 20
BB_STD = 2
EMA_SHORT = 20
EMA_MID = 50
EMA_LONG = 200
ADX_PERIOD = 14
ATR_PERIOD = 14
ATR_TARGET_MULTIPLIER = 2.0
ATR_STOPLOSS_MULTIPLIER = 1.5

STRONG_BUY_THRESHOLD = 4
BUY_THRESHOLD = 2
STRONG_SELL_THRESHOLD = -4
SELL_THRESHOLD = -2

INDIA_TIMEZONE = "Asia/Kolkata"
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 15
MARKET_CLOSE_HOUR = 15
MARKET_CLOSE_MINUTE = 30
