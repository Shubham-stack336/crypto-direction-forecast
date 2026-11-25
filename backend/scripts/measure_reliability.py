"""Measure how often each served model is right at each confidence level, on the 2023-24 holdout.

This only reports: nothing is fitted or chosen by its score. "Clear" means the model's 20% most
confident forecasts (a cut on the probabilities, made without looking at the outcomes).
Writes <stem>.reliability.json next to each model. Run after `train_v2.py download`.
"""
import hashlib
import json

import joblib
import numpy as np
import pandas as pd

from train_v2 import ARTIFACTS_DIR, CLASSES, CLEAR_SHARE, HOLDOUT, HOLDOUT_COINS, HOLDOUT_DIR, V1, dataset, v1

EDGES = (0.0, 0.36, 0.39, 0.42, 0.45, 0.50, 0.55, 1.01)
OWN = ["BTC", "ETH", "SOL", "DOGE"]
MIN_ROWS = 100


def measure(stem: str, coins: list[str]) -> None:
    rows = pd.concat([dataset(HOLDOUT_DIR / f"{c.lower()}.csv", c) for c in coins], ignore_index=True)
    model = joblib.load(ARTIFACTS_DIR / f"{stem}.joblib")["model"]
    proba = model.predict_proba(rows[V1].set_axis(v1.FEATURE_COLUMNS, axis=1))
    top = proba.max(axis=1)
    right = np.array(CLASSES)[proba.argmax(axis=1)] == rows["label"].to_numpy()
    clear = float(np.quantile(top, 1 - CLEAR_SHARE))
    bins = []
    for lo, hi in zip(EDGES, EDGES[1:]):
        m = (top >= lo) & (top < hi)
        if m.sum() >= MIN_ROWS:
            bins.append({"from": lo, "to": hi, "rows": int(m.sum()), "accuracy": float(right[m].mean())})
    strong = top >= clear
    report = {
        "model_sha256": hashlib.sha256((ARTIFACTS_DIR / f"{stem}.joblib").read_bytes()).hexdigest(),
        "clear_threshold": clear, "clear_accuracy": float(right[strong].mean()),
        "other_accuracy": float(right[~strong].mean()), "rows": len(rows), "coins": coins,
        "period": [str(HOLDOUT[0]), str(HOLDOUT[1])], "bins": bins,
    }
    (ARTIFACTS_DIR / f"{stem}.reliability.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(stem, f"clear>={clear:.3f} acc={report['clear_accuracy']:.3f} other={report['other_accuracy']:.3f}",
          [(b["from"], b["rows"], round(b["accuracy"], 3)) for b in bins])


if __name__ == "__main__":
    for coin in OWN:
        measure(f"{coin.lower()}_usdt_1h_rf", [coin])
    measure("all_usdt_1h_rf", [c for c in HOLDOUT_COINS if c not in OWN])
