from features import make_features
from labels import make_target
from step3_validate import CSV_PATH, load_csv, validate

HORIZON = 3
THRESHOLD = 0.003


def build_dataset(horizon=HORIZON, threshold=THRESHOLD, feature_fn=make_features):
    df, problems = validate(load_csv(CSV_PATH))
    if problems:
        raise ValueError(f"Fix data problems first: {problems}")
    return feature_fn(df).merge(make_target(df, horizon, threshold), on="timestamp")