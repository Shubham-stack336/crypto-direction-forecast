"""Cache, failover, rate limits, unique forecasts and model integrity."""
import hashlib
import json
import threading

import fakeredis
import pandas as pd
import pytest

from app.background import BackgroundWorker
from app.core.cache import MemoryStore, RedisStore
from app.core.config import get_settings
from app.ml.inference import IncompatibleModelError
from app.repositories.market_repository import MarketDataUnavailableError, MarketSymbolError
from app.repositories.model_repository import FileModelRepository
from app.repositories.resilient_market import BREAKER_OPEN_S, CachingMarketRepository, FailoverMarketRepository
from tests.conftest import FakeMarketRepository, build_market, make_prediction


@pytest.fixture(params=["memory", "redis"])
def store(request):
    return MemoryStore() if request.param == "memory" else RedisStore(fakeredis.FakeRedis())


def test_store_basics(store):
    assert store.get("a") is None
    store.set("a", b"x", 10)
    assert store.get("a") == b"x"
    assert [store.incr("n", 60) for _ in range(3)] == [1, 2, 3]
    assert store.acquire("l", 60) and not store.acquire("l", 60)


def test_memory_store_expires_and_stays_bounded():
    now = [0.0]
    store = MemoryStore(clock=lambda: now[0], max_keys=3)
    for i in range(10):
        store.set(str(i), b"x", 5)
    assert len(store._data) == 3
    now[0] = 6
    assert store.get("9") is None


def test_redis_outage_falls_back_to_memory():
    server = fakeredis.FakeServer()
    server.connected = False
    store = RedisStore(fakeredis.FakeRedis(server=server))
    store.set("a", b"x", 10)
    assert store.get("a") == b"x" and store.incr("n", 5) == 1


def test_candles_are_cached_exactly_and_refreshed_at_the_hour(store):
    inner = FakeMarketRepository(build_market())
    wall = [3600.0 * 10 + 3599]
    repo = CachingMarketRepository(inner, store, wall=lambda: wall[0])
    first = repo.fetch_candles("BTC/USDT", "1h", 400)
    second = repo.fetch_candles("BTC/USDT", "1h", 400)
    assert inner.calls == 1
    assert first["close"].tolist() == second["close"].tolist()
    assert (first["timestamp"].to_numpy() == second["timestamp"].to_numpy()).all()
    assert str(second["timestamp"].dt.tz) == "UTC"
    wall[0] += 2  # a new hour: the old unfinished candle must not be reused
    repo.fetch_candles("BTC/USDT", "1h", 400)
    assert inner.calls == 2


