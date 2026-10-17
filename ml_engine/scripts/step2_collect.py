import time

import ccxt
import pandas as pd

import json
from datetime import datetime, timezone



SYMBOL = "BTC/USDT"
TIMEFRAME = "1h"
DAYS = 730
PAGE_LIMIT = 1000
MAX_RETRIES = 3


def fetch_page(exchange, since_ms):
    for attempt in range(1, MAX_RETRIES +1):
        try:
            return exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, since=since_ms, limit=PAGE_LIMIT)
        except ccxt.NetworkError as err:
            if attempt == MAX_RETRIES:
                raise
            wait = 2 ** attempt
            print(f"Attempt {attempt} failed ({err}). Retrying in {wait}s...")
            time.sleep(wait)



def fetch_history(exchange):
    candle_ms = exchange.parse_timeframe(TIMEFRAME) * 1000
    now_ms = exchange.milliseconds()
    since_ms = now_ms - DAYS * 24 *60 * 60 *1000


    rows = []
    while since_ms < now_ms:
        page = fetch_page(exchange, since_ms)
        if not page:
            break
        rows.extend(page)
        since_ms = page[-1][0] + candle_ms
        print(f"Fetched{len(page)}candle, total so far: {len(rows)}")


    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df = df[df["timestamp"] + candle_ms <= now_ms]
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True) 
    return df.reset_index(drop=True)


if __name__ == "__main__":
    exchange = ccxt.binance({"enableRateLimit": True, "timeout": 10000})
    df = fetch_history(exchange)

    print(f"Rows: {len(df)}")
    print(f"From {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")
    print(f"Duplicate timestamps: {df['timestamp'].duplicated().sum()}")

    df.to_csv("data/raw/btc_usdt_1h.csv", index=False)
    print("Saved to data/raw/btc_usdt_1h.csv")


        
    meta = {
        "source": "binance via ccxt",
        "symbol": SYMBOL,
        "timeframe": TIMEFRAME,
        "rows": len(df),
        "first_candle_utc": str(df["timestamp"].iloc[0]),
        "last_candle_utc": str(df["timestamp"].iloc[-1]),
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    with open("data/raw/btc_usdt_1h.meta.json", "w") as f:
        json.dump(meta, f, indent=2)
    print("Saved metadata")

