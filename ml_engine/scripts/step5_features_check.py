import numpy as np

from features import FEATURE_COLUMNS, make_features
from step3_validate import CSV_PATH, load_csv, validate

df, problems = validate(load_csv(CSV_PATH))
if problems:
    raise SystemExit(f"Fix data problems first: {problems}")

features = make_features(df)
print(f"Input rows: {len(df)}, feature rows: {len(features)}")
print(features.head(3))

t = 1500
full_row = features.loc[t, FEATURE_COLUMNS].to_numpy(dtype=float)
cut_row = make_features(df.iloc[: t + 1]).loc[t, FEATURE_COLUMNS].to_numpy(dtype=float)

print("Same features when future data is removed:", np.allclose(full_row, cut_row))
