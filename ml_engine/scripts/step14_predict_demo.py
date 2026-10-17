import json
import tempfile
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import ccxt
import pandas as pd

from inference import PredictionEngine, PredictionError

MODEL_PATH = "artifacts/btc_usdt_1h_rf.joblib"


def fetch_recent(limit=500):
    exchange = ccxt.binance({"enableRateLimit": True, "timeout": 10000})
    raw = exchange.fetch_ohlcv("BTC/USDT", "1h", limit=limit)
    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df


def expect_error(title, action):
    try:
        action()
        print(f"{title} -> NO ERROR (unexpected)")
    except PredictionError as err:
        print(f"{title} -> {type(err).__name__}: {err}")


engine = PredictionEngine.load(MODEL_PATH)
candles = fetch_recent()
result = engine.predict(candles)
print(json.dumps(asdict(result), indent=2))

print("\n--- Failure modes ---")
expect_error("short history", lambda: engine.predict(candles.tail(50)))
expect_error("missing column", lambda: engine.predict(candles.drop(columns=["volume"])))
expect_error(
    "stale data",
    lambda: engine.predict(candles, now=datetime.now(timezone.utc) + timedelta(hours=10)),
)
expect_error("missing model", lambda: PredictionEngine.load("artifacts/does_not_exist.joblib"))

with tempfile.TemporaryDirectory() as folder:
    bad_file = Path(folder) / "bad.joblib"
    bad_file.write_bytes(b"this is not a model")
    expect_error("corrupted model", lambda: PredictionEngine.load(bad_file))
