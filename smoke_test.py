import asyncio
import os
from data_fetcher import get_stock_data
from indicators import calculate_all_indicators
from signal_engine import generate_signal
from config import DEFAULT_PERIOD, DEFAULT_INTERVAL

import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
# Monkey-patch requests to default verify=False and include a User-Agent
_orig_get = requests.get
def patched_get(url, **kwargs):
    headers = kwargs.get("headers", {})
    if "User-Agent" not in headers:
        headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    kwargs["headers"] = headers
    kwargs["verify"] = False
    return _orig_get(url, **kwargs)

requests.get = patched_get

import pandas as pd
import numpy as np

async def main():
    print("Starting Mock Smoke Test...")
    symbol = "RELIANCE"
    
    # Create mock OHLCV data (300 days)
    num_rows = 300
    dates = pd.date_range(start="2023-01-01", periods=num_rows, freq="B")
    data = {
        "Open": np.linspace(100, 150, num_rows),
        "High": np.linspace(105, 155, num_rows),
        "Low": np.linspace(95, 145, num_rows),
        "Close": np.linspace(102, 152, num_rows),
        "Volume": np.random.randint(1000, 5000, num_rows)
    }
    df = pd.DataFrame(data, index=dates)
    meta = {
        "symbol": "RELIANCE",
        "company_name": "RELIANCE Mock",
        "live_price": 152.0
    }

    print("Calculating indicators...")
    try:
        enriched = calculate_all_indicators(df)
        print("Indicators calculated successfully!")
    except Exception as e:
        print(f"Error calculating indicators: {e}")
        return
    
    print("Generating signal...")
    try:
        result = generate_signal(enriched, meta)
        print("Signal generated successfully!")
    except Exception as e:
        print(f"Error generating signal: {e}")
        return
    
    print("\n--- TEST RESULT ---")
    print(f"SYMBOL: {symbol}")
    print(f"SIGNAL: {result['signal']}")
    print(f"RSI: {result['rsi']:.2f}")
    print(f"ADX: {result['adx']:.2f}")
    print(f"TREND: {result['trend']}")
    print("-------------------\n")
    print("Smoke test complete!")

if __name__ == "__main__":
    asyncio.run(main())
