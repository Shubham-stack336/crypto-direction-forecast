"""Train one model for every USDT pair, on real Binance hourly candles from many coins.

Same features, labels and hyperparameters as the per-coin models; nothing is tuned.
Every coin is split at the same calendar moment, so the test period is in the future for all
of them. The model is reported on the training coins and on coins it has never seen.
Run from backend/:  python scripts/train_universal_model.py
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ccxt
import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from train_real_models import (
    ARTIFACTS_DIR, BACKEND, DAYS, DEV_FRACTION, HORIZON, THRESHOLD, TIMEFRAME,
    build_dataset, evaluate, fetch_history,
)
from app.ml.features import FEATURE_COLUMNS, FEATURE_VERSION
from app.ml.validation import validate

TRAIN_COINS = [
    "BTC", "ETH", "SOL", "DOGE", "BNB", "XRP", "ADA", "TRX", "AVAX", "LINK", "DOT", "LTC", "BCH",
    "UNI", "ATOM", "NEAR", "APT", "FIL", "ETC", "ARB", "OP", "INJ", "SUI", "XLM", "HBAR",
]
UNSEEN_COINS = ["PEPE", "SHIB", "AAVE", "ICP", "ALGO", "VET", "SAND", "GRT", "FET", "TIA"]
CACHE_DIR = BACKEND / "data" / "universe"
STEM = "all_usdt_1h_rf"


def load(exchange, coin):
    path = CACHE_DIR / f"{coin.lower()}_usdt_1h.csv"
    if path.exists():
        df = pd.read_csv(path)
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    else:
        df = fetch_history(exchange, f"{coin}/USDT")
        df.to_csv(path, index=False)
    df, problems = validate(df, min_rows=DAYS * 24 - 48)
    if problems:
        raise ValueError("; ".join(problems))
    data = build_dataset(df)
    finite = np.isfinite(data[FEATURE_COLUMNS].to_numpy(dtype=float)).all(axis=1)
    return data[finite].assign(coin=coin)


def main():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    exchange = ccxt.binance({"enableRateLimit": True, "timeout": 20000})
    frames, skipped = {}, {}
    for coin in TRAIN_COINS + UNSEEN_COINS:
        try:
            frames[coin] = load(exchange, coin)
            print("loaded", coin, len(frames[coin]), flush=True)
        except (ValueError, ccxt.BadSymbol) as err:
            skipped[coin] = str(err)
            print("SKIPPED", coin, err, flush=True)

    train_coins = [c for c in TRAIN_COINS if c in frames]
    unseen_coins = [c for c in UNSEEN_COINS if c in frames]
    start = max(frames[c]["timestamp"].iloc[0] for c in frames)
    end = min(frames[c]["timestamp"].iloc[-1] for c in frames)
    cutoff = start + (end - start) * DEV_FRACTION
    gap = pd.Timedelta(hours=HORIZON)  # training labels must not see the test period

    def part(coins, test):
        data = pd.concat([frames[c] for c in coins], ignore_index=True)
        keep = (data["timestamp"] >= cutoff) & (data["timestamp"] <= end) if test else data["timestamp"] < cutoff - gap
        return data[keep]

    train, seen, unseen = part(train_coins, False), part(train_coins, True), part(unseen_coins, True)
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
    results, seen_results = {}, {}
    for name, model in models.items():
        model.fit(train[FEATURE_COLUMNS], train["label"])
        results[name] = evaluate(model, unseen[FEATURE_COLUMNS], unseen["label"])
        seen_results[name] = evaluate(model, seen[FEATURE_COLUMNS], seen["label"])
        for title, r in (("unseen", results[name]), ("seen", seen_results[name])):
            print(f"{name:20s} {title:7s} acc={r['accuracy']:.4f} bal={r['balanced_accuracy']:.4f} "
                  f"f1={r['macro_f1']:.4f} hit={r['directional_hit_rate']}", flush=True)

    chosen = models["random_forest"]
    per_coin = {
        c: evaluate(chosen, d[FEATURE_COLUMNS], d["label"])["balanced_accuracy"]
        for c, d in unseen.groupby("coin")
    }
    print("unseen per coin", per_coin)
    metadata = {
        "symbol": "ALL/USDT", "timeframe": TIMEFRAME, "horizon_candles": HORIZON, "threshold": THRESHOLD,
        "feature_version": FEATURE_VERSION, "feature_columns": FEATURE_COLUMNS,
        "classes": [str(c) for c in chosen.classes_],
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "train_period": [str(train["timestamp"].min()), str(train["timestamp"].max())],
        "sklearn_version": sklearn.__version__, "data_source": "binance via ccxt",
        "model_name": "universal", "train_coins": train_coins,
    }
    joblib.dump({"model": chosen, "metadata": metadata}, ARTIFACTS_DIR / f"{STEM}.joblib")
    metrics = {
        "candidate_model": "random_forest",
        "test_period": [str(unseen["timestamp"].min()), str(unseen["timestamp"].max())],
        "test_rows": len(unseen),
        "test_class_distribution": {k: int(v) for k, v in unseen["label"].value_counts().items()},
        "results": results,
        "results_on_training_coins": seen_results,
        "balanced_accuracy_per_unseen_coin": per_coin,
        "train_coins": train_coins, "unseen_coins": unseen_coins, "skipped": skipped,
        "note": "Scores are on coins the model never saw, in a later period. Coins are chosen among those "
                "listed today, so delisted coins are not represented.",
    }
    (ARTIFACTS_DIR / f"{STEM}.metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print("DONE train", len(train), "seen", len(seen), "unseen", len(unseen))


if __name__ == "__main__":
    main()
