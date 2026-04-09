"""Market data fetching utilities for NSE/BSE symbols and key indices."""

from __future__ import annotations

import requests
from typing import Any

import yfinance as yf

from config import BSE_SUFFIX, DEFAULT_EXCHANGE, NSE_SUFFIX
from logger import LOGGER

# ---------------------------------------------------------------------------
# Patch requests session used by yfinance to avoid 429 rate-limit errors
# ---------------------------------------------------------------------------
_YF_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}


def _make_yf_ticker(symbol: str) -> yf.Ticker:
    """Create a yfinance Ticker with a patched session to avoid 429 errors."""
    session = requests.Session()
    session.headers.update(_YF_HEADERS)
    session.verify = False
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except Exception:
        pass
    return yf.Ticker(symbol, session=session)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def detect_exchange(symbol: str) -> tuple[str, str]:
    """Detect stock exchange from symbol suffix.

    Args:
        symbol: Input symbol possibly ending with .NS or .BO.

    Returns:
        Tuple of (clean_symbol, exchange).
    """
    clean_symbol = symbol.strip().upper()
    if clean_symbol.endswith(BSE_SUFFIX):
        return clean_symbol[:-3], "BSE"
    if clean_symbol.endswith(NSE_SUFFIX):
        return clean_symbol[:-3], "NSE"
    return clean_symbol, DEFAULT_EXCHANGE


def get_ticker_symbol(symbol: str, exchange: str) -> str:
    """Build yfinance ticker symbol using exchange.

    Args:
        symbol: Exchange-agnostic stock symbol.
        exchange: "NSE" or "BSE".

    Returns:
        Full ticker symbol for yfinance.
    """
    normalized = symbol.strip().upper()
    if exchange.upper() == "BSE":
        return f"{normalized}{BSE_SUFFIX}"
    return f"{normalized}{NSE_SUFFIX}"


def format_market_cap(value: Any) -> str:
    """Format market cap to Indian units (Cr/Lakh Cr).

    Args:
        value: Raw market cap value in INR.

    Returns:
        Formatted market cap string.
    """
    try:
        cap = float(value)
    except (TypeError, ValueError):
        return "N/A"

    crore = cap / 1e7
    if cap > 1e10:
        return f"{crore / 1e5:.2f} Lakh Cr"
    return f"{crore:.2f} Cr"


def get_stock_data(
    symbol: str,
    exchange: str,
    period: str,
    interval: str,
) -> tuple[Any, dict[str, Any] | None, str | None]:
    """Fetch historical and meta information for a stock.

    Args:
        symbol: Clean symbol name.
        exchange: NSE or BSE.
        period: yfinance history period.
        interval: yfinance history interval.

    Returns:
        Tuple of (dataframe, metadata, error_message).
    """
    try:
        ticker_symbol = get_ticker_symbol(symbol, exchange)
        ticker = _make_yf_ticker(ticker_symbol)
        df = ticker.history(period=period, interval=interval, auto_adjust=False)
        if df is None or df.empty:
            return None, None, f"No historical data found for {ticker_symbol}."

        info = ticker.info or {}
        current_price = info.get("currentPrice") or info.get("regularMarketPrice") or float(df["Close"].iloc[-1])
        metadata = {
            "symbol": symbol.upper(),
            "exchange": exchange.upper(),
            "ticker": ticker_symbol,
            "company_name": info.get("longName") or symbol.upper(),
            "sector": info.get("sector") or "N/A",
            "live_price": current_price,
            "market_cap": format_market_cap(info.get("marketCap")),
            "pe": info.get("trailingPE"),
            "dividend_yield": info.get("dividendYield"),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
            "average_volume": info.get("averageVolume"),
            "regular_market_volume": info.get("regularMarketVolume"),
            "beta": info.get("beta"),
            "change": info.get("regularMarketChange"),
            "change_percent": info.get("regularMarketChangePercent"),
        }
        return df, metadata, None
    except Exception as exc:  # pylint: disable=broad-except
        LOGGER.exception("Failed to fetch stock data for %s", symbol)
        return None, None, f"Data fetch error: {exc}"


def get_index_data(index: str) -> dict[str, Any]:
    """Fetch key index metrics for Indian benchmark indices.

    Args:
        index: One of NIFTY, SENSEX, BANKNIFTY.

    Returns:
        Dictionary with index price and session stats.
    """
    mapping = {
        "NIFTY": "^NSEI",
        "SENSEX": "^BSESN",
        "BANKNIFTY": "^NSEBANK",
    }
    symbol = mapping.get(index.upper())
    if not symbol:
        return {"error": f"Unsupported index '{index}'."}

    try:
        ticker = _make_yf_ticker(symbol)
        hist = ticker.history(period="2d", interval="1d")
        if hist.empty:
            return {"error": f"No data for {index}."}

        latest = hist.iloc[-1]
        prev_close = hist.iloc[-2]["Close"] if len(hist) > 1 else latest["Open"]
        change = float(latest["Close"] - prev_close)
        change_pct = (change / prev_close * 100) if prev_close else 0.0
        return {
            "index": index.upper(),
            "symbol": symbol,
            "price": float(latest["Close"]),
            "change": change,
            "change_pct": change_pct,
            "high": float(latest["High"]),
            "low": float(latest["Low"]),
        }
    except Exception as exc:  # pylint: disable=broad-except
        LOGGER.exception("Index data fetch failed for %s", index)
        return {"error": str(exc)}
