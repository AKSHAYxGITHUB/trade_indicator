"""Main Telegram bot entrypoint for NSE/BSE stock analysis."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import pytz
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

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

# ---------------------------------------------------------------------------
# State constants for ConversationHandler
# ---------------------------------------------------------------------------
AWAITING_SYMBOL_ANALYZE = 1
AWAITING_SYMBOL_PRICE = 2
AWAITING_SYMBOL_NEWS = 3
AWAITING_SYMBOL_WATCH = 4
AWAITING_SYMBOL_COMPARE_A = 5
AWAITING_SYMBOL_COMPARE_B = 6

LAST_SEARCH: dict[int, str] = {}
COMPARE_BUFFER: dict[int, str] = {}

NIFTY20 = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "SBIN", "ITC", "LT", "KOTAKBANK", "BHARTIARTL",
    "HINDUNILVR", "AXISBANK", "BAJFINANCE", "ASIANPAINT", "MARUTI", "HCLTECH", "WIPRO", "NTPC", "TITAN", "ULTRACEMCO",
]


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _allowed(user_id: int) -> bool:
    """Check user access against optional whitelist."""
    return not ALLOWED_USER_IDS or user_id in ALLOWED_USER_IDS


def _main_keyboard() -> ReplyKeyboardMarkup:
    """Create the persistent reply keyboard."""
    rows = [
        ["📊 Analyze Stock", "💰 Quick Price"],
        ["📰 Stock News", "🌍 Global Markets"],
        ["⭐ My Watchlist", "📡 Screener"],
        ["📈 Nifty", "📉 Sensex", "🏦 BankNifty"],
        ["🕐 Market Hours", "ℹ️ Help"],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, input_field_placeholder="Type a symbol or choose an option...")


def _stock_action_buttons(symbol: str) -> InlineKeyboardMarkup:
    """Return inline action buttons for a given stock symbol."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Analyze Again", callback_data=f"analyze:{symbol}"),
            InlineKeyboardButton("💰 Quick Price", callback_data=f"price:{symbol}"),
        ],
        [
            InlineKeyboardButton("📰 Get News", callback_data=f"news:{symbol}"),
            InlineKeyboardButton("⭐ Add to Watchlist", callback_data=f"watch:{symbol}"),
        ],
        [
            InlineKeyboardButton("📊 Main Menu", callback_data="menu"),
        ],
    ])


