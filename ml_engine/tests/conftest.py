import joblib
import numpy as np
import pandas as pd
import pytest

from features import FEATURE_COLUMNS, make_features
from inference import PredictionEngine
from model_zoo import make_logreg

LAST_CLOSED = pd.Timestamp("2026-01-20 00:00", tz="UTC")


def build_market(n=400, seed=0):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    open_ = np.concatenate([[100.0], close[:-1]])
    return pd.DataFrame(
        {
            "timestamp": pd.date_range(end=LAST_CLOSED, periods=n, freq="h"),
            "open": open_,
            "high": np.maximum(open_, close) * 1.001,
            "low": np.minimum(open_, close) * 0.999,
            "close": close,
            "volume": rng.uniform(10, 100, n),
        }
    )


@pytest.fixture
def market():
    return build_market()


@pytest.fixture
def now():
    return LAST_CLOSED + pd.Timedelta(hours=1, minutes=30)


@pytest.fixture
def artifact_factory(tmp_path, market):
    def _make(name="model.joblib", **metadata_overrides):
        features = make_features(market)
        labels = np.random.default_rng(1).choice(
            ["DOWN", "SIDEWAYS", "UP"], size=len(features)
        )
        model = make_logreg().fit(features[FEATURE_COLUMNS], labels)
        metadata = {
            "symbol": "BTC/USDT",
            "timeframe": "1h",
            "horizon_candles": 3,
            "threshold": 0.003,
            "feature_version": "v1",
            "feature_columns": FEATURE_COLUMNS,
            "classes": [str(c) for c in model.classes_],
            "trained_at_utc": "2026-01-01T00:00:00+00:00",
        }
        metadata.update(metadata_overrides)
        path = tmp_path / name
        joblib.dump({"model": model, "metadata": metadata}, path)
        return path

    return _make


@pytest.fixture
def engine(artifact_factory):
    return PredictionEngine.load(artifact_factory())
