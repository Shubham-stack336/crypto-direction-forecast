import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from dataset import HORIZON, build_dataset
from features import FEATURE_COLUMNS

N_FOLDS = 5

data = build_dataset()
dev = data.iloc[: int(len(data) * 0.85)]
fold_size = len(dev) // (N_FOLDS + 1)


def run_walkforward(feature_cols):
    bal_scores, hit_rates = [], []
    for k in range(1, N_FOLDS + 1):
        train_end = fold_size * k
        train = dev.iloc[: train_end - HORIZON]
        test = dev.iloc[train_end : train_end + fold_size]

        model = make_pipeline(
            StandardScaler(),
            LogisticRegression(class_weight="balanced", max_iter=1000),
        )
        model.fit(train[feature_cols], train["label"])
        pred = pd.Series(model.predict(test[feature_cols]), index=test.index)
        actual = test["label"]

        bal_scores.append(balanced_accuracy_score(actual, pred))

        moved = actual.isin(["UP", "DOWN"]) & pred.isin(["UP", "DOWN"])
        if moved.sum() > 0:
            hit_rates.append((pred[moved] == actual[moved]).mean())
    return np.mean(bal_scores), np.mean(hit_rates)


variants = {
    "all features": FEATURE_COLUMNS,
    "without vol_10": [c for c in FEATURE_COLUMNS if c != "vol_10"],
    "only vol_10": ["vol_10"],
}

for name, cols in variants.items():
    bal, hit = run_walkforward(cols)
    print(f"{name:16s} balanced_acc={bal:.3f}  directional_hit_rate={hit:.3f}")
