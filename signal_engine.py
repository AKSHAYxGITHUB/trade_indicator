"""Signal generation engine using multi-indicator scoring."""

from __future__ import annotations

from datetime import datetime, time

import pandas as pd
import pytz

from config import ATR_STOPLOSS_MULTIPLIER, ATR_TARGET_MULTIPLIER, INDIA_TIMEZONE, MARKET_CLOSE_HOUR, MARKET_CLOSE_MINUTE, MARKET_OPEN_HOUR, MARKET_OPEN_MINUTE


def _market_status(now_ist: datetime) -> str:
    """Check if Indian market is currently open.

    Args:
        now_ist: Current IST datetime.

    Returns:
        OPEN or CLOSED.
    """
    if now_ist.weekday() >= 5:
        return "CLOSED"
    open_time = time(MARKET_OPEN_HOUR, MARKET_OPEN_MINUTE)
    close_time = time(MARKET_CLOSE_HOUR, MARKET_CLOSE_MINUTE)
    return "OPEN" if open_time <= now_ist.time() <= close_time else "CLOSED"


def generate_signal(df: pd.DataFrame, meta: dict) -> dict:
    """Generate BUY/HOLD/EXIT signal from an enriched indicator dataframe.

    Args:
        df: Indicator-enriched dataframe.
        meta: Metadata dictionary for the instrument.

    Returns:
        Dictionary with signal details and trade plan.
    """
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest

    score = 0
    reasons: list[str] = []
    warnings: list[str] = []

    rsi = float(latest["RSI"])
    if rsi < 25:
        score += 3; reasons.append("🟢 Extremely Oversold — Strong BUY")
    elif rsi < 35:
        score += 2; reasons.append("🟢 Oversold — BUY opportunity")
    elif rsi < 45:
        score += 1; reasons.append("🟢 RSI Neutral-Bullish")
    elif rsi > 75:
        score -= 3; reasons.append("🔴 Extremely Overbought — Strong EXIT")
    elif rsi > 65:
        score -= 2; reasons.append("🟠 Overbought — Consider EXIT")
    elif rsi > 55:
        score -= 1; reasons.append("🟠 RSI Neutral-Bearish")

    if prev["MACD"] < prev["MACD_Signal"] and latest["MACD"] > latest["MACD_Signal"]:
        score += 3; reasons.append("🟢 MACD Bullish Crossover → Strong BUY")
    elif prev["MACD"] > prev["MACD_Signal"] and latest["MACD"] < latest["MACD_Signal"]:
        score -= 3; reasons.append("🔴 MACD Bearish Crossover → Strong SELL")
    elif latest["MACD"] > latest["MACD_Signal"]:
        score += 1; reasons.append("🟢 MACD above signal → Bullish bias")
    else:
        score -= 1; reasons.append("🟠 MACD below signal → Bearish bias")

    price = float(meta.get("live_price") or latest["Close"])
    if price <= latest["BB_Lower"]:
        score += 2; reasons.append("🟢 Price at lower band → Oversold BUY")
    if price >= latest["BB_Upper"]:
        score -= 2; reasons.append("🟠 Price at upper band → Overbought EXIT")
    if float(latest["BB_Width"]) < 1.5:
        warnings.append("⚠️ Low volatility — Breakout expected soon")

    ema20, ema50, ema200 = float(latest["EMA_20"]), float(latest["EMA_50"]), float(latest["EMA_200"])
    if price > ema20 > ema50 > ema200:
        score += 3; reasons.append("🟢 Perfect Bull Stack — Strong Uptrend BUY")
    elif price > ema20 > ema50:
        score += 2; reasons.append("🟢 Price above EMA20 & EMA50 — Uptrend")
    elif price < ema20 < ema50 < ema200:
        score -= 3; reasons.append("🔴 Perfect Bear Stack — Strong Downtrend EXIT")
    elif price < ema20 < ema50:
        score -= 2; reasons.append("🟠 Price below EMA20 & EMA50 — Downtrend")
    if ema50 > ema200:
        score += 1; reasons.append("🟢 Golden Cross confirmed — Long term BUY")
    elif ema50 < ema200:
        score -= 1; reasons.append("🟠 Death Cross confirmed — Long term EXIT")

    adx = float(latest["ADX"])
    di_plus = float(latest["DI_Plus"])
    di_minus = float(latest["DI_Minus"])
    if adx > 40 and di_plus > di_minus:
        score += 2; reasons.append("🟢 Very strong uptrend confirmed")
    elif adx > 25 and di_plus > di_minus:
        score += 1; reasons.append("🟢 Moderate uptrend confirmed")
    elif adx > 40 and di_minus > di_plus:
        score -= 2; reasons.append("🔴 Very strong downtrend confirmed")
    elif adx > 25 and di_minus > di_plus:
        score -= 1; reasons.append("🟠 Moderate downtrend confirmed")
    elif adx < 20:
        warnings.append("⚠️ Weak trend — Avoid momentum trades")

    vwap = float(latest["VWAP"])
    if price > vwap:
        score += 1; reasons.append("🟢 Price above VWAP — Bullish intraday")
    else:
        score -= 1; reasons.append("🟠 Price below VWAP — Bearish intraday")

    vol_ratio = float(latest["Vol_Ratio"]) if pd.notna(latest["Vol_Ratio"]) else 0.0
    price_rising = latest["Close"] > prev["Close"]
    if vol_ratio > 1.5 and price_rising:
        score += 1; reasons.append("🟢 High volume with price rise — BUY confirmed")
    elif vol_ratio > 1.5 and not price_rising:
        score -= 1; reasons.append("🟠 High volume with price fall — SELL confirmed")
    elif vol_ratio < 0.5:
        warnings.append("⚠️ Low volume — Signal may be unreliable")

    if latest["StochRSI_K"] < 20 and latest["StochRSI_D"] < 20:
        score += 1; reasons.append("🟢 StochRSI Oversold — Supporting BUY")
    elif latest["StochRSI_K"] > 80 and latest["StochRSI_D"] > 80:
        score -= 1; reasons.append("🟠 StochRSI Overbought — Supporting EXIT")

    if latest["Hammer"] == 1:
        score += 1; reasons.append("🟢 Hammer candle detected — Bullish reversal signal")
    if latest["Bull_Engulf"] == 1:
        score += 2; reasons.append("🟢 Bullish Engulfing — Strong reversal signal")
    if latest["Bear_Engulf"] == 1:
        score -= 2; reasons.append("🔴 Bearish Engulfing — Strong reversal signal")

    signal = "⚪ HOLD/NEUTRAL"; confidence = 50
    if score >= 6:
        signal, confidence = "🟢 STRONG BUY", 92
    elif score >= 4:
        signal, confidence = "🟢 BUY", 82
    elif score >= 2:
        signal, confidence = "🟡 WEAK BUY", 67
    elif score <= -6:
        signal, confidence = "🔴 STRONG EXIT", 92
    elif score <= -4:
        signal, confidence = "🔴 EXIT/SELL", 82
    elif score <= -2:
        signal, confidence = "🟠 WEAK EXIT", 67

    atr = float(latest["ATR"]) if pd.notna(latest["ATR"]) else 0.0
    if "BUY" in signal:
        target = price + (atr * ATR_TARGET_MULTIPLIER)
        stop = price - (atr * ATR_STOPLOSS_MULTIPLIER)
    elif "EXIT" in signal or "SELL" in signal:
        target = price - (atr * ATR_TARGET_MULTIPLIER)
        stop = price + atr
    else:
        target = price + atr
        stop = price - atr
    rr = abs((target - price) / (price - stop)) if price != stop else 0.0

    trend = "SIDEWAYS"
    if ema20 > ema50 > ema200:
        trend = "BULLISH"
    elif ema20 < ema50 < ema200:
        trend = "BEARISH"

    now_ist = datetime.now(pytz.timezone(INDIA_TIMEZONE))
    return {
        "signal": signal,
        "confidence": confidence,
        "score": int(score),
        "entry_price": float(price),
        "target_price": float(target),
        "stop_loss": float(stop),
        "risk_reward": float(rr),
        "rsi": rsi,
        "macd": float(latest["MACD"]),
        "macd_signal": float(latest["MACD_Signal"]),
        "adx": adx,
        "di_plus": di_plus,
        "di_minus": di_minus,
        "vwap": vwap,
        "ema_20": ema20,
        "ema_50": ema50,
        "ema_200": ema200,
        "bb_upper": float(latest["BB_Upper"]),
        "bb_lower": float(latest["BB_Lower"]),
        "atr": atr,
        "volume_ratio": vol_ratio,
        "reasons": reasons,
        "warnings": warnings,
        "signal_date": now_ist.strftime("%Y-%m-%d %H:%M:%S"),
        "market_status": _market_status(now_ist),
        "trend": trend,
        "timeframe": "Daily",
    }
