"""Business workflows. No FastAPI objects and no raw exchange/file/SQL access in here."""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd

from app.ml.inference import InvalidInputError, Prediction
from app.ml.validation import validate
from app.repositories.candle_repository import PostgresCandleRepository
from app.repositories.history_repository import (
    HistoryNotConfiguredError,
    HistoryRepository,
    HistoryStorageError,
    StoredPrediction,
)
from app.repositories.market_repository import MarketRepository
from app.repositories.model_repository import FileModelRepository

logger = logging.getLogger(__name__)

SNAPSHOT_CANDLES = 24
SAVED_CANDLES = 3


@dataclass(frozen=True)
class PredictionOutcome:
    prediction: Prediction
    saved: bool


@dataclass(frozen=True)
class HistoryPage:
    items: list[StoredPrediction]
    total: int
    limit: int
    offset: int


@dataclass(frozen=True)
class Readiness:
    models: list[str]
    database: str


@dataclass(frozen=True)
class MarketSnapshot:
    symbol: str
    timeframe: str
    latest_closed_candle_utc: str
    last_close: float
    data_age_minutes: float
    is_fresh: bool
    candles: list[dict]


@dataclass(frozen=True)
class SavedCandles:
    symbol: str
    timeframe: str
    candles: list[dict]


@dataclass(frozen=True)
class ModelStatus:
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


class PredictionService:
    def __init__(
        self,
        market_repo: MarketRepository,
        model_repo: FileModelRepository,
        candles_limit: int,
        max_staleness_candles: int,
        history_repo: HistoryRepository | None = None,
        candle_repo: PostgresCandleRepository | None = None,
    ):
        self._market = market_repo
        self._models = model_repo
        self._history = history_repo
        self._candles = candle_repo
        self._limit = candles_limit
        self._max_staleness = max_staleness_candles

    def predict(self, symbol: str, timeframe: str) -> PredictionOutcome:
        engine = self._models.get_engine(symbol, timeframe)
        candles = self._market.fetch_candles(symbol, timeframe, self._limit)
        prediction = engine.predict(candles)
        self._save_candles(candles, symbol, timeframe)
        return PredictionOutcome(prediction, self._save(prediction, engine, symbol, timeframe))

    def _save(self, prediction: Prediction, engine, symbol: str, timeframe: str) -> bool:
        """A storage failure must not hide a valid prediction; report it as saved=False."""
        if self._history is None:
            return False
        try:
            self._history.add(prediction)
        except HistoryStorageError:
            return False
        try:
            self._history.register_model(
                engine.model_version, engine.metadata, self._models.get_metrics(symbol, timeframe)
            )
        except HistoryStorageError:
            logger.warning("prediction saved but model version could not be registered")
        return True

    def _save_candles(self, raw: pd.DataFrame, symbol: str, timeframe: str) -> None:
        """Keep the last closed candles. A storage failure must not hide a valid prediction."""
        if self._candles is None:
            return
        try:
            closed = self._closed_candles(raw, timeframe, datetime.now(timezone.utc))
            self._candles.save(symbol, timeframe, self._rows(closed.tail(SAVED_CANDLES)))
        except (HistoryStorageError, InvalidInputError):
            logger.warning("latest candles could not be saved")

    def saved_candles(self, symbol: str, timeframe: str) -> SavedCandles:
        if self._candles is None:
            raise HistoryNotConfiguredError("no database configured")
        return SavedCandles(symbol, timeframe, self._candles.latest(symbol, timeframe, SAVED_CANDLES))

    @staticmethod
    def _closed_candles(raw: pd.DataFrame, timeframe: str, now: datetime) -> pd.DataFrame:
        df, problems = validate(raw.assign(timestamp=pd.to_datetime(raw["timestamp"], utc=True)))
        if problems:
            raise InvalidInputError("; ".join(problems))
        if df["timestamp"].iloc[-1] + pd.Timedelta(timeframe) > now:
            df = df.iloc[:-1]
        return df

    @staticmethod
    def _rows(df: pd.DataFrame) -> list[dict]:
        return [
            {
                "timestamp": row.timestamp.isoformat(),
                "open": float(row.open),
                "high": float(row.high),
                "low": float(row.low),
                "close": float(row.close),
                "volume": float(row.volume),
            }
            for row in df.itertuples()
        ]

    def history(self, symbol: str, timeframe: str, limit: int, offset: int) -> HistoryPage:
        if self._history is None:
            raise HistoryNotConfiguredError("no database configured")
        items, total = self._history.list(symbol, timeframe, limit, offset)
        return HistoryPage(items=items, total=total, limit=limit, offset=offset)

    def market_snapshot(self, symbol: str, timeframe: str, now: datetime | None = None) -> MarketSnapshot:
        now = now or datetime.now(timezone.utc)
        raw = self._market.fetch_candles(symbol, timeframe, self._limit)
        df = self._closed_candles(raw, timeframe, now)
        candle_length = pd.Timedelta(timeframe)

        latest = df.iloc[-1]
        age = now - (latest["timestamp"] + candle_length)
        recent = df.tail(SNAPSHOT_CANDLES)
        return MarketSnapshot(
            symbol=symbol,
            timeframe=timeframe,
            latest_closed_candle_utc=latest["timestamp"].isoformat(),
            last_close=float(latest["close"]),
            data_age_minutes=round(age.total_seconds() / 60, 1),
            is_fresh=age <= self._max_staleness * candle_length,
            candles=self._rows(recent),
        )

    def model_status(self, symbol: str, timeframe: str) -> ModelStatus:
        engine = self._models.get_engine(symbol, timeframe)
        meta = engine.metadata
        return ModelStatus(
            symbol=meta["symbol"],
            timeframe=meta["timeframe"],
            model_version=engine.model_version,
            feature_version=meta["feature_version"],
            feature_columns=list(meta["feature_columns"]),
            classes=list(meta["classes"]),
            horizon_candles=meta["horizon_candles"],
            threshold=meta["threshold"],
            trained_at_utc=meta["trained_at_utc"],
            train_period=list(meta["train_period"]),
            evaluation=self._models.get_metrics(symbol, timeframe),
        )

    def readiness(self) -> Readiness:
        if self._history is None:
            database = "not_configured"
        else:
            try:
                self._history.ping()
                database = "ok"
            except HistoryStorageError:
                database = "unavailable"
        return Readiness(models=self._models.available_models(), database=database)
