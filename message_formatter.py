"""Message formatting helpers for Telegram responses."""

from __future__ import annotations

from typing import Any


def _n(value: Any, digits: int = 2, prefix: str = "") -> str:
    """Format numeric values in human-readable style.

    Args:
        value: Numeric value.
        digits: Decimal digits.
        prefix: Optional prefix.

    Returns:
        Formatted text or N/A.
    """
    try:
        return f"{prefix}{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return "N/A"


def format_full_analysis(meta: dict, result: dict, news: list[dict]) -> str:
    """Format comprehensive stock analysis report text.

    Args:
        meta: Instrument metadata dictionary.
        result: Signal result dictionary.
        news: List of latest stock news items.

    Returns:
        Markdown-formatted full analysis message.
    """
    reasons = "\n".join(result.get("reasons", [])) or "• No strong reasons generated"
    warnings = "\n".join(result.get("warnings", [])) or "• None"
    emoji = {"POSITIVE": "🟢", "NEGATIVE": "🔴", "NEUTRAL": "⚪"}
    top_news = news[:3] if news else []
    news_text = "\n".join(
        f"{emoji.get(item.get('sentiment', 'NEUTRAL'), '⚪')} {item.get('title')}"
        for item in top_news
    ) or "• No recent headlines found"

    return f"""
═══════════════════════════════════
📊 *STOCK ANALYSIS REPORT*
═══════════════════════════════════
🏢 {meta.get('company_name', 'N/A')}
🔤 {meta.get('symbol', 'N/A')} | 🏦 {meta.get('exchange', 'N/A')}
🏭 Sector: {meta.get('sector', 'N/A')}
📅 {result.get('signal_date', 'N/A')} IST

───────────────────────────────────
💵 LIVE PRICE: ₹{_n(meta.get('live_price'))}
📈 52W High: ₹{_n(meta.get('fifty_two_week_high'))}
📉 52W Low:  ₹{_n(meta.get('fifty_two_week_low'))}
📊 P/E Ratio: {_n(meta.get('pe'))}
💰 Market Cap: {meta.get('market_cap', 'N/A')}
📦 Volume: {_n(meta.get('regular_market_volume'), 0)} ({_n(result.get('volume_ratio'))}x avg)
⚡ Beta: {_n(meta.get('beta'))}
───────────────────────────────────

🎯 SIGNAL: {result.get('signal', 'N/A')}
💪 Confidence: {result.get('confidence', 0)}%
📈 Trend: {result.get('trend', 'N/A')}
🕐 Market: {result.get('market_status', 'N/A')}

───────────────────────────────────
💰 TRADE PLAN
✅ Entry Price:  ₹{_n(result.get('entry_price'))}
🎯 Target Price: ₹{_n(result.get('target_price'))}
🛡️ Stop Loss:   ₹{_n(result.get('stop_loss'))}
⚖️ Risk:Reward = 1:{_n(result.get('risk_reward'))}
───────────────────────────────────

📊 INDICATORS
• RSI(14):           {_n(result.get('rsi'))}
• MACD:              {_n(result.get('macd'))}
• MACD Signal:       {_n(result.get('macd_signal'))}
• ADX:               {_n(result.get('adx'))}
• DI+/DI-:           {_n(result.get('di_plus'))} / {_n(result.get('di_minus'))}
• VWAP:              ₹{_n(result.get('vwap'))}
• EMA 20/50/200:     {_n(result.get('ema_20'))} / {_n(result.get('ema_50'))} / {_n(result.get('ema_200'))}
• BB Upper/Lower:    {_n(result.get('bb_upper'))} / {_n(result.get('bb_lower'))}
• ATR(14):           {_n(result.get('atr'))}
───────────────────────────────────

📋 ANALYSIS REASONS:
{reasons}

⚠️ WARNINGS:
{warnings}

📰 LATEST NEWS:
{news_text}

───────────────────────────────────
⚠️ Educational use only.
Not SEBI-registered investment advice.
═══════════════════════════════════
""".strip()


def format_quick_price(meta: dict) -> str:
    """Format quick stock price snapshot.

    Args:
        meta: Instrument metadata dictionary.

    Returns:
        Markdown-formatted quick-price message.
    """
    return (
        f"💰 *{meta.get('symbol', 'N/A')}* ({meta.get('exchange', 'N/A')})\n"
        f"Live: ₹{_n(meta.get('live_price'))}\n"
        f"Change: {_n(meta.get('change'))} ({_n(meta.get('change_percent'))}%)\n"
        f"52W High/Low: ₹{_n(meta.get('fifty_two_week_high'))} / ₹{_n(meta.get('fifty_two_week_low'))}\n\n"
        "⚠️ Educational use only."
    )


def format_global_market(data: str) -> str:
    """Wrap global market text with disclaimer.

    Args:
        data: Global market multiline text.

    Returns:
        Markdown string.
    """
    return f"{data}\n\n⚠️ Educational use only."


def format_error(symbol: str, error_msg: str) -> str:
    """Format user-friendly error message.

    Args:
        symbol: Requested symbol.
        error_msg: Underlying error message.

    Returns:
        Friendly error text.
    """
    return (
        f"❌ Could not process *{symbol.upper()}*.\n"
        f"Reason: {error_msg}\n"
        "Try NSE symbols like RELIANCE, INFY or BSE symbols like TCS.BO.\n\n"
        "⚠️ Educational use only."
    )
