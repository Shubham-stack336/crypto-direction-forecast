import pandas as pd

from app.repositories.market_repository import MarketDataUnavailableError, MarketSymbolError
from tests.conftest import FakeMarketRepository


def test_live(make_client, live_market):
    client = make_client(FakeMarketRepository(live_market))
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_lists_loaded_models(make_client, live_market):
    client = make_client(FakeMarketRepository(live_market))
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "models": ["BTC/USDT 1h"], "database": "not_configured"}


def test_ready_fails_without_models(make_client, live_market, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    client = make_client(FakeMarketRepository(live_market), directory=empty)
    response = client.get("/health/ready")
    assert response.status_code == 503


def test_prediction_success(make_client, live_market):
    client = make_client(FakeMarketRepository(live_market))
    response = client.post("/api/v1/predictions/BTC-USDT")
    assert response.status_code == 200
    body = response.json()
    assert body["label"] in {"UP", "DOWN", "SIDEWAYS"}
    assert set(body["probabilities"]) == {"UP", "DOWN", "SIDEWAYS"}
    assert abs(sum(body["probabilities"].values()) - 1.0) < 1e-3
    assert body["symbol"] == "BTC/USDT"
    assert body["data_quality"]["dropped_incomplete_candle"] is True
    assert "not financial advice" in body["disclaimer"]
    assert body["saved"] is False


def test_prediction_accepts_explicit_body_and_lowercase_symbol(make_client, live_market):
    client = make_client(FakeMarketRepository(live_market))
    response = client.post("/api/v1/predictions/btc-usdt", json={"timeframe": "1h"})
    assert response.status_code == 200


def test_prediction_rejects_bad_timeframe_and_extra_fields(make_client, live_market):
    client = make_client(FakeMarketRepository(live_market))
    assert client.post("/api/v1/predictions/BTC-USDT", json={"timeframe": "4h"}).status_code == 422
    assert client.post("/api/v1/predictions/BTC-USDT", json={"hack": 1}).status_code == 422


def test_invalid_symbol_format_is_422(make_client, live_market):
    client = make_client(FakeMarketRepository(live_market))
    assert client.post("/api/v1/predictions/BTCUSDT").status_code in (404, 422)
    assert client.post("/api/v1/predictions/BTC-USDT-X").status_code in (404, 422)
    assert client.get("/api/v1/market/bad_symbol").status_code == 422


def test_prediction_without_model_is_404(make_client, live_market):
    client = make_client(FakeMarketRepository(live_market))
    response = client.post("/api/v1/predictions/ETH-USDT")
    assert response.status_code == 404


def test_prediction_unknown_symbol_on_exchange_is_404(make_client):
    client = make_client(FakeMarketRepository(error=MarketSymbolError("BTC/USDT")))
    assert client.post("/api/v1/predictions/BTC-USDT").status_code == 404


def test_prediction_provider_down_is_503_without_internal_details(make_client):
    client = make_client(FakeMarketRepository(error=MarketDataUnavailableError("socket 10.0.0.5 refused")))
    response = client.post("/api/v1/predictions/BTC-USDT")
    assert response.status_code == 503
    assert "10.0.0.5" not in response.text


def test_prediction_stale_data_is_503(make_client, market):
    client = make_client(FakeMarketRepository(market))
    response = client.post("/api/v1/predictions/BTC-USDT")
    assert response.status_code == 503
    assert "too old" in response.json()["detail"]


def test_prediction_insufficient_history_is_502(make_client, live_market):
    client = make_client(FakeMarketRepository(live_market.tail(50)))
    assert client.post("/api/v1/predictions/BTC-USDT").status_code == 502


def test_prediction_invalid_provider_data_is_502(make_client, live_market):
    broken = live_market.copy()
    broken.loc[200, "close"] = float("nan")
    client = make_client(FakeMarketRepository(broken))
    assert client.post("/api/v1/predictions/BTC-USDT").status_code == 502


def test_corrupted_model_is_503(make_client, live_market, model_dir):
    (model_dir / "btc_usdt_1h_rf.joblib").write_bytes(b"not a model")
    client = make_client(FakeMarketRepository(live_market))
    response = client.post("/api/v1/predictions/BTC-USDT")
    assert response.status_code == 503
    assert "not a model" not in response.text


def test_unexpected_error_returns_generic_500(make_client):
    client = make_client(FakeMarketRepository(error=RuntimeError("secret database password")))
    response = client.post("/api/v1/predictions/BTC-USDT")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "secret" not in response.text


def test_market_snapshot(make_client, live_market):
    client = make_client(FakeMarketRepository(live_market))
    response = client.get("/api/v1/market/BTC-USDT")
    assert response.status_code == 200
    body = response.json()
    assert body["is_fresh"] is True
    assert len(body["candles"]) == 24
    latest_open = pd.Timestamp.now(tz="UTC").floor("h")
    assert pd.Timestamp(body["latest_closed_candle_utc"]) == latest_open - pd.Timedelta(hours=1)


def test_market_stale_is_reported_not_hidden(make_client, market):
    client = make_client(FakeMarketRepository(market))
    response = client.get("/api/v1/market/BTC-USDT")
    assert response.status_code == 200
    assert response.json()["is_fresh"] is False


def test_market_provider_down_is_503(make_client):
    client = make_client(FakeMarketRepository(error=MarketDataUnavailableError("x")))
    assert client.get("/api/v1/market/BTC-USDT").status_code == 503


def test_model_status(make_client, live_market):
    client = make_client(FakeMarketRepository(live_market))
    response = client.get("/api/v1/models/BTC-USDT/status")
    assert response.status_code == 200
    body = response.json()
    assert body["model_version"] == "v1-2026-01-01"
    assert body["horizon_candles"] == 3
    assert body["evaluation"]["candidate_model"] == "synthetic-test-model"
    assert body["feature_columns"][0] == "ret_1"


def test_model_status_without_metrics_file(make_client, live_market, model_dir):
    (model_dir / "btc_usdt_1h_rf.metrics.json").unlink()
    client = make_client(FakeMarketRepository(live_market))
    assert client.get("/api/v1/models/BTC-USDT/status").json()["evaluation"] is None


def test_model_status_unknown_symbol_is_404(make_client, live_market):
    client = make_client(FakeMarketRepository(live_market))
    assert client.get("/api/v1/models/ETH-USDT/status").status_code == 404
