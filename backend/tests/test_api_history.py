from tests.conftest import FakeMarketRepository


def test_prediction_is_saved_and_appears_in_history(make_client, live_market, history_repo):
    client = make_client(FakeMarketRepository(live_market), history_repo=history_repo)

    created = client.post("/api/v1/predictions/BTC-USDT")
    assert created.status_code == 200
    assert created.json()["saved"] is True

    history = client.get("/api/v1/predictions/BTC-USDT/history")
    assert history.status_code == 200
    body = history.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["label"] == created.json()["label"]
    assert item["probabilities"] == created.json()["probabilities"]
    assert item["model_version"] == created.json()["model_version"]
    assert item["symbol"] == "BTC/USDT" and item["horizon_candles"] == 3


def test_history_is_newest_first_with_pagination(make_client, live_market, history_repo):
    client = make_client(FakeMarketRepository(live_market), history_repo=history_repo)
    for _ in range(3):
        client.post("/api/v1/predictions/BTC-USDT")

    body = client.get("/api/v1/predictions/BTC-USDT/history?limit=2").json()
    assert body["total"] == 3 and len(body["items"]) == 2 and body["limit"] == 2
    times = [i["prediction_time_utc"] for i in body["items"]]
    assert times == sorted(times, reverse=True)

    last = client.get("/api/v1/predictions/BTC-USDT/history?limit=2&offset=2").json()
    assert len(last["items"]) == 1


def test_empty_history_is_an_empty_list(make_client, live_market, history_repo):
    client = make_client(FakeMarketRepository(live_market), history_repo=history_repo)
    response = client.get("/api/v1/predictions/BTC-USDT/history")
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 50, "offset": 0}


def test_history_query_limits_are_enforced(make_client, live_market, history_repo):
    client = make_client(FakeMarketRepository(live_market), history_repo=history_repo)
    base = "/api/v1/predictions/BTC-USDT/history"
    assert client.get(f"{base}?limit=0").status_code == 422
    assert client.get(f"{base}?limit=201").status_code == 422
    assert client.get(f"{base}?offset=-1").status_code == 422
    assert client.get(f"{base}?timeframe=4h").status_code == 422


def test_history_without_database_is_503(make_client, live_market):
    client = make_client(FakeMarketRepository(live_market))
    response = client.get("/api/v1/predictions/BTC-USDT/history")
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]


def test_database_outage_does_not_hide_the_prediction(make_client, live_market, dead_history_repo):
    client = make_client(FakeMarketRepository(live_market), history_repo=dead_history_repo)

    prediction = client.post("/api/v1/predictions/BTC-USDT")
    assert prediction.status_code == 200
    assert prediction.json()["saved"] is False

    history = client.get("/api/v1/predictions/BTC-USDT/history")
    assert history.status_code == 503
    assert "127.0.0.1" not in history.text


def test_readiness_reports_database(make_client, live_market, history_repo, dead_history_repo):
    ok = make_client(FakeMarketRepository(live_market), history_repo=history_repo).get("/health/ready")
    assert ok.status_code == 200 and ok.json()["database"] == "ok"

    down = make_client(FakeMarketRepository(live_market), history_repo=dead_history_repo).get("/health/ready")
    assert down.status_code == 503


def test_model_version_is_registered_once(make_client, live_market, history_repo, db_engine):
    from sqlalchemy import text

    client = make_client(FakeMarketRepository(live_market), history_repo=history_repo)
    client.post("/api/v1/predictions/BTC-USDT")
    client.post("/api/v1/predictions/BTC-USDT")
    with db_engine.connect() as connection:
        rows = connection.execute(text("SELECT model_version, evaluation FROM model_versions")).all()
    assert len(rows) == 1
    assert rows[0][0] == "v1-2026-01-01"
    assert rows[0][1]["candidate_model"] == "synthetic-test-model"
