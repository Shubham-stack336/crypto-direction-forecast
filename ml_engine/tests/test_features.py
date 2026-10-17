import numpy as np
import pandas as pd
import pytest

from features import (
    FEATURE_COLUMNS,
    FEATURE_COLUMNS_V2,
    WARMUP_ROWS_V2,
    make_features,
    make_features_v2,
)


def make_market(n=300, seed=0):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=n, freq="h", tz="UTC"),
            "close": close,
            "volume": rng.uniform(10, 100, n),
        }
    )


@pytest.mark.parametrize(
    "feature_fn, cols",
    [(make_features, FEATURE_COLUMNS), (make_features_v2, FEATURE_COLUMNS_V2)],
)
def test_past_features_do_not_change_when_future_changes(feature_fn, cols):
    df = make_market()
    before = feature_fn(df)

    altered = df.copy()
    altered.loc[250:, "close"] = altered.loc[250:, "close"] * 3
    altered.loc[250:, "volume"] = altered.loc[250:, "volume"] * 5
    after = feature_fn(altered)

    past = before.index[before.index < 250]
    pd.testing.assert_frame_equal(before.loc[past, cols], after.loc[past, cols])


def test_v1_has_no_missing_values_and_warmup_removed():
    out = make_features(make_market())
    assert not out[FEATURE_COLUMNS].isna().any().any()
    assert out.index.min() >= 29


def test_v2_has_no_missing_values_and_warmup_removed():
    out = make_features_v2(make_market())
    assert not out[FEATURE_COLUMNS_V2].isna().any().any()
    assert out.index.min() >= WARMUP_ROWS_V2
