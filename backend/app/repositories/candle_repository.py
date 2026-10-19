"""PostgreSQL persistence for the most recent closed market candles."""
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.repositories.database import session_scope
from app.repositories.history_repository import HistoryStorageError
from app.repositories.orm import MarketCandleRecord

logger = logging.getLogger(__name__)

PRICE_COLUMNS = ("open", "high", "low", "close", "volume")


class PostgresCandleRepository:
    def __init__(self, session_factory: sessionmaker[Session]):
        self._factory = session_factory

    def save(self, symbol: str, timeframe: str, candles: list[dict]) -> None:
        if not candles:
            return
        rows = [
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "candle_time_utc": datetime.fromisoformat(c["timestamp"]),
                **{name: c[name] for name in PRICE_COLUMNS},
            }
            for c in candles
        ]
        statement = insert(MarketCandleRecord).values(rows)
        statement = statement.on_conflict_do_update(
            index_elements=["symbol", "timeframe", "candle_time_utc"],
            set_={name: statement.excluded[name] for name in PRICE_COLUMNS},
        )
        try:
            with session_scope(self._factory) as session:
                session.execute(statement)
        except SQLAlchemyError as err:
            logger.warning("could not save candles: %s", type(err).__name__)
            raise HistoryStorageError("could not save candles") from err

    def latest(self, symbol: str, timeframe: str, limit: int) -> list[dict]:
        try:
            with session_scope(self._factory) as session:
                rows = session.scalars(
                    select(MarketCandleRecord)
                    .where(
                        MarketCandleRecord.symbol == symbol,
                        MarketCandleRecord.timeframe == timeframe,
                    )
                    .order_by(MarketCandleRecord.candle_time_utc.desc())
                    .limit(limit)
                ).all()
                return [
                    {
                        "timestamp": r.candle_time_utc.isoformat(),
                        "open": r.open,
                        "high": r.high,
                        "low": r.low,
                        "close": r.close,
                        "volume": r.volume,
                    }
                    for r in reversed(rows)
                ]
        except SQLAlchemyError as err:
            logger.warning("could not read candles: %s", type(err).__name__)
            raise HistoryStorageError("could not read candles") from err
