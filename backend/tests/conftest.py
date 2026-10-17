"""Shared fixtures. All data and models here are SYNTHETIC and exist only to test code behaviour."""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy import text

from app.dependencies import get_history_repository, get_market_repository, get_model_repository
from app.main import create_app
from app.ml.features import FEATURE_COLUMNS, make_features
from app.ml.inference import DISCLAIMER, Prediction, PredictionEngine
from app.repositories.database import create_db_engine, create_session_factory
from app.repositories.history_repository import PostgresHistoryRepository
from app.repositories.model_repository import FileModelRepository

LAST_CLOSED = pd.Timestamp("2026-01-20 00:00", tz="UTC")
ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def alembic_config(url: str) -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    cfg.attributes["configure_logger"] = False
    return cfg


def make_prediction(label="UP", at="2026-01-20T12:00:00+00:00", symbol="BTC/USDT") -> Prediction:
    probs = {"UP": 0.2, "DOWN": 0.2, "SIDEWAYS": 0.6}
    probs[label] = 0.6 if label in probs else 0.0
    return Prediction(
        label=label,
        probabilities=probs,
        symbol=symbol,
        timeframe="1h",
        horizon_candles=3,
        prediction_time_utc=at,
        latest_candle_utc="2026-01-20T11:00:00+00:00",
        model_version="v1-2026-01-01",
        feature_version="v1",
        status="ok",
        data_quality={"rows_used": 499, "dropped_incomplete_candle": True, "data_age_minutes": 5.0},
        disclaimer=DISCLAIMER,
    )


def build_market(n: int = 400, last_ts: pd.Timestamp = LAST_CLOSED, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    open_ = np.concatenate([[100.0], close[:-1]])
    return pd.DataFrame(
        {
            "timestamp": pd.date_range(end=last_ts, periods=n, freq="h"),
            "open": open_,
            "high": np.maximum(open_, close) * 1.001,
            "low": np.minimum(open_, close) * 0.999,
            "close": close,
            "volume": rng.uniform(10, 100, n),
        }
    )


def write_artifact(directory, market: pd.DataFrame, name: str = "btc_usdt_1h_rf", **metadata_overrides):
    features = make_features(market)
    labels = np.random.default_rng(1).choice(["DOWN", "SIDEWAYS", "UP"], size=len(features))
    model = make_pipeline(
        StandardScaler(), LogisticRegression(class_weight="balanced", max_iter=1000)
    ).fit(features[FEATURE_COLUMNS], labels)
    metadata = {
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "horizon_candles": 3,
        "threshold": 0.003,
        "feature_version": "v1",
        "feature_columns": FEATURE_COLUMNS,
        "classes": [str(c) for c in model.classes_],
        "trained_at_utc": "2026-01-01T00:00:00+00:00",
        "train_period": ["2025-01-01T00:00:00+00:00", "2025-12-31T00:00:00+00:00"],
    }
    metadata.update(metadata_overrides)
    path = directory / f"{name}.joblib"
    joblib.dump({"model": model, "metadata": metadata}, path)
    return path


class FakeMarketRepository:
    def __init__(self, candles: pd.DataFrame | None = None, error: Exception | None = None):
        self.candles = candles
        self.error = error
        self.calls = 0

    def fetch_candles(self, symbol, timeframe, limit):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.candles.copy()


@pytest.fixture
def market():
    return build_market()


@pytest.fixture
def now():
    return LAST_CLOSED + pd.Timedelta(hours=1, minutes=30)


@pytest.fixture
def artifact_factory(tmp_path, market):
    def _make(name="model", **metadata_overrides):
        return write_artifact(tmp_path, market, name=name, **metadata_overrides)

    return _make


@pytest.fixture
def engine(artifact_factory):
    return PredictionEngine.load(artifact_factory())


@pytest.fixture
def live_market():
    """Candles ending at the current (still open) hour, like a real exchange response."""
    current_hour = pd.Timestamp.now(tz="UTC").floor("h")
    return build_market(n=400, last_ts=current_hour)


@pytest.fixture
def model_dir(tmp_path, market):
    directory = tmp_path / "models"
    directory.mkdir()
    write_artifact(directory, market)
    (directory / "btc_usdt_1h_rf.metrics.json").write_text(
        json.dumps({"candidate_model": "synthetic-test-model", "test_rows": 10}), encoding="utf-8"
    )
    return directory


@pytest.fixture(scope="session", autouse=True)
def detach_app_log_handler():
    """create_app() installs a stderr handler; drop it before pytest closes its captured streams."""
    yield
    import logging

    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, "_app_handler", False):
            root.removeHandler(handler)


@pytest.fixture(scope="session")
def pg_server_url(tmp_path_factory):
    """A real, throw-away PostgreSQL server migrated to the latest schema via Alembic."""
    import pgserver

    server = pgserver.get_server(str(tmp_path_factory.mktemp("pgdata")), cleanup_mode="stop")
    url = server.get_uri().replace("postgresql://", "postgresql+psycopg://", 1)
    command.upgrade(alembic_config(url), "head")
    yield url
    server.cleanup()


@pytest.fixture
def db_engine(pg_server_url):
    engine = create_db_engine(pg_server_url, connect_timeout_s=3, statement_timeout_ms=5000, pool_size=2)
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE predictions, model_versions RESTART IDENTITY"))
    yield engine
    engine.dispose()


@pytest.fixture
def history_repo(db_engine):
    return PostgresHistoryRepository(create_session_factory(db_engine))


@pytest.fixture
def dead_history_repo():
    """Points at a port nobody listens on, to simulate a database outage."""
    engine = create_db_engine("postgresql+psycopg://u:p@127.0.0.1:1/none", connect_timeout_s=1)
    yield PostgresHistoryRepository(create_session_factory(engine))
    engine.dispose()


@pytest.fixture
def make_client(model_dir):
    def _make(market_repo, directory=None, history_repo=None):
        app = create_app()
        model_repo = FileModelRepository(directory or model_dir, max_staleness_candles=3)
        app.dependency_overrides[get_market_repository] = lambda: market_repo
        app.dependency_overrides[get_model_repository] = lambda: model_repo
        app.dependency_overrides[get_history_repository] = lambda: history_repo
        return TestClient(app, raise_server_exceptions=False)

    return _make