def _index_buttons() -> InlineKeyboardMarkup:
    """Return inline buttons for index quick-access."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📈 Nifty 50", callback_data="index:NIFTY"),
            InlineKeyboardButton("📉 Sensex", callback_data="index:SENSEX"),
            InlineKeyboardButton("🏦 BankNifty", callback_data="index:BANKNIFTY"),
        ],
        [
            InlineKeyboardButton("🌍 Global Markets", callback_data="global"),
        ],
    ])


def _watchlist_buttons(symbols: list[str]) -> InlineKeyboardMarkup:
    """Return inline buttons to quickly analyze watchlist stocks."""
    buttons = []
    row = []
    for i, sym in enumerate(symbols):
        row.append(InlineKeyboardButton(f"📊 {sym}", callback_data=f"analyze:{sym}"))
        if len(row) == 2 or i == len(symbols) - 1:
            buttons.append(row)
            row = []
    buttons.append([InlineKeyboardButton("📊 Main Menu", callback_data="menu")])
    return InlineKeyboardMarkup(buttons)


# ---------------------------------------------------------------------------
# Core analysis helper
# ---------------------------------------------------------------------------

async def _analyze_symbol(symbol: str, chat_id: int, context: ContextTypes.DEFAULT_TYPE, reply_to_msg=None) -> None:
    """Analyze a symbol and send full report with action buttons."""
    clean, exchange = detect_exchange(symbol)
    err = None
    for attempt in range(2):
        df, meta, err = get_stock_data(clean, exchange, DEFAULT_PERIOD, DEFAULT_INTERVAL)
        if not err:
            break
        if attempt == 0:
            await asyncio.sleep(2)
    if err or df is None or meta is None:
        if reply_to_msg:
            await reply_to_msg.reply_text(format_error(symbol, err or "Unknown error"), parse_mode="Markdown")
        else:
            await context.bot.send_message(chat_id=chat_id, text=format_error(symbol, err or "Unknown error"), parse_mode="Markdown")
        return

    enriched = calculate_all_indicators(df)
    result = generate_signal(enriched, meta)
    news = get_stock_news(meta.get("company_name", clean), clean)
    message = format_full_analysis(meta, result, news)
    await context.bot.send_message(
        chat_id=chat_id,
        text=message,
        parse_mode="Markdown",
        reply_markup=_stock_action_buttons(symbol.upper()),
    )


# ---------------------------------------------------------------------------
# /start command
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    user_id = update.effective_user.id
    if not _allowed(user_id):
        await update.message.reply_text("Access Denied")
        return
    name = update.effective_user.first_name or "Trader"
    text = (
        f"👋 Welcome, *{name}*!\n\n"
        "I'm your *NSE/BSE Stock Indicator Bot*.\n\n"
        "I provide:\n"
        "• 📊 Full technical analysis (RSI, MACD, ADX, BB...)\n"
        "• 🎯 BUY / HOLD / EXIT signals with targets\n"
        "• 📰 Latest news with sentiment\n"
        "• ⭐ Watchlist alerts\n"
        "• 📡 NIFTY20 screener\n\n"
        "👇 Tap a button below or type a stock symbol (e.g. *RELIANCE*, *INFY*, *TCS*).\n\n"
        "⚠️ Educational use only."
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=_main_keyboard())


# ---------------------------------------------------------------------------
# /help command
# ---------------------------------------------------------------------------

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    msg = (
        "*📖 How to use this bot*\n\n"
        "*Quick Commands:*\n"
        "`/analyze RELIANCE` — Full analysis\n"
        "`/price INFY` — Live price\n"
        "`/nifty` `/sensex` `/banknifty` — Index data\n"
        "`/global` — Global market view\n"
        "`/news RELIANCE` — Top news\n"
        "`/watch RELIANCE` — Add to watchlist\n"
        "`/unwatch RELIANCE` — Remove from watchlist\n"
        "`/watchlist` — View watchlist\n"
        "`/screener` — NIFTY20 screener\n"
        "`/compare INFY TCS` — Side-by-side\n"
        "`/market` — Market status\n\n"
        "*Or:* Just type a symbol directly!\n\n"
        "*Indicators:* RSI, MACD, EMA, BB, ADX, VWAP, ATR, StochRSI, Patterns\n\n"
        "⚠️ Educational use only. Not SEBI-registered."
    )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=_main_keyboard())


# ---------------------------------------------------------------------------
# Conversation: Analyze Stock (button-triggered)
# ---------------------------------------------------------------------------

async def ask_symbol_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt user to enter a symbol for analysis."""
    await update.message.reply_text(
        "📊 *Which stock do you want to analyze?*\n\nType the symbol (e.g. RELIANCE, INFY, TCS.BO):",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return AWAITING_SYMBOL_ANALYZE


async def recv_symbol_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive the symbol and perform analysis."""
    symbol = update.message.text.strip().upper()
    user_id = update.effective_user.id
    LAST_SEARCH[user_id] = symbol
    await update.message.reply_text(f"🔍 Analyzing *{symbol}*... please wait.", parse_mode="Markdown", reply_markup=_main_keyboard())
    await _analyze_symbol(symbol, update.effective_chat.id, context, reply_to_msg=None)
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Conversation: Quick Price (button-triggered)
# ---------------------------------------------------------------------------

async def ask_symbol_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt user to enter a symbol for quick price."""
    await update.message.reply_text(
        "💰 *Which stock price do you want?*\n\nType the symbol (e.g. INFY, HDFCBANK):",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return AWAITING_SYMBOL_PRICE


async def recv_symbol_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive symbol and return quick price."""
    clean, exchange = detect_exchange(update.message.text.strip())
    _, meta, err = get_stock_data(clean, exchange, DEFAULT_PERIOD, DEFAULT_INTERVAL)
    if err or meta is None:
        await update.message.reply_text(format_error(clean, err or "Unknown"), parse_mode="Markdown", reply_markup=_main_keyboard())
    else:
        await update.message.reply_text(
            format_quick_price(meta),
            parse_mode="Markdown",
            reply_markup=_stock_action_buttons(clean),
        )
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Conversation: Stock News (button-triggered)
# ---------------------------------------------------------------------------

async def ask_symbol_news(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt user to enter a symbol for news."""
    await update.message.reply_text(
        "📰 *Which stock news do you want?*\n\nType the symbol (e.g. RELIANCE, SBIN):",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return AWAITING_SYMBOL_NEWS


async def recv_symbol_news(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive symbol and return top news."""
    query = update.message.text.strip().upper()
    articles = get_stock_news(query, query)
    lines = [f"📰 *{query} — Latest News*\n"]
    for item in articles[:5]:
        sentiment_emoji = {"POSITIVE": "🟢", "NEGATIVE": "🔴", "NEUTRAL": "⚪"}.get(item.get("sentiment", "NEUTRAL"), "⚪")
        lines.append(f"{sentiment_emoji} {item['title']}")
    lines.append("\n⚠️ Educational use only.")
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=_stock_action_buttons(query),
    )
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Conversation: Add to Watchlist (button-triggered)
# ---------------------------------------------------------------------------

async def ask_symbol_watch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt user to enter a symbol for watchlist."""
    await update.message.reply_text(
        "⭐ *Which stock do you want to add to your watchlist?*\n\nType the symbol:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return AWAITING_SYMBOL_WATCH


async def recv_symbol_watch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive symbol and add to watchlist."""
    symbol = update.message.text.strip().upper()
    add_to_watchlist(update.effective_user.id, symbol)
    await update.message.reply_text(
        f"✅ *{symbol}* added to your watchlist!\n\nYou'll get alerts when signal changes.\n\n⚠️ Educational use only.",
        parse_mode="Markdown",
        reply_markup=_main_keyboard(),
    )
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Cancel conversation
# ---------------------------------------------------------------------------

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel any active conversation."""
    await update.message.reply_text("Cancelled. Back to main menu.", reply_markup=_main_keyboard())
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Direct Commands (usable directly via /command SYMBOL)
# ---------------------------------------------------------------------------

async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /analyze command."""
    user_id = update.effective_user.id
    if not _allowed(user_id):
        await update.message.reply_text("Access Denied")
        return
    if not context.args:
        await update.message.reply_text("Usage: /analyze RELIANCE", reply_markup=_main_keyboard())
        return
    symbol = context.args[0].upper()
    LAST_SEARCH[user_id] = symbol
    await update.message.reply_text(f"🔍 Analyzing *{symbol}*...", parse_mode="Markdown")
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
    await update.message.reply_text(
        format_quick_price(meta),
        parse_mode="Markdown",
        reply_markup=_stock_action_buttons(clean),
    )


async def global_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /global command."""
    await update.message.reply_text(
        format_global_market(get_global_overview()),
        parse_mode="Markdown",
        reply_markup=_index_buttons(),
    )


async def news_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /news command."""
    query = " ".join(context.args).upper() if context.args else "NSE India"
    articles = get_stock_news(query, query)
    lines = [f"📰 *{query} — News*\n"]
    for item in articles[:5]:
        sentiment_emoji = {"POSITIVE": "🟢", "NEGATIVE": "🔴", "NEUTRAL": "⚪"}.get(item.get("sentiment", "NEUTRAL"), "⚪")
        lines.append(f"{sentiment_emoji} {item['title']}")
    lines.append("\n⚠️ Educational use only.")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def watch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /watch command."""
    if not context.args:
        await update.message.reply_text("Usage: /watch RELIANCE")
        return
    symbol = context.args[0].upper()
    add_to_watchlist(update.effective_user.id, symbol)
    await update.message.reply_text(
        f"✅ *{symbol}* added to your watchlist!\n\n⚠️ Educational use only.",
        parse_mode="Markdown",
    )


async def unwatch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /unwatch command."""
    if not context.args:
        await update.message.reply_text("Usage: /unwatch RELIANCE")
        return
    symbol = context.args[0].upper()
    remove_from_watchlist(update.effective_user.id, symbol)
    await update.message.reply_text(f"❌ *{symbol}* removed from watchlist.\n\n⚠️ Educational use only.", parse_mode="Markdown")


async def watchlist_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /watchlist command."""
    items = get_watchlist(update.effective_user.id)
    if not items:
        await update.message.reply_text(
            "⭐ Your watchlist is empty.\n\nAdd stocks using /watch RELIANCE or the Watchlist button.",
            reply_markup=_main_keyboard(),
        )
        return
    txt = "⭐ *Your Watchlist*\n\n" + "\n".join(f"• {s}" for s in items)
    txt += "\n\nTap a stock to analyze:"
    await update.message.reply_text(txt, parse_mode="Markdown", reply_markup=_watchlist_buttons(items))


async def screener(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /screener command."""
    await update.message.reply_text("📡 Running NIFTY20 screener... this takes ~30s.", reply_markup=_main_keyboard())
    buys, exits, holds = [], [], []
    for sym in NIFTY20:
        df, meta, err = get_stock_data(sym, "NSE", DEFAULT_PERIOD, DEFAULT_INTERVAL)
        if err or df is None or meta is None:
            continue
        result = generate_signal(calculate_all_indicators(df), meta)
        sig = result["signal"]
        entry = f"{sym} — RSI {result['rsi']:.0f}"
        if "STRONG BUY" in sig:
            buys.insert(0, f"🟢🟢 {entry}")
        elif "BUY" in sig:
            buys.append(f"🟢 {entry}")
        elif "STRONG SELL" in sig or "STRONG EXIT" in sig:
            exits.insert(0, f"🔴🔴 {entry}")
        elif "EXIT" in sig or "SELL" in sig:
            exits.append(f"🔴 {entry}")
        else:
            holds.append(f"⚪ {entry}")

    msg = "📡 *NIFTY20 Screener Results*\n\n"
    msg += "🟢 *BUY Signals:*\n" + ("\n".join(buys) if buys else "None") + "\n\n"
    msg += "⚪ *HOLD:*\n" + ("\n".join(holds) if holds else "None") + "\n\n"
    msg += "🔴 *EXIT Signals:*\n" + ("\n".join(exits) if exits else "None")
    msg += "\n\n⚠️ Educational use only."
    await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode="Markdown")


async def compare(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /compare command."""
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /compare INFY TCS")
        return
    outputs = [f"⚖️ *Stock Comparison*\n"]
    for symbol in context.args[:2]:
        clean, exchange = detect_exchange(symbol)
        df, meta, err = get_stock_data(clean, exchange, DEFAULT_PERIOD, DEFAULT_INTERVAL)
        if err or df is None or meta is None:
            outputs.append(f"❌ {symbol}: data unavailable")
            continue
        result = generate_signal(calculate_all_indicators(df), meta)
        outputs.append(
            f"*{symbol}*\n"
            f"Signal: {result['signal']}\n"
            f"RSI: {result['rsi']:.1f} | ADX: {result['adx']:.1f}\n"
            f"Price: ₹{meta['live_price']:,.2f} | Trend: {result['trend']}"
        )
    await update.message.reply_text("\n\n".join(outputs) + "\n\n⚠️ Educational use only.", parse_mode="Markdown")


async def market(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /market command."""
    tz = pytz.timezone(INDIA_TIMEZONE)
    now = datetime.now(tz)
    open_dt = now.replace(hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MINUTE, second=0, microsecond=0)
    close_dt = now.replace(hour=MARKET_CLOSE_HOUR, minute=MARKET_CLOSE_MINUTE, second=0, microsecond=0)

    if now.weekday() >= 5:
        days = 7 - now.weekday()
        next_open = (now + timedelta(days=days)).replace(hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MINUTE)
        status = "CLOSED (Weekend) 📅"
    elif open_dt <= now <= close_dt:
        next_open = close_dt
        status = "OPEN 🟢"
    elif now < open_dt:
        next_open = open_dt
        status = "CLOSED (Pre-Market) 🌙"
    else:
        next_open = (now + timedelta(days=1)).replace(hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MINUTE)
        status = "CLOSED (After-Hours) 🌆"

    msg = (
        f"🕐 *Market Status*\n\n"
        f"Status: *{status}*\n"
        f"Current Time: {now.strftime('%Y-%m-%d %H:%M:%S')} IST\n"
        f"Next Session: {next_open.strftime('%Y-%m-%d %H:%M')} IST\n\n"
        f"📅 Market Hours: Mon–Fri, 09:15–15:30 IST\n\n"
        f"⚠️ Educational use only."
    )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=_index_buttons())


async def index_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, index_name: str) -> None:
    """Handle benchmark index quick analysis command."""
    idx = get_index_data(index_name)
    if "error" in idx:
        await update.message.reply_text(f"❌ {idx['error']}")
        return
    direction = "▲" if idx["change"] >= 0 else "▼"
    color = "🟢" if idx["change"] >= 0 else "🔴"
    await update.message.reply_text(
        f"{color} *{index_name}*\n"
        f"Price: *{idx['price']:,.2f}* {direction} {idx['change']:+.2f} ({idx['change_pct']:+.2f}%)\n"
        f"High: {idx['high']:,.2f} | Low: {idx['low']:,.2f}\n\n"
        "⚠️ Educational use only.",
        parse_mode="Markdown",
        reply_markup=_index_buttons(),
    )


async def nifty(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await index_cmd(update, context, "NIFTY")


async def sensex(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await index_cmd(update, context, "SENSEX")


async def banknifty(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await index_cmd(update, context, "BANKNIFTY")


# ---------------------------------------------------------------------------
# Inline keyboard callback handler
# ---------------------------------------------------------------------------

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle all inline button presses."""
    query = update.callback_query
    await query.answer()
    data = query.data

    chat_id = query.message.chat_id

    if data.startswith("analyze:"):
        symbol = data.split(":", 1)[1]
        LAST_SEARCH[query.from_user.id] = symbol
        await query.message.reply_text(f"🔍 Analyzing *{symbol}*...", parse_mode="Markdown")
        await _analyze_symbol(symbol, chat_id, context)

    elif data.startswith("price:"):
        symbol = data.split(":", 1)[1]
        clean, exchange = detect_exchange(symbol)
        _, meta, err = get_stock_data(clean, exchange, DEFAULT_PERIOD, DEFAULT_INTERVAL)
        if err or meta is None:
            await query.message.reply_text(format_error(clean, err or "Unknown"), parse_mode="Markdown")
        else:
            await query.message.reply_text(
                format_quick_price(meta),
                parse_mode="Markdown",
                reply_markup=_stock_action_buttons(clean),
            )

    elif data.startswith("news:"):
        symbol = data.split(":", 1)[1]
        articles = get_stock_news(symbol, symbol)
        lines = [f"📰 *{symbol} — Latest News*\n"]
        for item in articles[:5]:
            sentiment_emoji = {"POSITIVE": "🟢", "NEGATIVE": "🔴", "NEUTRAL": "⚪"}.get(item.get("sentiment", "NEUTRAL"), "⚪")
            lines.append(f"{sentiment_emoji} {item['title']}")
        lines.append("\n⚠️ Educational use only.")
        await query.message.reply_text(
            "\n".join(lines),
            parse_mode="Markdown",
            reply_markup=_stock_action_buttons(symbol),
        )

    elif data.startswith("watch:"):
        symbol = data.split(":", 1)[1]
        add_to_watchlist(query.from_user.id, symbol)
        await query.message.reply_text(
            f"✅ *{symbol}* added to your watchlist!\n\n⚠️ Educational use only.",
            parse_mode="Markdown",
        )

    elif data.startswith("index:"):
        index_name = data.split(":", 1)[1]
        idx = get_index_data(index_name)
        if "error" in idx:
            await query.message.reply_text(f"❌ {idx['error']}")
        else:
            direction = "▲" if idx["change"] >= 0 else "▼"
            color = "🟢" if idx["change"] >= 0 else "🔴"
            await query.message.reply_text(
                f"{color} *{index_name}*\n"
                f"Price: *{idx['price']:,.2f}* {direction} {idx['change']:+.2f} ({idx['change_pct']:+.2f}%)\n"
                f"High: {idx['high']:,.2f} | Low: {idx['low']:,.2f}\n\n"
                "⚠️ Educational use only.",
                parse_mode="Markdown",
                reply_markup=_index_buttons(),
            )

    elif data == "global":
        await query.message.reply_text(
            format_global_market(get_global_overview()),
            parse_mode="Markdown",
            reply_markup=_index_buttons(),
        )

    elif data == "menu":
        await query.message.reply_text(
            "📊 Main Menu — choose an option or type a symbol:",
            reply_markup=_main_keyboard(),
        )


# ---------------------------------------------------------------------------
# Free-text handler
# ---------------------------------------------------------------------------

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle free-text messages for symbol analysis and keyboard actions."""
    text = (update.message.text or "").strip()
    lowered = text.lower()

    # Keyboard button shortcuts
    shortcuts = {
        "📊 analyze stock": "ASK_ANALYZE",
        "💰 quick price": "ASK_PRICE",
        "📰 stock news": "ASK_NEWS",
        "⭐ my watchlist": "WATCHLIST",
        "📡 screener": "SCREENER",
        "🌍 global markets": "GLOBAL",
        "📈 nifty": "NIFTY",
        "📉 sensex": "SENSEX",
        "🏦 banknifty": "BANKNIFTY",
        "🕐 market hours": "MARKET",
        "ℹ️ help": "HELP",
    }

    key = shortcuts.get(lowered)
    if key == "ASK_ANALYZE":
        await ask_symbol_analyze(update, context)
        context.user_data["_conv_state"] = AWAITING_SYMBOL_ANALYZE
        return
    elif key == "ASK_PRICE":
        await ask_symbol_price(update, context)
        context.user_data["_conv_state"] = AWAITING_SYMBOL_PRICE
        return
    elif key == "ASK_NEWS":
        await ask_symbol_news(update, context)
        context.user_data["_conv_state"] = AWAITING_SYMBOL_NEWS
        return
    elif key == "WATCHLIST":
        await watchlist_cmd(update, context)
        return
    elif key == "SCREENER":
        await screener(update, context)
        return
    elif key == "GLOBAL":
        await global_cmd(update, context)
        return
    elif key == "NIFTY":
        await nifty(update, context)
        return
    elif key == "SENSEX":
        await sensex(update, context)
        return
    elif key == "BANKNIFTY":
        await banknifty(update, context)
        return
    elif key == "MARKET":
        await market(update, context)
        return
    elif key == "HELP":
        await help_cmd(update, context)
        return

    # Check if we are in a conv state (waiting for symbol input)
    conv_state = context.user_data.get("_conv_state")
    if conv_state == AWAITING_SYMBOL_ANALYZE:
        context.user_data.pop("_conv_state", None)
        await recv_symbol_analyze(update, context)
        return
    elif conv_state == AWAITING_SYMBOL_PRICE:
        context.user_data.pop("_conv_state", None)
        await recv_symbol_price(update, context)
        return
    elif conv_state == AWAITING_SYMBOL_NEWS:
        context.user_data.pop("_conv_state", None)
        await recv_symbol_news(update, context)
        return
    elif conv_state == AWAITING_SYMBOL_WATCH:
        context.user_data.pop("_conv_state", None)
        await recv_symbol_watch(update, context)
        return

    # Default: treat as a symbol
    symbol = text.split()[-1].upper()
    LAST_SEARCH[update.effective_user.id] = symbol
    await update.message.reply_text(f"🔍 Analyzing *{symbol}*...", parse_mode="Markdown")
    await _analyze_symbol(symbol, update.effective_chat.id, context)


# ---------------------------------------------------------------------------
# Error handler
# ---------------------------------------------------------------------------

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log unhandled exceptions from telegram handlers."""
    LOGGER.exception("Unhandled Telegram error. Update=%s", update, exc_info=context.error)


# ---------------------------------------------------------------------------
# Scheduler hook
# ---------------------------------------------------------------------------

async def post_init(application: Application) -> None:
    """Start background tasks after the bot's event loop is officially running."""
    start_scheduler(application.bot)
    LOGGER.info("Scheduler integrated via post_init hook.")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Start Telegram bot polling service."""
    if not TELEGRAM_TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN is not set in environment.")

    # --- SSL FIX (Monkey-patch httpx for the Telegram client) ---
    import httpx
    _original_client_init = httpx.AsyncClient.__init__

    def _patched_client_init(self, *args, **kwargs):
        kwargs["verify"] = False
        _original_client_init(self, *args, **kwargs)

    httpx.AsyncClient.__init__ = _patched_client_init
    # ------------------------------------------------------------

    application = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()

    # Commands
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
    application.add_handler(CommandHandler("cancel", cancel))

    # Inline button callbacks
    application.add_handler(CallbackQueryHandler(button_callback))

    # Free-text handler (catches keyboard shortcuts + plain symbol input)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    application.add_error_handler(error_handler)

    LOGGER.info("Bot started successfully.")
    application.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
