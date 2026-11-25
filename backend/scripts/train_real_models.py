"""Train ETH, SOL and DOGE models on real Binance hourly candles.

Same recipe as the BTC model (ml_engine/scripts/step12_final.py): same features, labels,
chronological 85/15 split and fixed hyperparameters. Nothing is tuned, and the test set is
only used for the final report. Run from backend/:  python scripts/train_real_models.py
"""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

import ccxt
import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.ml.features import FEATURE_COLUMNS, FEATURE_VERSION, make_features
from app.ml.validation import validate

SYMBOLS = ["ETH/USDT", "SOL/USDT", "DOGE/USDT"]
TIMEFRAME = "1h"
DAYS = 730
HORIZON = 3
THRESHOLD = 0.003
WARMUP_ROWS = 100
DEV_FRACTION = 0.85
CLASSES = ["DOWN", "SIDEWAYS", "UP"]
ARTIFACTS_DIR = BACKEND / "artifacts"
RAW_DIR = BACKEND.parent / "ml_engine" / "data" / "raw"
MAX_RETRIES = 5


def fetch_page(exchange, symbol, since_ms):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return exchange.fetch_ohlcv(symbol, TIMEFRAME, since=since_ms, limit=1000)
        except ccxt.NetworkError:
            if attempt == MAX_RETRIES:
                raise
            time.sleep(2**attempt)


def fetch_history(exchange, symbol):
    candle_ms = exchange.parse_timeframe(TIMEFRAME) * 1000
    now_ms = exchange.milliseconds()
    since_ms = now_ms - DAYS * 24 * 60 * 60 * 1000
    rows = []
    while since_ms < now_ms:
        page = fetch_page(exchange, symbol, since_ms)
        if not page:
            break
        rows.extend(page)
        since_ms = page[-1][0] + candle_ms
    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df = df[df["timestamp"] + candle_ms <= now_ms]  # closed candles only
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df.reset_index(drop=True)


def build_dataset(df):
    features = make_features(df)
    features = features[features.index >= WARMUP_ROWS]
    forward = df["close"].shift(-HORIZON) / df["close"] - 1
    labels = np.select([forward > THRESHOLD, forward < -THRESHOLD], ["UP", "DOWN"], default="SIDEWAYS")
    target = pd.DataFrame({"timestamp": df["timestamp"], "label": labels})[forward.notna()]
    return features.merge(target, on="timestamp")


def evaluate(model, X, y):
    pred = model.predict(X)
    actual = y.to_numpy()
    moved = np.isin(actual, ["UP", "DOWN"]) & np.isin(pred, ["UP", "DOWN"])
    return {
        "accuracy": float(accuracy_score(actual, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(actual, pred)),
        "macro_f1": float(f1_score(actual, pred, average="macro", zero_division=0)),
        "directional_hit_rate": float((pred[moved] == actual[moved]).mean()) if moved.any() else None,
        "confusion_matrix_rows_true_cols_pred": confusion_matrix(actual, pred, labels=CLASSES).tolist(),
    }


def train(exchange, symbol):
    slug = f"{symbol.replace('/', '_').lower()}_{TIMEFRAME}"
    df, problems = validate(fetch_history(exchange, symbol), min_rows=DAYS * 24 - 48)
    if problems:
        raise ValueError(f"{symbol}: {problems}")

    df.to_csv(RAW_DIR / f"{slug}.csv", index=False)
    meta = {
        "source": "binance via ccxt",
        "symbol": symbol,
        "timeframe": TIMEFRAME,
        "rows": len(df),
        "first_candle_utc": str(df["timestamp"].iloc[0]),
        "last_candle_utc": str(df["timestamp"].iloc[-1]),
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (RAW_DIR / f"{slug}.meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    data = build_dataset(df)
    dev_end = int(len(data) * DEV_FRACTION)
    train_set = data.iloc[: dev_end - HORIZON]  # gap: training labels must not see the test period
    test = data.iloc[dev_end:]

    models = {
        "random_forest": RandomForestClassifier(
            n_estimators=300, max_depth=5, min_samples_leaf=50,
            class_weight="balanced_subsample", random_state=42, n_jobs=-1,
        ),
        "logistic_regression": make_pipeline(
            StandardScaler(), LogisticRegression(class_weight="balanced", max_iter=1000)
        ),
        "naive_most_frequent": DummyClassifier(strategy="most_frequent"),
    }
    report = {}
    for name, model in models.items():
        model.fit(train_set[FEATURE_COLUMNS], train_set["label"])
        report[name] = evaluate(model, test[FEATURE_COLUMNS], test["label"])

    chosen = models["random_forest"]
    metadata = {
        "symbol": symbol,
        "timeframe": TIMEFRAME,
        "horizon_candles": HORIZON,
        "threshold": THRESHOLD,
        "feature_version": FEATURE_VERSION,
        "feature_columns": FEATURE_COLUMNS,
        "classes": [str(c) for c in chosen.classes_],
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "train_period": [str(train_set["timestamp"].iloc[0]), str(train_set["timestamp"].iloc[-1])],
        "sklearn_version": sklearn.__version__,
        "data_source": "binance via ccxt",
    }
    joblib.dump({"model": chosen, "metadata": metadata}, ARTIFACTS_DIR / f"{slug}_rf.joblib")
    metrics = {
        "candidate_model": "random_forest",
        "test_period": [str(test["timestamp"].iloc[0]), str(test["timestamp"].iloc[-1])],
        "test_rows": len(test),
        "test_class_distribution": {k: int(v) for k, v in test["label"].value_counts().items()},
        "results": report,
        "note": "Real Binance candles. BTC recipe, not tuned. Logistic regression and naive are reference only.",
    }
    (ARTIFACTS_DIR / f"{slug}_rf.metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print(symbol, "rows", len(df), "train", len(train_set), "test", len(test), metrics["test_period"])
    for name, r in report.items():
        print(f"  {name:20s} acc={r['accuracy']:.4f} bal={r['balanced_accuracy']:.4f} "
              f"f1={r['macro_f1']:.4f} hit={r['directional_hit_rate']}", flush=True)


if __name__ == "__main__":
    binance = ccxt.binance({"enableRateLimit": True, "timeout": 20000})
    for name in SYMBOLS:
        train(binance, name)
