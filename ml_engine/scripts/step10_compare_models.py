import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from dataset import build_dataset
from evaluation import log_experiment, walk_forward

from features import FEATURE_COLUMNS, make_features_v2


def make_logreg():
    return make_pipeline(
        StandardScaler(),
        LogisticRegression(class_weight="balanced", max_iter=1000),
    )


def make_forest():
    return RandomForestClassifier(
        n_estimators=300,
        max_depth=5,
        min_samples_leaf=50,
        class_weight="balanced_subsample",
        random_state=42,
        n_jobs=-1,
    )


def make_hgb():
    return HistGradientBoostingClassifier(
        max_depth=3,
        learning_rate=0.05,
        max_iter=200,
        class_weight="balanced",
        random_state=42,
    )


data = build_dataset(feature_fn=make_features_v2)
dev = data.iloc[: int(len(data) * 0.85)]

factories = {
    "logistic regression": make_logreg,
    "random forest": make_forest,
    "hist gradient boosting": make_hgb,
}
results = {name: walk_forward(dev, FEATURE_COLUMNS, f) for name, f in factories.items()}

base = results["logistic regression"]
for name, r in results.items():
    wins = int((r["bal"] > base["bal"]).sum())
    print(
        f"{name:23s} bal={r['bal'].mean():.3f} (std {r['bal'].std():.3f})  "
        f"macroF1={r['f1'].mean():.3f}  hit_rate={np.nanmean(r['hit']):.3f}  "
        f"beats logreg in {wins}/{len(r['bal'])} folds"
    )

print()
for name, r in results.items():
    log_experiment(name, "v1", r)
    diff = r["bal"].mean() - base["bal"].mean()
    print(f"{name:23s} exact balanced-acc difference vs logreg: {diff:+.4f}")
print("Logged to data/experiments.jsonl")
