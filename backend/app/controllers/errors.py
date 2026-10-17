"""Translate domain errors into safe HTTP errors. Internal details go to logs, not clients."""
import logging
from typing import Callable, TypeVar

from fastapi import HTTPException

from app.core.symbols import normalize_symbol
from app.ml.inference import (
    IncompatibleModelError,
    InsufficientHistoryError,
    InvalidInputError,
    ModelNotFoundError,
    StaleDataError,
)
from app.repositories.history_repository import HistoryNotConfiguredError, HistoryStorageError
from app.repositories.market_repository import MarketDataUnavailableError, MarketSymbolError

logger = logging.getLogger(__name__)
T = TypeVar("T")

_MAPPING: list[tuple[type[Exception], int, str]] = [
    (ModelNotFoundError, 404, "No trained model is available for this symbol and timeframe"),
    (MarketSymbolError, 404, "This symbol was not found on the market data provider"),
    (IncompatibleModelError, 503, "The model for this symbol is currently unavailable"),
    (MarketDataUnavailableError, 503, "Market data provider is currently unavailable"),
    (StaleDataError, 503, "Market data is too old to produce a reliable prediction"),
    (HistoryNotConfiguredError, 503, "Prediction history storage is not configured"),
    (HistoryStorageError, 503, "Prediction history storage is currently unavailable"),
    (InsufficientHistoryError, 502, "Market data provider returned too little history"),
    (InvalidInputError, 502, "Market data provider returned invalid data"),
]


def to_http_exception(exc: Exception) -> HTTPException:
    for exc_type, status_code, message in _MAPPING:
        if isinstance(exc, exc_type):
            logger.warning("request failed (%s): %s", type(exc).__name__, exc)
            return HTTPException(status_code=status_code, detail=message)
    logger.exception("unexpected error", exc_info=exc)
    return HTTPException(status_code=500, detail="Internal server error")


def run_service(action: Callable[[], T]) -> T:
    try:
        return action()
    except HTTPException:
        raise
    except Exception as exc:
        raise to_http_exception(exc) from exc


def parse_symbol(slug: str) -> str:
    try:
        return normalize_symbol(slug)
    except ValueError as err:
        raise HTTPException(status_code=422, detail="Invalid symbol format, use e.g. BTC-USDT") from err
