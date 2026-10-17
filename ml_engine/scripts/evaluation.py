import json
from datetime import datetime, timezone


import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, f1_score

from dataset import HORIZON


def walk_forward(dev, feature_cols, model_factory, n_folds=5):
    fold_size = len(dev) // (n_folds + 1)
    bal, f1s, hits = [], [], []

    for k in range(1, n_folds + 1):
        train_end = fold_size * k
        train = dev.iloc[: train_end - HORIZON]
        test = dev.iloc[train_end : train_end + fold_size]

        model = model_factory()
        model.fit(train[feature_cols], train["label"])
        pred = pd.Series(model.predict(test[feature_cols]), index=test.index)
        actual = test["label"]

        bal.append(balanced_accuracy_score(actual, pred))
        f1s.append(f1_score(actual, pred, average="macro", zero_division=0))

        moved = actual.isin(["UP", "DOWN"]) & pred.isin(["UP", "DOWN"])
        hits.append((pred[moved] == actual[moved]).mean() if moved.sum() > 0 else np.nan)

    return {"bal": np.array(bal), "f1": np.array(f1s), "hit": np.array(hits)}


def log_experiment(model_name, feature_set, results, path="data/experiments.jsonl"):
    record = {
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "model": model_name,
        "feature_set": feature_set,
        "bal_mean": float(results["bal"].mean()),
        "bal_std": float(results["bal"].std()),
        "macro_f1_mean": float(results["f1"].mean()),
        "hit_rate_mean": float(np.nanmean(results["hit"])),
        "fold_bal": [round(float(x), 4) for x in results["bal"]],
    }
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")
