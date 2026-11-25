"""Compare recent feature values with the stored history (population stability index).

Exit code 1 when a feature moved a lot, so a scheduled run shows up as failed. A drift alarm is a
reason to look at the model, not a reason to retrain on the test period.
"""
import sys
from pathlib import Path

import ccxt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.ml.features import FEATURE_COLUMNS, make_features  # noqa: E402

RAW = Path(__file__).resolve().parents[2] / "ml_engine" / "data" / "raw"
COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]
ALERT = 0.25  # common rule of thumb for a large shift


def psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    edges = np.quantile(expected, np.linspace(0, 1, bins + 1))[1:-1]
    e = np.bincount(np.digitize(expected, edges), minlength=bins) / len(expected)
    a = np.bincount(np.digitize(actual, edges), minlength=bins) / len(actual)
    e, a = np.clip(e, 1e-4, None), np.clip(a, 1e-4, None)
    return float(np.sum((a - e) * np.log(a / e)))


def main() -> int:
    exchange = ccxt.binance({"enableRateLimit": True, "options": {"fetchMarkets": {"types": ["spot"]}}})
    # Binance's public data host: the main one refuses US addresses such as GitHub's runners.
    exchange.urls["api"]["public"] = "https://data-api.binance.vision/api/v3"
    alarms = 0
    for coin in ("BTC", "ETH", "SOL", "DOGE"):
        history = pd.read_csv(RAW / f"{coin.lower()}_usdt_1h.csv")
        rows = exchange.fetch_ohlcv(f"{coin}/USDT", "1h", limit=1000)
        recent = pd.DataFrame(rows[:-1], columns=COLUMNS)
        old, new = make_features(history), make_features(recent)
        for name in FEATURE_COLUMNS:
            value = psi(old[name].to_numpy(), new[name].to_numpy())
            alarm = value > ALERT
            alarms += alarm
            print(f"{coin:5s} {name:16s} psi={value:.3f}{'  <- DRIFT' if alarm else ''}")
    return 1 if alarms else 0


if __name__ == "__main__":
    sys.exit(main())
