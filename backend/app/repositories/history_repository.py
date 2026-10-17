"""PostgreSQL persistence for prediction history and model-version metadata."""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.ml.inference import Prediction
from app.repositories.database import session_scope
from app.repositories.orm import ModelVersionRecord, PredictionRecord

logger = logging.getLogger(__name__)


class HistoryStorageError(Exception):
    """The database could not be reached or the operation failed."""


class HistoryNotConfiguredError(Exception):
    """No database is configured for this deployment."""


@dataclass(frozen=True)
class StoredPrediction:
    id: int
    symbol: str
    timeframe: str
    horizon_candles: int
    label: str
    probabilities: dict[str, float]
    prediction_time_utc: str
    latest_candle_utc: str
    model_version: str
    feature_version: str


class HistoryRepository(Protocol):
    def add(self, prediction: Prediction) -> int: ...

    def list(
        self, symbol: str, timeframe: str, limit: int, offset: int
    ) -> tuple[list[StoredPrediction], int]: ...

    def register_model(self, model_version: str, metadata: dict, evaluation: dict | None) -> None: ...

    def ping(self) -> None: ...


class PostgresHistoryRepository:
    def __init__(self, session_factory: sessionmaker[Session]):
        self._factory = session_factory

    def add(self, prediction: Prediction) -> int:
        probs = prediction.probabilities
        row = PredictionRecord(
            symbol=prediction.symbol,
            timeframe=prediction.timeframe,
            horizon_candles=prediction.horizon_candles,
            label=prediction.label,
            prob_up=probs.get("UP", 0.0),
            prob_down=probs.get("DOWN", 0.0),
            prob_sideways=probs.get("SIDEWAYS", 0.0),
            prediction_time_utc=datetime.fromisoformat(prediction.prediction_time_utc),
            latest_candle_utc=datetime.fromisoformat(prediction.latest_candle_utc),
            model_version=prediction.model_version,
            feature_version=prediction.feature_version,
            data_quality=prediction.data_quality,
        )
        try:
            with session_scope(self._factory) as session:
                session.add(row)
                session.flush()
                return row.id
        except SQLAlchemyError as err:
            logger.warning("could not save prediction: %s", type(err).__name__)
            raise HistoryStorageError("could not save prediction") from err

    def list(
        self, symbol: str, timeframe: str, limit: int, offset: int
    ) -> tuple[list[StoredPrediction], int]:
        where = (PredictionRecord.symbol == symbol, PredictionRecord.timeframe == timeframe)
        try:
            with session_scope(self._factory) as session:
                total = session.scalar(select(func.count()).select_from(PredictionRecord).where(*where))
                rows = session.scalars(
                    select(PredictionRecord)
                    .where(*where)
                    .order_by(PredictionRecord.prediction_time_utc.desc(), PredictionRecord.id.desc())
                    .limit(limit)
                    .offset(offset)
                ).all()
                items = [
                    StoredPrediction(
                        id=r.id,
                        symbol=r.symbol,
                        timeframe=r.timeframe,
                        horizon_candles=r.horizon_candles,
                        label=r.label,
                        probabilities={"UP": r.prob_up, "DOWN": r.prob_down, "SIDEWAYS": r.prob_sideways},
                        prediction_time_utc=r.prediction_time_utc.isoformat(),
                        latest_candle_utc=r.latest_candle_utc.isoformat(),
                        model_version=r.model_version,
                        feature_version=r.feature_version,
                    )
                    for r in rows
                ]
                return items, int(total or 0)
        except SQLAlchemyError as err:
            logger.warning("could not read history: %s", type(err).__name__)
            raise HistoryStorageError("could not read history") from err

    def register_model(self, model_version: str, metadata: dict, evaluation: dict | None) -> None:
        statement = (
            insert(ModelVersionRecord)
            .values(
                symbol=metadata["symbol"],
                timeframe=metadata["timeframe"],
                model_version=model_version,
                feature_version=metadata["feature_version"],
                horizon_candles=metadata["horizon_candles"],
                threshold=metadata["threshold"],
                trained_at_utc=datetime.fromisoformat(metadata["trained_at_utc"]),
                evaluation=evaluation,
            )
            .on_conflict_do_nothing(constraint="uq_model_versions_identity")
        )
        try:
            with session_scope(self._factory) as session:
                session.execute(statement)
        except SQLAlchemyError as err:
            logger.warning("could not register model version: %s", type(err).__name__)
            raise HistoryStorageError("could not register model version") from err

    def ping(self) -> None:
        try:
            with session_scope(self._factory) as session:
                session.execute(text("SELECT 1"))
        except SQLAlchemyError as err:
            raise HistoryStorageError("database unreachable") from err
