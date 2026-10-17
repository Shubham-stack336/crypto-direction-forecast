import pandas as pd
import pytest

from app.ml.inference import InvalidInputError, ModelNotFoundError
from app.repositories.model_repository import FileModelRepository
from app.services.prediction_service import PredictionService
from tests.conftest import FakeMarketRepository


def make_service(market_repo, model_dir):
    return PredictionService(
        market_repo,
        FileModelRepository(model_dir, max_staleness_candles=3),
        candles_limit=500,
        max_staleness_candles=3,
    )


def test_snapshot_freshness_follows_the_clock(market, model_dir, now):
    service = make_service(FakeMarketRepository(market), model_dir)
    fresh = service.market_snapshot("BTC/USDT", "1h", now=now)
    stale = service.market_snapshot("BTC/USDT", "1h", now=now + pd.Timedelta(hours=10))
    assert fresh.is_fresh is True
    assert stale.is_fresh is False
    assert fresh.data_age_minutes == 30.0


def test_snapshot_rejects_invalid_candles(market, model_dir, now):
    broken = market.copy()
    broken.loc[10, "high"] = 0.01
    service = make_service(FakeMarketRepository(broken), model_dir)
    with pytest.raises(InvalidInputError):
        service.market_snapshot("BTC/USDT", "1h", now=now)


def test_service_does_not_fetch_market_data_when_model_is_missing(market, model_dir):
    repo = FakeMarketRepository(market)
    service = make_service(repo, model_dir)
    with pytest.raises(ModelNotFoundError):
        service.predict("ETH/USDT", "1h")
    assert repo.calls == 0
