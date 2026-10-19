"""SQLAlchemy table definitions (PostgreSQL)."""
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    Identity,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.repositories.database import Base


class PredictionRecord(Base):
    __tablename__ = "predictions"
    __table_args__ = (
        CheckConstraint("label IN ('UP', 'DOWN', 'SIDEWAYS')", name="ck_predictions_label"),
        CheckConstraint(
            "prob_up BETWEEN 0 AND 1 AND prob_down BETWEEN 0 AND 1 AND prob_sideways BETWEEN 0 AND 1",
            name="ck_predictions_probabilities",
        ),
        Index(
            "ix_predictions_symbol_timeframe_time",
            "symbol",
            "timeframe",
            "prediction_time_utc",
            "id",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    horizon_candles: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(10), nullable=False)
    prob_up: Mapped[float] = mapped_column(Float, nullable=False)
    prob_down: Mapped[float] = mapped_column(Float, nullable=False)
    prob_sideways: Mapped[float] = mapped_column(Float, nullable=False)
    prediction_time_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    latest_candle_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    feature_version: Mapped[str] = mapped_column(String(20), nullable=False)
    data_quality: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ModelVersionRecord(Base):
    __tablename__ = "model_versions"
    __table_args__ = (
        UniqueConstraint("symbol", "timeframe", "model_version", name="uq_model_versions_identity"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    feature_version: Mapped[str] = mapped_column(String(20), nullable=False)
    horizon_candles: Mapped[int] = mapped_column(Integer, nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    trained_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    evaluation: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MarketCandleRecord(Base):
    __tablename__ = "market_candles"


    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    timeframe: Mapped[str] = mapped_column(String(10), primary_key=True)
    candle_time_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False)
    saved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )