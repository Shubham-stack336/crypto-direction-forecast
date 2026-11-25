"""Composition root: the only place that wires repositories -> services -> controllers."""
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from fastapi import Depends
from sqlalchemy import Engine

from app.background import BackgroundWorker
from app.controllers.coin_controller import CoinController
from app.controllers.health_controller import HealthController
from app.controllers.market_controller import MarketController
from app.controllers.model_controller import ModelController
from app.controllers.prediction_controller import PredictionController
from app.core.cache import CacheStore, MemoryStore, RedisStore
from app.core.config import Settings, get_settings
from app.repositories.database import create_db_engine, create_session_factory
from app.repositories.candle_repository import PostgresCandleRepository
from app.repositories.history_repository import HistoryRepository, PostgresHistoryRepository
from app.repositories.market_repository import CcxtMarketRepository, MarketRepository
from app.repositories.model_repository import FileModelRepository
from app.repositories.resilient_market import CachingMarketRepository, FailoverMarketRepository
from app.services.prediction_service import PredictionService


@lru_cache
def get_cache_store() -> CacheStore:
    url = get_settings().redis_url
    return RedisStore.from_url(url) if url else MemoryStore()


@lru_cache
def get_market_repository() -> MarketRepository:
    settings = get_settings()
    repos = [
        (name, CcxtMarketRepository(name, settings.market_timeout_ms, settings.market_max_retries))
        for name in [settings.exchange_id, *settings.fallback_exchange_ids]
    ]
    return CachingMarketRepository(FailoverMarketRepository(repos), get_cache_store())


@lru_cache
def get_model_repository() -> FileModelRepository:
    settings = get_settings()
    challenger_dir = settings.model_dir / "challenger"
    challenger = FileModelRepository(challenger_dir, settings.max_staleness_candles) if challenger_dir.is_dir() else None
    return FileModelRepository(
        settings.model_dir, settings.max_staleness_candles, challenger, settings.serve_challenger
    )


@lru_cache
def get_db_engine() -> Engine | None:
    settings = get_settings()
    if not settings.database_url:
        return None
    return create_db_engine(
        settings.database_url,
        connect_timeout_s=settings.db_connect_timeout_s,
        statement_timeout_ms=settings.db_statement_timeout_ms,
        pool_size=settings.db_pool_size,
    )


@lru_cache
def get_history_repository() -> HistoryRepository | None:
    engine = get_db_engine()
    if engine is None:
        return None
    return PostgresHistoryRepository(create_session_factory(engine))


@lru_cache
def get_candle_repository() -> PostgresCandleRepository | None:
    engine = get_db_engine()
    if engine is None:
        return None
    return PostgresCandleRepository(create_session_factory(engine))


def dispose_db_engine() -> None:
    if get_db_engine.cache_info().currsize:
        engine = get_db_engine()
        if engine is not None:
            engine.dispose()


def get_prediction_service(
    market_repo: MarketRepository = Depends(get_market_repository),
    model_repo: FileModelRepository = Depends(get_model_repository),
    history_repo: HistoryRepository | None = Depends(get_history_repository),
    candle_repo: PostgresCandleRepository | None = Depends(get_candle_repository),
    cache: CacheStore = Depends(get_cache_store),
    settings: Settings = Depends(get_settings),
) -> PredictionService:
    return PredictionService(
        market_repo,
        model_repo,
        candles_limit=settings.market_candles_limit,
        max_staleness_candles=settings.max_staleness_candles,
        history_repo=history_repo,
        candle_repo=candle_repo,
        cache=cache,
    )


def build_background_worker() -> BackgroundWorker:
    settings = get_settings()
    history = get_history_repository()
    service = get_prediction_service(
        get_market_repository(), get_model_repository(), history, get_candle_repository(), get_cache_store(), settings
    )
    purge = None
    if history is not None and settings.history_retention_days:
        age = timedelta(days=settings.history_retention_days)

        def purge():
            history.purge_older_than(datetime.now(timezone.utc) - age)

    auto = None
    if history is not None and settings.auto_forecast_symbols:

        def auto():
            service.auto_forecast(settings.auto_forecast_symbols)

    return BackgroundWorker(get_cache_store(), service.refresh_scan, purge, auto_forecast=auto)


def get_health_controller(service: PredictionService = Depends(get_prediction_service)) -> HealthController:
    return HealthController(service)


def get_coin_controller(service: PredictionService = Depends(get_prediction_service)) -> CoinController:
    return CoinController(service)


def get_market_controller(service: PredictionService = Depends(get_prediction_service)) -> MarketController:
    return MarketController(service)


def get_prediction_controller(service: PredictionService = Depends(get_prediction_service)) -> PredictionController:
    return PredictionController(service)


def get_model_controller(service: PredictionService = Depends(get_prediction_service)) -> ModelController:
    return ModelController(service)
