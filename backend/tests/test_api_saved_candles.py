from tests.conftest import FakeMarketRepository


def test_prediction_saves_the_last_three_closed_candles(make_client, live_market, candle_repo):
    client = make_client(FakeMarketRepository(live_market), candle_repo=candle_repo)
    assert client.post("/api/v1/predictions/BTC-USDT").status_code == 200

    response = client.get("/api/v1/market/BTC-USDT/saved")
    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "BTC/USDT" and body["timeframe"] == "1h"
    assert len(body["candles"]) == 3

    # the newest candle in live_market is still open, so it must not be stored
    closed_times = list(live_market["timestamp"].iloc[-4:-1].dt.strftime("%Y-%m-%dT%H:%M:%S+00:00"))
    assert [c["timestamp"] for c in body["candles"]] == closed_times


def test_repeated_predictions_do_not_duplicate_candles(make_client, live_market, candle_repo):
    client = make_client(FakeMarketRepository(live_market), candle_repo=candle_repo)
    client.post("/api/v1/predictions/BTC-USDT")
    client.post("/api/v1/predictions/BTC-USDT")
    assert len(client.get("/api/v1/market/BTC-USDT/saved").json()["candles"]) == 3


def test_saved_candles_empty_before_any_prediction(make_client, live_market, candle_repo):
    client = make_client(FakeMarketRepository(live_market), candle_repo=candle_repo)
    assert client.get("/api/v1/market/BTC-USDT/saved").json()["candles"] == []


def test_saved_candles_without_database_is_503(make_client, live_market):
    client = make_client(FakeMarketRepository(live_market))
    assert client.get("/api/v1/market/BTC-USDT/saved").status_code == 503
    assert client.post("/api/v1/predictions/BTC-USDT").status_code == 200
