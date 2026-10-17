import joblib
import numpy as np
import pandas as pd
import pytest

from app.ml.features import FEATURE_COLUMNS
from app.ml.inference import (
    IncompatibleModelError,
    InsufficientHistoryError,
    InvalidInputError,
    ModelNotFoundError,
    PredictionEngine,
    StaleDataError,
)


def with_open_candle(market):
    extra = market.iloc[[-1]].copy()
    extra["timestamp"] = extra["timestamp"] + pd.Timedelta(hours=1)
    return pd.concat([market, extra], ignore_index=True)


def test_prediction_is_structured(engine, market, now):
    result = engine.predict(market, now=now)
    assert result.status == "ok"
    assert result.label in {"DOWN", "SIDEWAYS", "UP"}
    assert set(result.probabilities) == {"DOWN", "SIDEWAYS", "UP"}
    assert sum(result.probabilities.values()) == pytest.approx(1.0, abs=1e-3)
    assert result.symbol == "BTC/USDT"
    assert result.timeframe == "1h"
    assert result.horizon_candles == 3
    assert result.model_version == "v1-2026-01-01"
    assert result.latest_candle_utc == market["timestamp"].iloc[-1].isoformat()
    assert result.data_quality["dropped_incomplete_candle"] is False


def test_incomplete_candle_is_dropped(engine, market, now):
    result = engine.predict(with_open_candle(market), now=now)
    assert result.data_quality["dropped_incomplete_candle"] is True
    assert result.latest_candle_utc == market["timestamp"].iloc[-1].isoformat()


def test_open_candle_does_not_change_prediction(engine, market, now):
    candles = with_open_candle(market)
    altered = candles.copy()
    altered.loc[altered.index[-1], ["open", "high", "low", "close"]] = 500.0
    assert engine.predict(candles, now=now).probabilities == engine.predict(altered, now=now).probabilities


def test_same_input_gives_same_output(engine, market, now):
    assert engine.predict(market, now=now).probabilities == engine.predict(market, now=now).probabilities


def test_input_is_not_modified(engine, market, now):
    before = market.copy()
    engine.predict(market, now=now)
    pd.testing.assert_frame_equal(before, market)


def test_stale_data_is_rejected(engine, market, now):
    with pytest.raises(StaleDataError):
        engine.predict(market, now=now + pd.Timedelta(hours=10))


def test_staleness_check_can_be_disabled(artifact_factory, market, now):
    engine = PredictionEngine.load(artifact_factory(), max_staleness_candles=None)
    assert engine.predict(market, now=now + pd.Timedelta(hours=10)).status == "ok"


def test_too_little_history_is_rejected(engine, market, now):
    with pytest.raises(InsufficientHistoryError):
        engine.predict(market.tail(50), now=now)


def test_missing_columns_are_rejected(engine, market, now):
    with pytest.raises(InvalidInputError):
        engine.predict(market.drop(columns=["volume"]), now=now)


def test_non_dataframe_is_rejected(engine, now):
    with pytest.raises(InvalidInputError):
        engine.predict([1, 2, 3], now=now)


def test_missing_values_are_rejected(engine, market, now):
    bad = market.copy()
    bad.loc[200, "close"] = np.nan
    with pytest.raises(InvalidInputError):
        engine.predict(bad, now=now)


def test_missing_model_file(tmp_path):
    with pytest.raises(ModelNotFoundError):
        PredictionEngine.load(tmp_path / "nope.joblib")


def test_corrupted_model_file(tmp_path):
    path = tmp_path / "bad.joblib"
    path.write_bytes(b"this is not a model")
    with pytest.raises(IncompatibleModelError):
        PredictionEngine.load(path)


def test_wrong_feature_order_is_rejected(artifact_factory):
    path = artifact_factory(feature_columns=list(reversed(FEATURE_COLUMNS)))
    with pytest.raises(IncompatibleModelError):
        PredictionEngine.load(path)


def test_unknown_feature_version_is_rejected(artifact_factory):
    path = artifact_factory(feature_version="v99")
    with pytest.raises(IncompatibleModelError):
        PredictionEngine.load(path)


def test_wrong_file_structure_is_rejected(tmp_path):
    path = tmp_path / "odd.joblib"
    joblib.dump({"foo": 1}, path)
    with pytest.raises(IncompatibleModelError):
        PredictionEngine.load(path)
