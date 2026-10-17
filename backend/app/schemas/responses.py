from typing import Literal

from pydantic import BaseModel, ConfigDict


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timeframe: Literal["1h"] = "1h"


class HealthResponse(BaseModel):
    status: str


class ReadinessResponse(BaseModel):
    status: str
    models: list[str]
    database: str


class PredictionResponse(BaseModel):
    label: Literal["UP", "DOWN", "SIDEWAYS"]
    probabilities: dict[str, float]
    symbol: str
    timeframe: str
    horizon_candles: int
    prediction_time_utc: str
    latest_candle_utc: str
    model_version: str
    feature_version: str
    status: str
    data_quality: dict
    disclaimer: str
    saved: bool


class HistoryItem(BaseModel):
    id: int
    symbol: str
    timeframe: str
    horizon_candles: int
    label: Literal["UP", "DOWN", "SIDEWAYS"]
    probabilities: dict[str, float]
    prediction_time_utc: str
    latest_candle_utc: str
    model_version: str
    feature_version: str


class HistoryResponse(BaseModel):
    items: list[HistoryItem]
    total: int
    limit: int
    offset: int


class CandleOut(BaseModel):
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class MarketResponse(BaseModel):
    symbol: str
    timeframe: str
    latest_closed_candle_utc: str
    last_close: float
    data_age_minutes: float
    is_fresh: bool
    candles: list[CandleOut]


class ModelStatusResponse(BaseModel):
    symbol: str
    timeframe: str
    model_version: str
    feature_version: str
    feature_columns: list[str]
    classes: list[str]
    horizon_candles: int
    threshold: float
    trained_at_utc: str
    train_period: list[str]
    evaluation: dict | None
    disclaimer: str


class ErrorResponse(BaseModel):
    detail: str
