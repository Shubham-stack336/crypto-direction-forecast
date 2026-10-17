import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from dataset import build_dataset
from evaluation import walk_forward
from features import FEATURE_COLUMNS, FEATURE_COLUMNS_V2, make_features_v2
from step3_validate import CSV_PATH, load_csv, validate

df, _ = validate(load_csv(CSV_PATH))
t = 1500
full_row = make_features_v2(df).loc[t, FEATURE_COLUMNS_V2].to_numpy(dtype=float)
cut_row = make_features_v2(df.iloc[: t + 1]).loc[t, FEATURE_COLUMNS_V2].to_numpy(dtype=float)
leak_ok = np.allclose(full_row, cut_row)
print("Leakage check passed:", leak_ok)
if not leak_ok:
    raise SystemExit("v2 features use future data. Fix before continuing.")


def make_logreg():
    return make_pipeline(
        StandardScaler(),
        LogisticRegression(class_weight="balanced", max_iter=1000),
    )


data = build_dataset(feature_fn=make_features_v2)
dev = data.iloc[: int(len(data) * 0.85)]

results = {
    "v1 (7 features)": walk_forward(dev, FEATURE_COLUMNS, make_logreg),
    "v2 (12 features)": walk_forward(dev, FEATURE_COLUMNS_V2, make_logreg),
}

for name, r in results.items():
    print(
        f"{name:17s} bal={r['bal'].mean():.3f} (std {r['bal'].std():.3f})  "
        f"macroF1={r['f1'].mean():.3f}  hit_rate={np.nanmean(r['hit']):.3f}"
    )

v1, v2 = results["v1 (7 features)"], results["v2 (12 features)"]
print(f"v2 beat v1 in {int((v2['bal'] > v1['bal']).sum())} of {len(v1['bal'])} folds")
print(f"Mean balanced-acc difference (v2 - v1): {v2['bal'].mean() - v1['bal'].mean():+.3f}")
