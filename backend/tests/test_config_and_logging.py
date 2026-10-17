import json
import logging

import pytest
from pydantic import ValidationError

from app.core.config import Settings, normalize_database_url
from app.core.log import JsonFormatter
from tests.conftest import FakeMarketRepository


def test_database_url_variants_are_normalised_for_psycopg3():
    assert normalize_database_url("postgres://u:p@h:5432/d") == "postgresql+psycopg://u:p@h:5432/d"
    assert normalize_database_url("postgresql://u:p@h/d") == "postgresql+psycopg://u:p@h/d"
    assert normalize_database_url("postgresql+psycopg://u:p@h/d") == "postgresql+psycopg://u:p@h/d"


def test_empty_database_url_means_not_configured():
    assert Settings(_env_file=None, database_url="  ").database_url is None


def test_production_requires_a_database():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="production")
    assert Settings(_env_file=None, environment="production", database_url="postgres://u:p@h/d")


def test_wildcard_cors_origin_is_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, cors_origins=["*"])


def test_out_of_range_settings_are_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, market_candles_limit=5)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, market_max_retries=0)


def test_json_formatter_emits_structured_fields():
    record = logging.LogRecord("app.request", logging.INFO, __file__, 1, "request", None, None)
    record.request_id = "abc"
    record.status = 200
    entry = json.loads(JsonFormatter().format(record))
    assert entry["message"] == "request" and entry["request_id"] == "abc" and entry["status"] == 200
    assert entry["level"] == "INFO"


def test_every_response_gets_a_request_id_and_safe_headers(make_client, live_market):
    client = make_client(FakeMarketRepository(live_market))
    health = client.get("/health/live")
    assert len(health.headers["x-request-id"]) == 32
    assert health.headers["x-content-type-options"] == "nosniff"
    assert "cache-control" not in health.headers

    market = client.get("/api/v1/market/BTC-USDT")
    assert market.headers["cache-control"] == "no-store"
    assert market.headers["x-request-id"] != health.headers["x-request-id"]


def test_requests_are_logged_with_status_and_duration(make_client, live_market, caplog):
    client = make_client(FakeMarketRepository(live_market))
    with caplog.at_level(logging.INFO, logger="app.request"):
        client.get("/health/live")
    record = next(r for r in caplog.records if r.name == "app.request")
    assert record.path == "/health/live" and record.status == 200 and record.duration_ms >= 0


def test_cors_allows_only_configured_origins(make_client, live_market, monkeypatch):
    from app.core import config

    monkeypatch.setattr(config, "get_settings", lambda: Settings(_env_file=None, cors_origins=["https://app.example"]))
    import app.main as main

    monkeypatch.setattr(main, "get_settings", config.get_settings)
    client = make_client(FakeMarketRepository(live_market))
    allowed = client.get("/health/live", headers={"Origin": "https://app.example"})
    denied = client.get("/health/live", headers={"Origin": "https://evil.example"})
    assert allowed.headers.get("access-control-allow-origin") == "https://app.example"
    assert "access-control-allow-origin" not in denied.headers
