"""Global market overview fetcher and formatter."""

from __future__ import annotations

from typing import Any

import yfinance as yf

from logger import LOGGER


def _fetch_quote(symbol: str) -> dict[str, Any]:
    """Fetch quote details from yfinance history.

    Args:
        symbol: yfinance instrument symbol.

    Returns:
        Dictionary with last price and change percentage.
    """
    hist = yf.Ticker(symbol).history(period="2d", interval="1d")
    if hist.empty:
        return {"price": None, "change_pct": None}
    latest = hist.iloc[-1]
    prev = hist.iloc[-2] if len(hist) > 1 else latest
    change_pct = ((latest["Close"] - prev["Close"]) / prev["Close"] * 100) if prev["Close"] else 0
    return {"price": float(latest["Close"]), "change_pct": float(change_pct)}


def get_global_overview() -> str:
    """Fetch and format global market snapshot text.

    Returns:
        Multiline global overview string.
    """
    instruments = [
        ("🇺🇸 S&P 500", "^GSPC", "index"),
        ("🇺🇸 Dow Jones", "^DJI", "index"),
        ("🇺🇸 NASDAQ", "^IXIC", "index"),
        ("🇮🇳 NIFTY 50", "^NSEI", "index"),
        ("🇮🇳 SENSEX", "^BSESN", "index"),
        ("🇮🇳 GIFT NIFTY", "NIFTY50.NSE", "index"),
        ("🛢️ Crude Oil", "CL=F", "usd_bbl"),
        ("🥇 Gold", "GC=F", "usd_oz"),
        ("💵 USD/INR", "INR=X", "inr"),
        ("💲 DXY", "DX-Y.NYB", "index"),
    ]
    lines = ["🌍 *Global Market Overview*", ""]
    for label, symbol, kind in instruments:
        try:
            data = _fetch_quote(symbol)
            price = data["price"]
            change_pct = data["change_pct"]
            if price is None:
                lines.append(f"{label}: N/A")
                continue
            if kind == "inr":
                lines.append(f"{label}: ₹{price:,.2f}")
            elif kind == "usd_bbl":
                arrow = "▲" if (change_pct or 0) >= 0 else "▼"
                lines.append(f"{label}: ${price:,.2f}/bbl ({arrow} {change_pct:+.2f}%)")
            elif kind == "usd_oz":
                arrow = "▲" if (change_pct or 0) >= 0 else "▼"
                lines.append(f"{label}: ${price:,.2f}/oz ({arrow} {change_pct:+.2f}%)")
            else:
                arrow = "▲" if (change_pct or 0) >= 0 else "▼"
                lines.append(f"{label}: {price:,.2f} ({arrow} {change_pct:+.2f}%)")
        except Exception:
            LOGGER.exception("Failed global quote for %s", symbol)
            lines.append(f"{label}: N/A")
    return "\n".join(lines)
