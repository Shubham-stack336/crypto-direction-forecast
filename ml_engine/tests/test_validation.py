import pandas as pd

from step3_validate import validate


def make_candles(n=600):
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=n, freq="h", tz="UTC"),
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
            "volume": 1.0,
        }
    )


def test_clean_data_passes():
    _, problems = validate(make_candles())
    assert problems == []


def test_missing_candle_is_reported():
    _, problems = validate(make_candles().drop(index=300))
    assert any("gap" in p for p in problems)


def test_duplicates_are_removed():
    candles = make_candles()
    with_dup = pd.concat([candles, candles.iloc[[10]]])
    clean, _ = validate(with_dup)
    assert len(clean) == 600


def test_impossible_candle_is_reported():
    candles = make_candles()
    candles.loc[5, "high"] = 50.0
    _, problems = validate(candles)
    assert any("impossible" in p for p in problems)
