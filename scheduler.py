"""APScheduler-based watchlist scanner and market brief jobs."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from config import ALERT_CHECK_INTERVAL_MINUTES, DEFAULT_INTERVAL, DEFAULT_PERIOD, INDIA_TIMEZONE
from data_fetcher import detect_exchange, get_stock_data
from global_market import get_global_overview
from indicators import calculate_all_indicators
from logger import LOGGER
from message_formatter import format_full_analysis, format_global_market
from news_fetcher import get_stock_news
from signal_engine import generate_signal

WATCHLIST: dict[int, set[str]] = defaultdict(set)
LAST_SIGNAL: dict[tuple[int, str], str] = {}


def add_to_watchlist(user_id: int, symbol: str) -> None:
    """Add symbol to user's watchlist.

    Args:
        user_id: Telegram user ID.
        symbol: Stock symbol.

    Returns:
        None.
    """
    WATCHLIST[user_id].add(symbol.upper())


def remove_from_watchlist(user_id: int, symbol: str) -> None:
    """Remove symbol from user's watchlist.

    Args:
        user_id: Telegram user ID.
        symbol: Stock symbol.

    Returns:
        None.
    """
    WATCHLIST[user_id].discard(symbol.upper())


def get_watchlist(user_id: int) -> list[str]:
    """Return user's watchlist symbols.

    Args:
        user_id: Telegram user ID.

    Returns:
        Sorted watchlist list.
    """
    return sorted(WATCHLIST.get(user_id, set()))


async def check_watchlist_signals(bot: Any) -> None:
    """Scan user watchlists and send alert on new BUY/EXIT signals.

    Args:
        bot: Telegram bot instance.

    Returns:
        None.
    """
    for user_id, symbols in WATCHLIST.items():
        for symbol in symbols:
            clean, exchange = detect_exchange(symbol)
            df, meta, err = get_stock_data(clean, exchange, DEFAULT_PERIOD, DEFAULT_INTERVAL)
            if err or df is None or meta is None:
                continue
            enriched = calculate_all_indicators(df)
            result = generate_signal(enriched, meta)
            signal = result["signal"]
            key = (user_id, symbol)
            if signal != LAST_SIGNAL.get(key) and ("BUY" in signal or "EXIT" in signal or "SELL" in signal):
                news = get_stock_news(meta.get("company_name", clean), clean)
                msg = format_full_analysis(meta, result, news)
                await bot.send_message(
                    chat_id=user_id,
                    text=f"📡 *Watchlist Alert*\n\n{msg}",
                    parse_mode="Markdown",
                )
                LAST_SIGNAL[key] = signal


async def send_morning_brief(bot: Any) -> None:
    """Send morning global market brief.

    Args:
        bot: Telegram bot instance.

    Returns:
        None.
    """
    msg = format_global_market(get_global_overview())
    for user_id in WATCHLIST:
        await bot.send_message(chat_id=user_id, text=f"🌅 *Morning Brief*\n\n{msg}", parse_mode="Markdown")


async def send_evening_summary(bot: Any) -> None:
    """Send evening wrap summary.

    Args:
        bot: Telegram bot instance.

    Returns:
        None.
    """
    summary = "🌆 *Evening Market Summary*\nGlobal cues and watchlist snapshots complete.\n\n⚠️ Educational use only."
    for user_id in WATCHLIST:
        await bot.send_message(chat_id=user_id, text=summary, parse_mode="Markdown")


def start_scheduler(bot: Any) -> AsyncIOScheduler:
    """Create and start APScheduler jobs.

    Args:
        bot: Telegram bot instance.

    Returns:
        Started AsyncIOScheduler.
    """
    tz = pytz.timezone(INDIA_TIMEZONE)
    scheduler = AsyncIOScheduler(timezone=tz)

    scheduler.add_job(
        check_watchlist_signals,
        trigger=CronTrigger(day_of_week="mon-fri", hour="9-15", minute=f"*/{ALERT_CHECK_INTERVAL_MINUTES}", timezone=tz),
        kwargs={"bot": bot},
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(send_morning_brief, CronTrigger(day_of_week="mon-fri", hour=9, minute=0, timezone=tz), kwargs={"bot": bot})
    scheduler.add_job(send_evening_summary, CronTrigger(day_of_week="mon-fri", hour=15, minute=35, timezone=tz), kwargs={"bot": bot})

    scheduler.start()
    LOGGER.info("Scheduler started successfully.")
    return scheduler
