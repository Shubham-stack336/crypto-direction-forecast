"""Candle repository tests run against a real PostgreSQL server (see conftest.pg_server_url)."""
from app.repositories.candle_repository import PostgresCandleRepository


def candle(hour: int, close: float = 100.0) -> dict:
    return {
        "timestamp": f"2026-01-20T{hour:02d}:00:00+00:00",
        "open": 99.0,
        "high": 101.0,
        "low": 98.0,
        "close": close,
        "volume": 10.0,
    }


def test_save_and_read_back_oldest_first(candle_repo: PostgresCandleRepository):
    candle_repo.save("BTC/USDT", "1h", [candle(9), candle(10), candle(11)])
    saved = candle_repo.latest("BTC/USDT", "1h", limit=3)
    assert [c["timestamp"][11:13] for c in saved] == ["09", "10", "11"]
    assert saved[0] == candle(9)


def test_latest_returns_only_the_newest_rows(candle_repo):
    candle_repo.save("BTC/USDT", "1h", [candle(h) for h in range(5)])
    saved = candle_repo.latest("BTC/USDT", "1h", limit=3)
    assert [c["timestamp"][11:13] for c in saved] == ["02", "03", "04"]


def test_saving_the_same_candle_again_updates_it(candle_repo):
    candle_repo.save("BTC/USDT", "1h", [candle(9, close=100.0)])
    candle_repo.save("BTC/USDT", "1h", [candle(9, close=105.0), candle(10)])
    saved = candle_repo.latest("BTC/USDT", "1h", limit=10)
    assert len(saved) == 2
    assert saved[0]["close"] == 105.0


def test_other_symbols_are_not_mixed_in(candle_repo):
    candle_repo.save("BTC/USDT", "1h", [candle(9)])
    candle_repo.save("ETH/USDT", "1h", [candle(10)])
    assert len(candle_repo.latest("ETH/USDT", "1h", limit=10)) == 1
    assert candle_repo.latest("BTC/USDT", "4h", limit=10) == []


def test_saving_nothing_is_a_no_op(candle_repo):
    candle_repo.save("BTC/USDT", "1h", [])
    assert candle_repo.latest("BTC/USDT", "1h", limit=3) == []
