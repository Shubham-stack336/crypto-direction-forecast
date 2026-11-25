import pandas as pd
import pytest

from app.repositories.history_repository import PostgresHistoryRepository
from app.repositories.database import create_db_engine, create_session_factory
from app.repositories.local_schema import upgrade_local_schema
from app.repositories.market_repository import CcxtMarketRepository, MarketDataUnavailableError
from app.services.prediction_service import PredictionService
from app.repositories.model_repository import FileModelRepository
from tests.conftest import FakeMarketRepository, make_prediction, write_artifact


@pytest.fixture
def both_models(model_dir, market):
    write_artifact(model_dir, market, name="all_usdt_1h_rf", symbol="ALL/USDT", model_name="universal")
    return model_dir


@pytest.fixture
def sqlite_history(tmp_path):
    url = f"sqlite:///{(tmp_path / 'h.db').as_posix()}"
    upgrade_local_schema(url)
    engine = create_db_engine(url)
    yield PostgresHistoryRepository(create_session_factory(engine))
    engine.dispose()


def test_coin_without_its_own_model_uses_the_universal_one(make_client, live_market, both_models, sqlite_history):
    client = make_client(FakeMarketRepository(live_market), history_repo=sqlite_history)
    body = client.post("/api/v1/predictions/XYZ-USDT").json()
    assert body["symbol"] == "XYZ/USDT" and body["saved"] is True
    assert body["model_version"].startswith("universal-")
    status = client.get("/api/v1/models/XYZ-USDT/status").json()
    assert status["symbol"] == "XYZ/USDT" and status["model_kind"] == "universal"
    assert client.get("/api/v1/models/BTC-USDT/status").json()["model_kind"] == "dedicated"
    assert client.get("/api/v1/predictions/XYZ-USDT/history").json()["total"] == 1


@pytest.mark.parametrize("slug", ["USDC-USDT", "ETH-BTC", "EUR-USDT"])
def test_universal_model_refuses_pegged_coins_and_other_quotes(make_client, live_market, both_models, slug):
    assert make_client(FakeMarketRepository(live_market)).post(f"/api/v1/predictions/{slug}").status_code == 404


def test_coins_lists_tickers_with_model_kind(make_client, live_market, both_models):
    items = make_client(FakeMarketRepository(live_market)).get("/api/v1/coins").json()["items"]
    assert [(i["symbol"], i["model"]) for i in items] == [("BTC/USDT", "dedicated"), ("XYZ/USDT", "universal")]


def test_scan_forecasts_without_saving(make_client, live_market, both_models, sqlite_history):
    client = make_client(FakeMarketRepository(live_market), history_repo=sqlite_history)
    items = client.get("/api/v1/coins/scan?limit=2").json()["items"]
    assert len(items) == 2 and abs(sum(items[0]["probabilities"].values()) - 1) < 0.01
    assert client.get("/api/v1/predictions/BTC-USDT/history").json()["total"] == 0
    assert client.get("/api/v1/coins/scan?limit=21").status_code == 422


def test_provider_outage_is_503(make_client):
    client = make_client(FakeMarketRepository(error=MarketDataUnavailableError("x")))
    assert client.get("/api/v1/coins").status_code == 503
    assert client.get("/api/v1/coins/scan").status_code == 503


def test_track_record_compares_forecast_with_reality(both_models, sqlite_history):
    times = pd.date_range("2026-01-20 00:00", periods=10, freq="h", tz="UTC")
    closes = [100, 100, 100, 101, 101, 101, 101, 101, 101, 101]
    candles = pd.DataFrame({"timestamp": times, "open": closes, "high": closes, "low": closes,
                            "close": closes, "volume": 1.0})
    for label, hour in (("DOWN", 0), ("UP", 0), ("UP", 4), ("UP", 8)):
        p = make_prediction(label, at=f"2026-01-20T{hour + 1:02d}:0{0 if label == 'DOWN' else 5}:00+00:00")
        object.__setattr__(p, "latest_candle_utc", times[hour].isoformat())
        sqlite_history.add(p)
    old = make_prediction("UP", at="2026-01-01T00:00:00+00:00")
    object.__setattr__(old, "latest_candle_utc", "2026-01-01T00:00:00+00:00")
    sqlite_history.add(old)
    service = PredictionService(FakeMarketRepository(candles), FileModelRepository(both_models), 500, 3,
                                history_repo=sqlite_history)
    record = service.track_record("BTC/USDT", "1h", now=times[-1] + pd.Timedelta(hours=1))
    # hour 0: only the later UP counts and +1% is UP; hour 4: flat, so UP is wrong; hour 8: not finished
    assert (record.checked, record.correct, record.pending, record.not_checkable) == (2, 1, 1, 1)
    assert {(i.label, i.actual) for i in record.items} == {("UP", "UP"), ("UP", "SIDEWAYS")}


def test_ticker_list_filters_and_caches():
    class Stub:
        calls = 0

        def load_markets(self):
            stock = {"spot": True, "active": True, "info": {"permissionSets": [["SPOT"]]}}
            base = {**stock, "info": {"permissionSets": [["SPOT", "TRD_GRP_016"]]}}
            return {"BTC/USDT": base, "USDC/USDT": base, "ETH/BTC": base, "OLD/USDT": {**base, "active": False},
                    "BTC/USDT:USDT": {**base, "spot": False}, "S/USDT": base, "NVDAB/USDT": stock}

        def fetch_tickers(self):
            self.calls += 1
            row = {"last": 1.0, "percentage": None, "quoteVolume": 5.0}
            return {s: row for s in self.load_markets()} | {"S/USDT": {**row, "quoteVolume": 9.0}}

    repo = CcxtMarketRepository("binance", 1000, 1)
    repo._exchange = Stub()
    assert [t.symbol for t in repo.list_tickers()] == ["S/USDT", "BTC/USDT"]
    repo.list_tickers()
    assert repo._exchange.calls == 1
