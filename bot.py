"""Main Telegram bot entrypoint for NSE/BSE stock analysis."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import pytz
from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from config import (
    ALLOWED_USER_IDS,
    DEFAULT_INTERVAL,
    DEFAULT_PERIOD,
    INDIA_TIMEZONE,
    MARKET_CLOSE_HOUR,
    MARKET_CLOSE_MINUTE,
    MARKET_OPEN_HOUR,
    MARKET_OPEN_MINUTE,
    TELEGRAM_TOKEN,
)
from data_fetcher import detect_exchange, get_index_data, get_stock_data
from global_market import get_global_overview
from indicators import calculate_all_indicators
from logger import LOGGER
from message_formatter import format_error, format_full_analysis, format_global_market, format_quick_price
from news_fetcher import get_stock_news
from scheduler import add_to_watchlist, get_watchlist, remove_from_watchlist, start_scheduler
from signal_engine import generate_signal

LAST_SEARCH: dict[int, str] = {}
NIFTY20 = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "SBIN", "ITC", "LT", "KOTAKBANK", "BHARTIARTL",
    "HINDUNILVR", "AXISBANK", "BAJFINANCE", "ASIANPAINT", "MARUTI", "HCLTECH", "WIPRO", "NTPC", "TITAN", "ULTRACEMCO",
]


def _allowed(user_id: int) -> bool:
    """Check user access against optional whitelist."""
    return not ALLOWED_USER_IDS or user_id in ALLOWED_USER_IDS


def _keyboard() -> ReplyKeyboardMarkup:
    """Create bot reply keyboard."""
    rows = [
        ["📊 Analyze Stock", "💰 Quick Price"],
        ["📰 Market News", "🌍 Global Markets"],
        ["⭐ My Watchlist", "📡 Screener"],
        ["📈 Nifty", "📉 Sensex"],
        ["ℹ️ Help", "🕐 Market Hours"],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


async def _analyze_symbol(symbol: str, chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Analyze a symbol and send full report."""
    clean, exchange = detect_exchange(symbol)
    err = None
    for attempt in range(2):
        df, meta, err = get_stock_data(clean, exchange, DEFAULT_PERIOD, DEFAULT_INTERVAL)
        if not err:
            break
        if attempt == 0:
            await asyncio.sleep(1)
    if err or df is None or meta is None:
        await context.bot.send_message(chat_id=chat_id, text=format_error(symbol, err or "Unknown error"), parse_mode="Markdown")
        return

    enriched = calculate_all_indicators(df)
    result = generate_signal(enriched, meta)
    news = get_stock_news(meta.get("company_name", clean), clean)
    message = format_full_analysis(meta, result, news)
    await context.bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    user_id = update.effective_user.id
    if not _allowed(user_id):
        await update.message.reply_text("Access Denied")
        return
    text = (
        "Welcome to NSE/BSE Stock Indicator Bot!\n\n"
        "Use /analyze RELIANCE for full report or /price INFY for quick price.\n"
        "You can also just type a symbol directly.\n\n"
        "⚠️ Educational use only."
    )
    await update.message.reply_text(text, reply_markup=_keyboard())


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    msg = (
        "*Commands*\n"
        "/analyze {SYMBOL}\n/price {SYMBOL}\n/nifty\n/sensex\n/banknifty\n/global\n/news {SYMBOL}\n"
        "/watch {SYMBOL}\n/unwatch {SYMBOL}\n/watchlist\n/screener\n/compare {A} {B}\n/market\n\n"
        "Indicators: RSI, MACD, EMA, BB, ADX, VWAP, ATR, StochRSI, patterns.\n\n"
        "⚠️ Educational use only."
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /analyze command."""
    user_id = update.effective_user.id
    if not _allowed(user_id):
        await update.message.reply_text("Access Denied")
        return
    if not context.args:
        await update.message.reply_text("Usage: /analyze RELIANCE")
        return
    symbol = context.args[0].upper()
    LAST_SEARCH[user_id] = symbol
    await _analyze_symbol(symbol, update.effective_chat.id, context)


async def price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /price command."""
    if not context.args:
        await update.message.reply_text("Usage: /price INFY")
        return
    clean, exchange = detect_exchange(context.args[0])
    _, meta, err = get_stock_data(clean, exchange, DEFAULT_PERIOD, DEFAULT_INTERVAL)
    if err or meta is None:
        await update.message.reply_text(format_error(clean, err or "Unknown"), parse_mode="Markdown")
        return
    await update.message.reply_text(format_quick_price(meta), parse_mode="Markdown")


async def global_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /global command."""
    await update.message.reply_text(format_global_market(get_global_overview()), parse_mode="Markdown")


async def news_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /news command."""
    query = " ".join(context.args) if context.args else "NSE"
    articles = get_stock_news(query, query)
    lines = ["📰 *Latest News*", ""]
    for item in articles[:5]:
        lines.append(f"• {item['title']} ({item['sentiment']})")
    lines.append("\n⚠️ Educational use only.")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def watch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /watch command."""
    if not context.args:
        await update.message.reply_text("Usage: /watch RELIANCE")
        return
    add_to_watchlist(update.effective_user.id, context.args[0])
    await update.message.reply_text("Added to watchlist.\n\n⚠️ Educational use only.")


async def unwatch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /unwatch command."""
    if not context.args:
        await update.message.reply_text("Usage: /unwatch RELIANCE")
        return
    remove_from_watchlist(update.effective_user.id, context.args[0])
    await update.message.reply_text("Removed from watchlist.\n\n⚠️ Educational use only.")


async def watchlist_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /watchlist command."""
    items = get_watchlist(update.effective_user.id)
    txt = "⭐ Watchlist: " + (", ".join(items) if items else "No stocks added")
    await update.message.reply_text(f"{txt}\n\n⚠️ Educational use only.")


async def screener(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /screener command."""
    buys, exits = [], []
    for sym in NIFTY20:
        df, meta, err = get_stock_data(sym, "NSE", DEFAULT_PERIOD, DEFAULT_INTERVAL)
        if err or df is None or meta is None:
            continue
        result = generate_signal(calculate_all_indicators(df), meta)
        if "BUY" in result["signal"]:
            buys.append(f"{sym} ({result['signal']})")
        if "EXIT" in result["signal"] or "SELL" in result["signal"]:
            exits.append(f"{sym} ({result['signal']})")
    msg = "📡 *NIFTY20 Screener*\n\n🟢 BUY:\n" + ("\n".join(buys) if buys else "None")
    msg += "\n\n🔴 EXIT:\n" + ("\n".join(exits) if exits else "None")
    msg += "\n\n⚠️ Educational use only."
    await update.message.reply_text(msg, parse_mode="Markdown")


async def compare(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /compare command."""
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /compare INFY TCS")
        return
    outputs = []
    for symbol in context.args[:2]:
        clean, exchange = detect_exchange(symbol)
        df, meta, err = get_stock_data(clean, exchange, DEFAULT_PERIOD, DEFAULT_INTERVAL)
        if err or df is None or meta is None:
            outputs.append(f"{symbol}: error")
            continue
        result = generate_signal(calculate_all_indicators(df), meta)
        outputs.append(f"{symbol}: {result['signal']} | RSI {result['rsi']:.2f} | ADX {result['adx']:.2f}")
    await update.message.reply_text("\n".join(outputs) + "\n\n⚠️ Educational use only.")


async def market(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /market command."""
    tz = pytz.timezone(INDIA_TIMEZONE)
    now = datetime.now(tz)
    open_dt = now.replace(hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MINUTE, second=0, microsecond=0)
    close_dt = now.replace(hour=MARKET_CLOSE_HOUR, minute=MARKET_CLOSE_MINUTE, second=0, microsecond=0)

    if now.weekday() >= 5:
        days = 7 - now.weekday()
        next_open = (now + timedelta(days=days)).replace(hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MINUTE)
        status = "CLOSED (Weekend)"
    elif open_dt <= now <= close_dt:
        next_open = close_dt
        status = "OPEN"
    elif now < open_dt:
        next_open = open_dt
        status = "CLOSED"
    else:
        next_open = (now + timedelta(days=1)).replace(hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MINUTE)
        status = "CLOSED"
    await update.message.reply_text(
        f"🕐 Market is *{status}*.\nNext session: {next_open.strftime('%Y-%m-%d %H:%M:%S')} IST\n\n⚠️ Educational use only.",
        parse_mode="Markdown",
    )


async def index_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, index_name: str) -> None:
    """Handle benchmark index quick analysis command."""
    idx = get_index_data(index_name)
    if "error" in idx:
        await update.message.reply_text(f"❌ {idx['error']}")
        return
    await update.message.reply_text(
        f"{index_name}: {idx['price']:.2f} ({idx['change_pct']:+.2f}%)\n"
        f"High: {idx['high']:.2f} | Low: {idx['low']:.2f}\n\n"
        "⚠️ Educational use only."
    )


async def nifty(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /nifty command."""
    await index_cmd(update, context, "NIFTY")


async def sensex(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /sensex command."""
    await index_cmd(update, context, "SENSEX")


async def banknifty(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /banknifty command."""
    await index_cmd(update, context, "BANKNIFTY")


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle free-text messages for symbol analysis and keyboard actions."""
    text = (update.message.text or "").strip()
    lowered = text.lower()
    if lowered == "again":
        symbol = LAST_SEARCH.get(update.effective_user.id)
        if not symbol:
            await update.message.reply_text("No previous symbol found.")
            return
        await _analyze_symbol(symbol, update.effective_chat.id, context)
        return

    shortcuts = {
        "📈 nifty": "NIFTY",
        "📉 sensex": "SENSEX",
        "🌍 global markets": "GLOBAL",
        "ℹ️ help": "HELP",
        "🕐 market hours": "MARKET",
    }
    if lowered in shortcuts:
        key = shortcuts[lowered]
        if key == "NIFTY":
            await nifty(update, context)
            return
        if key == "SENSEX":
            await sensex(update, context)
            return
        if key == "GLOBAL":
            await global_cmd(update, context)
            return
        if key == "HELP":
            await help_cmd(update, context)
            return
        if key == "MARKET":
            await market(update, context)
            return

    symbol = text.split()[-1].upper()
    LAST_SEARCH[update.effective_user.id] = symbol
    await _analyze_symbol(symbol, update.effective_chat.id, context)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log unhandled exceptions from telegram handlers."""
    LOGGER.exception("Unhandled Telegram error. Update=%s", update, exc_info=context.error)


async def post_init(application: Application) -> None:
    """Start background tasks after the bot's event loop is officially running."""
    start_scheduler(application.bot)
    LOGGER.info("Scheduler integrated via post_init hook.")


def main() -> None:
    """Start Telegram bot polling service."""
    if not TELEGRAM_TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN is not set in environment.")

    # --- FIX: Force the underlying HTTP client to ignore SSL verification ---
    import httpx
    
    _original_client_init = httpx.AsyncClient.__init__
    
    def _patched_client_init(self, *args, **kwargs):
        kwargs['verify'] = False
        _original_client_init(self, *args, **kwargs)
        
    httpx.AsyncClient.__init__ = _patched_client_init
    # ----------------------------------------------------------------------

    # Build application using the standard builder and our post_init hook
    application = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("analyze", analyze))
    application.add_handler(CommandHandler("price", price))
    application.add_handler(CommandHandler("nifty", nifty))
    application.add_handler(CommandHandler("sensex", sensex))
    application.add_handler(CommandHandler("banknifty", banknifty))
    application.add_handler(CommandHandler("global", global_cmd))
    application.add_handler(CommandHandler("news", news_cmd))
    application.add_handler(CommandHandler("watch", watch))
    application.add_handler(CommandHandler("unwatch", unwatch))
    application.add_handler(CommandHandler("watchlist", watchlist_cmd))
    application.add_handler(CommandHandler("screener", screener))
    application.add_handler(CommandHandler("compare", compare))
    application.add_handler(CommandHandler("market", market))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    application.add_error_handler(error_handler)

    LOGGER.info("Bot started successfully.")
    
    # Run the bot until the user presses Ctrl-C
    application.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
