import pandas as pd
import pytest

from labels import make_target


def make_df(closes):
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=len(closes), freq="h", tz="UTC"),
            "close": closes,
        }
    )


def test_labels_match_expected_forward_returns():
    out = make_target(make_df([100.0, 102.0, 102.0, 99.0]), horizon=1, threshold=0.01)
    assert list(out["label"]) == ["UP", "SIDEWAYS", "DOWN"]
    assert out["forward_return"].iloc[0] == pytest.approx(0.02)


def test_horizon_uses_correct_future_candle():
    out = make_target(make_df([100.0, 100.0, 110.0, 90.0]), horizon=2, threshold=0.05)
    assert list(out["label"]) == ["UP", "DOWN"]


def test_rows_without_future_are_dropped():
    df = make_df([100.0] * 10)
    out = make_target(df, horizon=3, threshold=0.01)
    assert len(out) == 7
    assert out["timestamp"].iloc[-1] == df["timestamp"].iloc[6]


def test_return_exactly_at_threshold_is_sideways():
    out = make_target(make_df([100.0, 150.0]), horizon=1, threshold=0.5)
    assert list(out["label"]) == ["SIDEWAYS"]
