import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.dummy import DummyClassifier
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
)

from dataset import HORIZON, THRESHOLD, build_dataset
from features import FEATURE_COLUMNS, make_features_v2
from model_zoo import make_forest, make_logreg

CLASSES = ["DOWN", "SIDEWAYS", "UP"]
ARTIFACT_DIR = Path("artifacts")
ARTIFACT_DIR.mkdir(exist_ok=True)
MODEL_PATH = ARTIFACT_DIR / "btc_usdt_1h_rf.joblib"
METRICS_PATH = ARTIFACT_DIR / "btc_usdt_1h_rf.metrics.json"


def evaluate(model, X, y):
    pred = model.predict(X)
    actual = y.to_numpy()
    moved = np.isin(actual, ["UP", "DOWN"]) & np.isin(pred, ["UP", "DOWN"])
    hit = float((pred[moved] == actual[moved]).mean()) if moved.any() else None
    return {
        "accuracy": float(accuracy_score(actual, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(actual, pred)),
        "macro_f1": float(f1_score(actual, pred, average="macro", zero_division=0)),
        "directional_hit_rate": hit,
        "confusion_matrix_rows_true_cols_pred": confusion_matrix(actual, pred, labels=CLASSES).tolist(),
    }


data = build_dataset(feature_fn=make_features_v2)
dev_end = int(len(data) * 0.85)
train = data.iloc[: dev_end - HORIZON]
test = data.iloc[dev_end:]

X_train, y_train = train[FEATURE_COLUMNS], train["label"]
X_test, y_test = test[FEATURE_COLUMNS], test["label"]

models = {
    "random_forest": make_forest(),
    "logistic_regression": make_logreg(),
    "naive_most_frequent": DummyClassifier(strategy="most_frequent"),
}
report = {}
for name, model in models.items():
    model.fit(X_train, y_train)
    report[name] = evaluate(model, X_test, y_test)

chosen = models["random_forest"]

metadata = {
    "symbol": "BTC/USDT",
    "timeframe": "1h",
    "horizon_candles": HORIZON,
    "threshold": THRESHOLD,
    "feature_version": "v1",
    "feature_columns": FEATURE_COLUMNS,
    "classes": [str(c) for c in chosen.classes_],
    "trained_at_utc": datetime.now(timezone.utc).isoformat(),
    "train_period": [str(train["timestamp"].iloc[0]), str(train["timestamp"].iloc[-1])],
    "sklearn_version": sklearn.__version__,
}
joblib.dump({"model": chosen, "metadata": metadata}, MODEL_PATH)

metrics_doc = {
    "candidate_model": "random_forest",
    "test_period": [str(test["timestamp"].iloc[0]), str(test["timestamp"].iloc[-1])],
    "test_rows": len(test),
    "test_class_distribution": {k: int(v) for k, v in y_test.value_counts().items()},
    "results": report,
    "note": "Test set evaluated once. Logistic regression and naive are reference only.",
}
with open(METRICS_PATH, "w") as f:
    json.dump(metrics_doc, f, indent=2)

for name, r in report.items():
    print(
        f"{name:20s} acc={r['accuracy']:.3f}  bal_acc={r['balanced_accuracy']:.3f}  "
        f"macroF1={r['macro_f1']:.3f}  hit_rate={r['directional_hit_rate']}"
    )
print("Test period:", metrics_doc["test_period"], "rows:", len(test))
print("Test class distribution:", metrics_doc["test_class_distribution"])

artifact = joblib.load(MODEL_PATH)
loaded = artifact["model"]
cols = artifact["metadata"]["feature_columns"]
print("Reloaded model gives identical predictions:", np.array_equal(loaded.predict(X_test[cols]), chosen.predict(X_test)))
latest = X_test[cols].iloc[[-1]]
probs = loaded.predict_proba(latest)[0]
print("Example prediction probabilities:", {c: round(float(p), 3) for c, p in zip(loaded.classes_, probs)})
