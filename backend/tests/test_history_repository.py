"""Repository tests run against a real PostgreSQL server (see conftest.pg_server_url)."""
import pytest
from sqlalchemy import inspect, text

from app.repositories.database import create_db_engine
from app.repositories.history_repository import HistoryStorageError
from tests.conftest import make_prediction


def test_add_and_list_roundtrip(history_repo):
    new_id = history_repo.add(make_prediction("UP"))
    items, total = history_repo.list("BTC/USDT", "1h", limit=10, offset=0)
    assert total == 1
    assert items[0].id == new_id
    assert items[0].label == "UP"
    assert items[0].probabilities == {"UP": 0.6, "DOWN": 0.2, "SIDEWAYS": 0.6}
    assert items[0].prediction_time_utc == "2026-01-20T12:00:00+00:00"
    assert items[0].model_version == "v1-2026-01-01"


def test_list_is_newest_first_and_paginated(history_repo):
    for hour in range(5):
        history_repo.add(make_prediction("UP", at=f"2026-01-20T0{hour}:00:00+00:00"))

    page1, total = history_repo.list("BTC/USDT", "1h", limit=2, offset=0)
    page2, _ = history_repo.list("BTC/USDT", "1h", limit=2, offset=2)
    assert total == 5
    assert [i.prediction_time_utc[11:13] for i in page1] == ["04", "03"]
    assert [i.prediction_time_utc[11:13] for i in page2] == ["02", "01"]


def test_list_filters_by_symbol_and_timeframe(history_repo):
    history_repo.add(make_prediction("UP", symbol="BTC/USDT"))
    history_repo.add(make_prediction("DOWN", symbol="ETH/USDT"))
    items, total = history_repo.list("ETH/USDT", "1h", limit=10, offset=0)
    assert total == 1 and items[0].label == "DOWN"
    assert history_repo.list("BTC/USDT", "4h", limit=10, offset=0) == ([], 0)


def test_register_model_is_idempotent(history_repo, db_engine):
    metadata = {
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "feature_version": "v1",
        "horizon_candles": 3,
        "threshold": 0.003,
        "trained_at_utc": "2026-01-01T00:00:00+00:00",
    }
    history_repo.register_model("v1-2026-01-01", metadata, {"note": "synthetic"})
    history_repo.register_model("v1-2026-01-01", metadata, {"note": "synthetic"})
    with db_engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM model_versions")).scalar() == 1


def test_database_rejects_invalid_label(history_repo):
    with pytest.raises(HistoryStorageError):
        history_repo.add(make_prediction("MAYBE"))
    assert history_repo.list("BTC/USDT", "1h", limit=10, offset=0) == ([], 0)


def test_failed_write_does_not_poison_later_use(history_repo):
    with pytest.raises(HistoryStorageError):
        history_repo.add(make_prediction("MAYBE"))
    history_repo.add(make_prediction("UP"))
    assert history_repo.list("BTC/USDT", "1h", limit=10, offset=0)[1] == 1


def test_expected_indexes_exist(db_engine):
    names = {index["name"] for index in inspect(db_engine).get_indexes("predictions")}
    assert "ix_predictions_symbol_timeframe_time" in names


def test_ping_works(history_repo):
    history_repo.ping()


def test_unreachable_database_raises_storage_error(dead_history_repo):
    with pytest.raises(HistoryStorageError):
        dead_history_repo.ping()
    with pytest.raises(HistoryStorageError):
        dead_history_repo.add(make_prediction("UP"))
    with pytest.raises(HistoryStorageError):
        dead_history_repo.list("BTC/USDT", "1h", limit=10, offset=0)


def test_statement_timeout_is_enforced(pg_server_url):
    engine = create_db_engine(pg_server_url, statement_timeout_ms=200)
    try:
        with pytest.raises(Exception) as error:
            with engine.connect() as connection:
                connection.execute(text("SELECT pg_sleep(3)"))
        assert "statement timeout" in str(error.value).lower()
    finally:
        engine.dispose()
