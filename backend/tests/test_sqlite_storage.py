"""Local-development storage: the same repositories on a real SQLite file."""
import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.core.config import BASE_DIR, Settings, normalize_database_url
from app.repositories.candle_repository import PostgresCandleRepository
from app.repositories.database import create_db_engine, create_session_factory
from app.repositories.history_repository import HistoryStorageError, PostgresHistoryRepository
from app.repositories.local_schema import upgrade_local_schema
from app.repositories.orm import ModelVersionRecord
from tests.conftest import FakeMarketRepository, make_prediction


@pytest.fixture
def url(tmp_path):
    return f"sqlite:///{(tmp_path / 'sub dir' / 'history.db').as_posix()}"


@pytest.fixture
def factory(url):
    upgrade_local_schema(url)
    upgrade_local_schema(url)  # restarting the server must be harmless
    engine = create_db_engine(url)
    yield create_session_factory(engine)
    engine.dispose()


def test_relative_path_is_anchored_to_backend():
    assert normalize_database_url("sqlite:///data/h.db") == f"sqlite:///{(BASE_DIR / 'data/h.db').as_posix()}"


def test_production_rejects_sqlite():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="production", database_url="sqlite:///data/h.db")


def test_history_survives_a_restart(factory, url):
    PostgresHistoryRepository(factory).add(make_prediction("UP", at="2026-01-20T17:30:00+05:30"))
    engine = create_db_engine(url)
    items, total = PostgresHistoryRepository(create_session_factory(engine)).list("BTC/USDT", "1h", 10, 0)
    engine.dispose()
    assert total == 1 and items[0].label == "UP"
    assert items[0].prediction_time_utc == "2026-01-20T12:00:00+00:00"


def test_invalid_label_is_rejected(factory):
    with pytest.raises(HistoryStorageError):
        PostgresHistoryRepository(factory).add(make_prediction("MAYBE"))


def test_candles_are_upserted(factory):
    repo = PostgresCandleRepository(factory)
    candle = {"timestamp": "2026-01-20T11:00:00+00:00", "open": 1, "high": 2, "low": 1, "close": 2, "volume": 5}
    repo.save("BTC/USDT", "1h", [candle])
    repo.save("BTC/USDT", "1h", [{**candle, "close": 1.5}])
    saved = repo.latest("BTC/USDT", "1h", 3)
    assert len(saved) == 1 and saved[0]["close"] == 1.5 and saved[0]["timestamp"] == candle["timestamp"]


def test_api_saves_predictions_and_registers_model_once(make_client, live_market, factory):
    client = make_client(
        FakeMarketRepository(live_market),
        history_repo=PostgresHistoryRepository(factory),
        candle_repo=PostgresCandleRepository(factory),
    )
    for _ in range(2):
        assert client.post("/api/v1/predictions/BTC-USDT").json()["saved"] is True
    page = client.get("/api/v1/predictions/BTC-USDT/history").json()
    assert page["total"] == 1  # same candle and model
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(ModelVersionRecord)) == 1
