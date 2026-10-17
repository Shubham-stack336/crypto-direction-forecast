import pandas as pd

from app.ml.features import FEATURE_COLUMNS, make_features
from app.ml.validation import validate
from tests.conftest import build_market


def test_past_features_do_not_change_when_future_changes():
    df = build_market(300)
    before = make_features(df)

    altered = df.copy()
    altered.loc[250:, "close"] = altered.loc[250:, "close"] * 3
    altered.loc[250:, "volume"] = altered.loc[250:, "volume"] * 5
    after = make_features(altered)

    past = before.index[before.index < 250]
    pd.testing.assert_frame_equal(before.loc[past, FEATURE_COLUMNS], after.loc[past, FEATURE_COLUMNS])


def test_features_have_no_missing_values_and_warmup_removed():
    out = make_features(build_market(300))
    assert not out[FEATURE_COLUMNS].isna().any().any()
    assert out.index.min() >= 29


def test_clean_data_passes_validation():
    _, problems = validate(build_market(600), min_rows=500)
    assert problems == []


def test_missing_candle_is_reported():
    _, problems = validate(build_market(600).drop(index=300))
    assert any("gap" in p for p in problems)


def test_duplicates_are_removed():
    candles = build_market(600)
    clean, _ = validate(pd.concat([candles, candles.iloc[[10]]]))
    assert len(clean) == 600


def test_impossible_candle_is_reported():
    candles = build_market(600)
    candles.loc[5, "high"] = 0.01
    _, problems = validate(candles)
    assert any("impossible" in p for p in problems)
