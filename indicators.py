"""Technical indicator calculation helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pandas_ta_classic as ta

from config import ADX_PERIOD, ATR_PERIOD, BB_PERIOD, BB_STD, EMA_LONG, EMA_MID, EMA_SHORT, MACD_FAST, MACD_SIGNAL, MACD_SLOW, RSI_PERIOD


def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate and append all required indicators to the dataframe.

    Args:
        df: OHLCV dataframe from yfinance.

    Returns:
        Dataframe enriched with indicators and pattern columns.
    """
    data = df.copy()

    data["RSI"] = ta.rsi(data["Close"], length=RSI_PERIOD)

    macd = ta.macd(data["Close"], fast=MACD_FAST, slow=MACD_SLOW, signal=MACD_SIGNAL)
    data["MACD"] = macd.iloc[:, 0]
    data["MACD_Signal"] = macd.iloc[:, 1]
    data["MACD_Hist"] = macd.iloc[:, 2]

    bbands = ta.bbands(data["Close"], length=BB_PERIOD, std=BB_STD)
    data["BB_Lower"] = bbands.iloc[:, 0]
    data["BB_Middle"] = bbands.iloc[:, 1]
    data["BB_Upper"] = bbands.iloc[:, 2]
    data["BB_Width"] = (data["BB_Upper"] - data["BB_Lower"]) / data["BB_Middle"] * 100

    data["EMA_20"] = ta.ema(data["Close"], length=EMA_SHORT)
    data["EMA_50"] = ta.ema(data["Close"], length=EMA_MID)
    data["EMA_200"] = ta.ema(data["Close"], length=EMA_LONG)
    data["SMA_50"] = ta.sma(data["Close"], length=50)
    data["SMA_200"] = ta.sma(data["Close"], length=200)

    adx = ta.adx(data["High"], data["Low"], data["Close"], length=ADX_PERIOD)
    data["ADX"] = adx.iloc[:, 0]
    data["DI_Plus"] = adx.iloc[:, 1]
    data["DI_Minus"] = adx.iloc[:, 2]

    try:
        data["VWAP"] = ta.vwap(data["High"], data["Low"], data["Close"], data["Volume"])
    except Exception:
        data["VWAP"] = (data["Close"] * data["Volume"]).cumsum() / data["Volume"].replace(0, np.nan).cumsum()

    data["ATR"] = ta.atr(data["High"], data["Low"], data["Close"], length=ATR_PERIOD)

    stoch_rsi = ta.stochrsi(data["Close"], length=14)
    data["StochRSI_K"] = stoch_rsi.iloc[:, 0]
    data["StochRSI_D"] = stoch_rsi.iloc[:, 1]

    data["Vol_SMA20"] = ta.sma(data["Volume"], length=20)
    data["Vol_Ratio"] = data["Volume"] / data["Vol_SMA20"].replace(0, np.nan)

    body = (data["Close"] - data["Open"]).abs()
    range_total = (data["High"] - data["Low"]).replace(0, np.nan)
    lower_shadow = np.minimum(data["Open"], data["Close"]) - data["Low"]
    upper_shadow = data["High"] - np.maximum(data["Open"], data["Close"])

    data["Doji"] = ((body / range_total) < 0.1).fillna(False).astype(int)
    data["Hammer"] = (((lower_shadow > 2 * body) & (upper_shadow < body)).fillna(False)).astype(int)

    prev_open = data["Open"].shift(1)
    prev_close = data["Close"].shift(1)
    data["Bull_Engulf"] = (
        ((prev_close < prev_open) & (data["Close"] > data["Open"]) & (data["Open"] < prev_close) & (data["Close"] > prev_open))
        .fillna(False)
        .astype(int)
    )
    data["Bear_Engulf"] = (
        ((prev_close > prev_open) & (data["Close"] < data["Open"]) & (data["Open"] > prev_close) & (data["Close"] < prev_open))
        .fillna(False)
        .astype(int)
    )

    return data