def test_parallel_callers_share_one_fetch():
    inner = FakeMarketRepository(build_market())
    repo = CachingMarketRepository(inner, MemoryStore(), wall=lambda: 1000.0)
    threads = [threading.Thread(target=repo.fetch_candles, args=("BTC/USDT", "1h", 400)) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert inner.calls == 1


def test_old_tickers_are_served_when_the_exchange_is_down():
    inner, wall = FakeMarketRepository(build_market()), [1000.0]
    repo = CachingMarketRepository(inner, MemoryStore(), wall=lambda: wall[0])
    before = repo.list_tickers()
    inner.error, wall[0] = MarketDataUnavailableError("x"), 1100.0
    assert repo.list_tickers() == before


def test_failover_and_circuit_breaker():
    bad = FakeMarketRepository(error=MarketDataUnavailableError("x"))
    good, now = FakeMarketRepository(build_market()), [0.0]
    repo = FailoverMarketRepository([("bad", bad), ("good", good)], clock=lambda: now[0])
    for _ in range(5):
        assert repo.fetch_candles("BTC/USDT", "1h", 10).attrs["source"] == "good"
    assert bad.calls == 3  # then the breaker opened
    now[0] = BREAKER_OPEN_S + 1
    repo.fetch_candles("BTC/USDT", "1h", 10)
    assert bad.calls == 4


def test_unknown_symbol_does_not_fail_over():
    good = FakeMarketRepository(build_market())
    repo = FailoverMarketRepository([("a", FakeMarketRepository(error=MarketSymbolError("X"))), ("b", good)])
    with pytest.raises(MarketSymbolError):
        repo.fetch_candles("X/USDT", "1h", 10)
    assert good.calls == 0


def test_rate_limit_returns_429_with_cors(make_client, live_market, monkeypatch):
    monkeypatch.setattr(get_settings(), "rate_limit_predict", 2)
    monkeypatch.setattr(get_settings(), "cors_origins", ["https://app.example"])
    monkeypatch.setattr("app.core.rate_limit.WINDOW_S", 10**9)  # no window change during the test
    client = make_client(FakeMarketRepository(live_market))
    codes = []
    for i in range(3):  # spoofing a header we do not trust must not help
        headers = {"Origin": "https://app.example", "X-Forwarded-For": f"1.1.1.{i}"}
        response = client.post("/api/v1/predictions/BTC-USDT", headers=headers)
        codes.append(response.status_code)
    assert codes == [200, 200, 429]
    assert int(response.headers["Retry-After"]) >= 1
    assert response.headers["access-control-allow-origin"] == "https://app.example"
    assert client.get("/health/live").status_code == 200


@pytest.mark.parametrize("path", ["/api/v1/ml/compare/BTC", "/api/v1/ml/predict/BTC", "/api/v1/data/fetch/BTC"])
def test_training_and_download_routes_are_gone(make_client, live_market, path):
    assert make_client(FakeMarketRepository(live_market)).get(path).status_code == 404


def test_metrics_need_a_token(make_client, live_market, monkeypatch):
    assert make_client(FakeMarketRepository(live_market)).get("/metrics").status_code == 404
    monkeypatch.setattr(get_settings(), "metrics_token", "test-token")
    client = make_client(FakeMarketRepository(live_market))
    client.get("/api/v1/market/BTC-USDT")
    assert client.get("/metrics").status_code == 401
    body = client.get("/metrics", headers={"Authorization": "Bearer test-token"})
    assert body.status_code == 200
    assert 'route="/api/v1/market/{symbol}"' in body.text


def test_same_candle_and_model_is_stored_once(history_repo):
    first = history_repo.add(make_prediction("UP", at="2026-01-20T12:00:00+00:00"))
    again = history_repo.add(make_prediction("DOWN", at="2026-01-20T12:10:00+00:00"))
    items, total = history_repo.list("BTC/USDT", "1h", 10, 0)
    assert first == again and total == 1
    assert items[0].label == "DOWN" and items[0].threshold == 0.003


def test_outcome_is_written_once_and_retention_deletes_old_rows(history_repo):
    row = history_repo.add(make_prediction("UP"))
    history_repo.save_outcomes({row: ("UP", 0.01)})
    history_repo.save_outcomes({row: ("DOWN", -0.01)})
    assert history_repo.list("BTC/USDT", "1h", 10, 0)[0][0].outcome_label == "UP"
    assert history_repo.purge_older_than(pd.Timestamp("2026-01-21", tz="UTC").to_pydatetime()) == 1


def test_scan_is_cached(make_client, live_market, monkeypatch):
    market = FakeMarketRepository(live_market)
    client = make_client(market)
    assert client.get("/api/v1/coins/scan?limit=1").status_code == 200
    calls = market.calls
    client.get("/api/v1/coins/scan?limit=1")
    assert market.calls == calls


def test_manifest_rejects_changed_or_unlisted_models(model_dir):
    path = model_dir / "btc_usdt_1h_rf.joblib"
    manifest = model_dir / "manifest.json"
    manifest.write_text(json.dumps({path.name: hashlib.sha256(path.read_bytes()).hexdigest()}))
    assert FileModelRepository(model_dir).get_engine("BTC/USDT", "1h")
    for wrong in ({path.name: "0" * 64}, {}):
        manifest.write_text(json.dumps(wrong))
        with pytest.raises(IncompatibleModelError):
            FileModelRepository(model_dir).get_engine("BTC/USDT", "1h")


def test_background_job_runs_once_per_interval_and_survives_errors():
    runs = []

    def job():
        runs.append(1)
        raise RuntimeError("boom")

    store = MemoryStore()
    for _ in range(2):  # two worker processes sharing a store
        BackgroundWorker(store, job).tick()
    assert len(runs) == 1
