"""Database persistence for prediction history and model-version metadata."""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.ml.inference import Prediction
from app.repositories.database import dialect_insert, session_scope
from app.repositories.orm import ModelVersionRecord, PredictionRecord

logger = logging.getLogger(__name__)
IDENTITY_COLUMNS = ("symbol", "timeframe", "latest_candle_utc", "model_version")


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
    threshold: float | None = None
    outcome_label: str | None = None
    outcome_return: float | None = None


class HistoryRepository(Protocol):
    def add(self, prediction: Prediction) -> int: ...

    def list(
        self, symbol: str, timeframe: str, limit: int, offset: int
    ) -> tuple[list[StoredPrediction], int]: ...

    def register_model(self, model_version: str, metadata: dict, evaluation: dict | None) -> None: ...

    def save_outcomes(self, outcomes: dict[int, tuple[str, float]]) -> None: ...

    def ping(self) -> None: ...


class PostgresHistoryRepository:
    def __init__(self, session_factory: sessionmaker[Session]):
        self._factory = session_factory

    def add(self, prediction: Prediction) -> int:
        probs = prediction.probabilities
        values = dict(
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
            threshold=prediction.threshold,
        )
        try:
            with session_scope(self._factory) as session:
                statement = dialect_insert(session, PredictionRecord).values(**values)
                updated = {k: statement.excluded[k] for k in values if k not in IDENTITY_COLUMNS}
                return session.execute(
                    statement.on_conflict_do_update(
                        index_elements=list(IDENTITY_COLUMNS), set_=updated
                    ).returning(PredictionRecord.id)
                ).scalar_one()
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
                        threshold=r.threshold,
                        outcome_label=r.outcome_label,
                        outcome_return=r.outcome_return,
                    )
                    for r in rows
                ]
                return items, int(total or 0)
        except SQLAlchemyError as err:
            logger.warning("could not read history: %s", type(err).__name__)
            raise HistoryStorageError("could not read history") from err

    def register_model(self, model_version: str, metadata: dict, evaluation: dict | None) -> None:
        values = {
            "symbol": metadata["symbol"],
            "timeframe": metadata["timeframe"],
            "model_version": model_version,
            "feature_version": metadata["feature_version"],
            "horizon_candles": metadata["horizon_candles"],
            "threshold": metadata["threshold"],
            "trained_at_utc": datetime.fromisoformat(metadata["trained_at_utc"]),
            "evaluation": evaluation,
        }
        try:
            with session_scope(self._factory) as session:
                session.execute(
                    dialect_insert(session, ModelVersionRecord)
                    .values(**values)
                    .on_conflict_do_nothing(index_elements=["symbol", "timeframe", "model_version"])
                )
        except SQLAlchemyError as err:
            logger.warning("could not register model version: %s", type(err).__name__)
            raise HistoryStorageError("could not register model version") from err

    def save_outcomes(self, outcomes: dict[int, tuple[str, float]]) -> None:
        """Write what really happened, once, so the record survives after the candles are gone."""
        if not outcomes:
            return
        try:
            with session_scope(self._factory) as session:
                for row_id, (label, change) in outcomes.items():
                    session.execute(
                        update(PredictionRecord)
                        .where(PredictionRecord.id == row_id, PredictionRecord.outcome_label.is_(None))
                        .values(outcome_label=label, outcome_return=change)
                    )
        except SQLAlchemyError as err:
            logger.warning("could not save outcomes: %s", type(err).__name__)
            raise HistoryStorageError("could not save outcomes") from err

    def purge_older_than(self, cutoff: datetime) -> int:
        try:
            with session_scope(self._factory) as session:
                return session.execute(
                    delete(PredictionRecord).where(PredictionRecord.prediction_time_utc < cutoff)
                ).rowcount
        except SQLAlchemyError as err:
            raise HistoryStorageError("could not purge history") from err

    def ping(self) -> None:
        try:
            with session_scope(self._factory) as session:
                session.execute(text("SELECT 1"))
        except SQLAlchemyError as err:
            raise HistoryStorageError("database unreachable") from err
