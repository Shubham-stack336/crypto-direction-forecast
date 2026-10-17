import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from features import FEATURE_COLUMNS, make_features
from labels import make_target
from step3_validate import CSV_PATH, load_csv, validate

HORIZON = 3
THRESHOLD = 0.003
CLASSES = ["DOWN", "SIDEWAYS", "UP"]

df, problems = validate(load_csv(CSV_PATH))
if problems:
    raise SystemExit(f"Fix data problems first: {problems}")

data = make_features(df).merge(make_target(df, HORIZON, THRESHOLD), on="timestamp")

n = len(data)
train_end = int(n * 0.70)
val_end = int(n * 0.85)

train = data.iloc[: train_end - HORIZON]
val = data.iloc[train_end : val_end - HORIZON]
# test = data.iloc[val_end:]  (untouched for now)

print(f"Train: {len(train)} rows, {train['timestamp'].iloc[0]} -> {train['timestamp'].iloc[-1]}")
print(f"Val:   {len(val)} rows, {val['timestamp'].iloc[0]} -> {val['timestamp'].iloc[-1]}")
print("Train class %:\n", (train["label"].value_counts(normalize=True) * 100).round(1))
print("Val class %:\n", (val["label"].value_counts(normalize=True) * 100).round(1))

X_train, y_train = train[FEATURE_COLUMNS], train["label"]
X_val, y_val = val[FEATURE_COLUMNS], val["label"]

models = {
    "naive (most frequent)": DummyClassifier(strategy="most_frequent"),
    "logistic regression": make_pipeline(
        StandardScaler(),
        LogisticRegression(class_weight="balanced", max_iter=1000),
    ),
}

for name, model in models.items():
    model.fit(X_train, y_train)
    pred = model.predict(X_val)
    print(f"\n=== {name} ===")
    print(f"Accuracy:          {accuracy_score(y_val, pred):.3f}")
    print(f"Balanced accuracy: {balanced_accuracy_score(y_val, pred):.3f}")
    print(f"Macro F1:          {f1_score(y_val, pred, average='macro', zero_division=0):.3f}")
    print("Confusion matrix (rows=true, cols=predicted):", CLASSES)
    print(confusion_matrix(y_val, pred, labels=CLASSES))
    print(classification_report(y_val, pred, labels=CLASSES, zero_division=0))
