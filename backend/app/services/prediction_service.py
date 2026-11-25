"""Business workflows. No FastAPI objects and no raw exchange/file/SQL access in here."""
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone

import pandas as pd

from app.core.cache import CacheStore
from app.ml.inference import InvalidInputError, Prediction, PredictionError
from app.ml.validation import validate
from app.repositories.candle_repository import PostgresCandleRepository
from app.repositories.history_repository import (
    HistoryNotConfiguredError,
    HistoryRepository,
    HistoryStorageError,
    SHADOW_PREFIX,
    StoredPrediction,
)
from app.repositories.market_repository import MarketDataUnavailableError, MarketRepository, MarketSymbolError, Ticker
from app.repositories.model_repository import FileModelRepository

logger = logging.getLogger(__name__)

SNAPSHOT_CANDLES = 24
SAVED_CANDLES = 3
TRACK_RECORD_ROWS = 200
SCAN_MAX = 20
SCAN_TTL_S = 300
SCAN_THREADS = 4


@dataclass(frozen=True)
class PredictionOutcome:
    prediction: Prediction
    saved: bool


@dataclass(frozen=True)
class Coin:
    symbol: str
    last: float
    change_pct: float
    quote_volume: float
    model: str


@dataclass(frozen=True)
class ScanRow:
    symbol: str
    last: float
    change_pct: float
    label: str
    probabilities: dict[str, float]
    model: str
    confidence: dict | None = None


@dataclass(frozen=True)
class CheckedForecast:
    id: int
    latest_candle_utc: str
    label: str
    actual: str
    return_pct: float
    correct: bool


@dataclass(frozen=True)
class TrackRecord:
    symbol: str
    checked: int
    correct: int
    pending: int
    not_checkable: int
    items: list[CheckedForecast]


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
    model_kind: str = "dedicated"


class PredictionService:
    def __init__(
        self,
        market_repo: MarketRepository,
        model_repo: FileModelRepository,
        candles_limit: int,
        max_staleness_candles: int,
        history_repo: HistoryRepository | None = None,
        candle_repo: PostgresCandleRepository | None = None,
        cache: CacheStore | None = None,
    ):
        self._market = market_repo
        self._models = model_repo
        self._history = history_repo
        self._candles = candle_repo
        self._cache = cache
        self._limit = candles_limit
        self._max_staleness = max_staleness_candles

    def predict(self, symbol: str, timeframe: str) -> PredictionOutcome:
        engine = self._models.get_engine(symbol, timeframe)
        candles = self._market.fetch_candles(symbol, timeframe, self._limit)
        prediction = replace(engine.predict(candles), symbol=symbol)
        if source := candles.attrs.get("source"):
            prediction = replace(prediction, data_quality={**prediction.data_quality, "source": source})
        self._save_candles(candles, symbol, timeframe)
        self._save_shadow(candles, symbol, timeframe)
        return PredictionOutcome(prediction, self._save(prediction, engine, symbol, timeframe))

    def _save_shadow(self, candles: pd.DataFrame, symbol: str, timeframe: str) -> None:
        """Let the challenger forecast the same candle. Users never see it and it can never break a request."""
        engine = self._models.get_challenger(symbol, timeframe) if self._history is not None else None
        if engine is None:
            return
        try:
            shadow = engine.predict(candles)
            self._history.add(replace(shadow, symbol=symbol, model_version=SHADOW_PREFIX + shadow.model_version))
        except (PredictionError, HistoryStorageError) as err:
            logger.warning("shadow forecast skipped: %s", err)

    def _kind(self, symbol: str, timeframe: str) -> str:
        return "dedicated" if self._models.model_symbol(symbol, timeframe) == symbol else "universal"

    def coins(self, timeframe: str) -> list[Coin]:
        return [self._coin(t, timeframe) for t in self._market.list_tickers()]

    def _coin(self, t: Ticker, timeframe: str) -> Coin:
        return Coin(t.symbol, t.last, t.change_pct, t.quote_volume, self._kind(t.symbol, timeframe))

    def scan(self, timeframe: str, limit: int) -> list[ScanRow]:
        """Forecast the busiest coins. Nothing is saved; a coin that cannot be forecast is left out."""
        if self._cache is None:
            return self._run_scan(timeframe, limit)
        cached = self._cache.get(self._scan_key(timeframe))
        rows = [ScanRow(**r) for r in json.loads(cached)] if cached else self.refresh_scan(timeframe)
        return rows[:limit]

    @staticmethod
    def _scan_key(timeframe: str) -> str:
        # The hour is part of the key: a new candle means a new forecast.
        return f"scan:{timeframe}:{int(datetime.now(timezone.utc).timestamp() // 3600)}"

    def refresh_scan(self, timeframe: str = "1h") -> list[ScanRow]:
        """Also called in the background so that users find a ready result."""
        key = self._scan_key(timeframe)
        rows = self._run_scan(timeframe, SCAN_MAX)
        self._cache.set(key, json.dumps([asdict(r) for r in rows]).encode(), SCAN_TTL_S)
        return rows

    def _run_scan(self, timeframe: str, limit: int) -> list[ScanRow]:
        tickers = self._market.list_tickers()[:limit]
        with ThreadPoolExecutor(SCAN_THREADS) as pool:
            rows = [r for r in pool.map(lambda t: self._scan_one(t, timeframe), tickers) if r is not None]
        if not rows:
            raise MarketDataUnavailableError("no coin could be scanned")
        return rows

    def _scan_one(self, t: Ticker, timeframe: str) -> ScanRow | None:
        try:
            engine = self._models.get_engine(t.symbol, timeframe)
            p = engine.predict(self._market.fetch_candles(t.symbol, timeframe, self._limit))
        except (PredictionError, MarketDataUnavailableError, MarketSymbolError) as err:
            logger.warning("scan skipped %s: %s", t.symbol, err)
            return None
        kind = self._kind(t.symbol, timeframe)
        return ScanRow(t.symbol, t.last, t.change_pct, p.label, p.probabilities, kind, p.confidence)

    def track_record(self, symbol: str, timeframe: str, now: datetime | None = None) -> TrackRecord:
        """Compare saved forecasts with what the price then did. One forecast per candle counts."""
        if self._history is None:
            raise HistoryNotConfiguredError("no database configured")
        now = now or datetime.now(timezone.utc)
        saved, _ = self._history.list(symbol, timeframe, TRACK_RECORD_ROWS, 0, include_shadow=True)
        by_candle = {}
        for item in saved:  # newest first, so the latest forecast for a candle wins
            by_candle.setdefault((item.latest_candle_utc, item.model_version), item)
        if not by_candle:
            return TrackRecord(symbol, 0, 0, 0, 0, [])

        length = pd.Timedelta(timeframe)
        close_at = None
        items, outcomes, pending, not_checkable = [], {}, 0, 0
        for item in by_candle.values():
            start = pd.Timestamp(item.latest_candle_utc)
            end = start + item.horizon_candles * length
            shadow = item.model_version.startswith(SHADOW_PREFIX)
            if item.outcome_label is not None:
                actual, change = item.outcome_label, item.outcome_return
            elif end + length > now:
                pending += not shadow
                continue
            else:
                if close_at is None:  # only ask the exchange when something is still unresolved
                    raw = self._market.fetch_candles(symbol, timeframe, self._limit)
                    closed = self._closed_candles(raw, timeframe, now)
                    close_at = dict(zip(closed["timestamp"], closed["close"]))
                # Judge a forecast by the threshold it was made with, not by today's model.
                if item.threshold is None or start not in close_at or end not in close_at:
                    not_checkable += not shadow
                    continue
                change = float(close_at[end] / close_at[start] - 1)
                actual = "UP" if change > item.threshold else "DOWN" if change < -item.threshold else "SIDEWAYS"
                outcomes[item.id] = (actual, change)
            if shadow:
                continue
            items.append(
                CheckedForecast(
                    item.id, item.latest_candle_utc, item.label, actual,
                    round(change * 100, 3), actual == item.label,
                )
            )
        try:
            self._history.save_outcomes(outcomes)
        except HistoryStorageError:
            logger.warning("outcomes could not be saved; they will be computed again")
        return TrackRecord(
            symbol, len(items), sum(i.correct for i in items), pending, not_checkable, items[:20]
        )

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

    def market_snapshot(
        self, symbol: str, timeframe: str, now: datetime | None = None, hours: int = SNAPSHOT_CANDLES
    ) -> MarketSnapshot:
        now = now or datetime.now(timezone.utc)
        raw = self._market.fetch_candles(symbol, timeframe, self._limit)
        df = self._closed_candles(raw, timeframe, now)
        candle_length = pd.Timedelta(timeframe)

        latest = df.iloc[-1]
        age = now - (latest["timestamp"] + candle_length)
        recent = df.tail(hours)
        return MarketSnapshot(
            symbol=symbol,
            timeframe=timeframe,
            latest_closed_candle_utc=latest["timestamp"].isoformat(),
            last_close=float(latest["close"]),
            data_age_minutes=round(age.total_seconds() / 60, 1),
            is_fresh=age <= self._max_staleness * candle_length,
            candles=self._rows(recent),
        )

    def record_summary(self) -> dict:
        if self._history is None:
            raise HistoryNotConfiguredError("no database configured")
        return self._history.outcome_summary()

    def auto_forecast(self, symbols: list[str], timeframe: str = "1h") -> None:
        """Save a forecast per candle and check old ones, so the public record does not depend on who clicks."""
        for symbol in symbols:
            try:
                self.predict(symbol, timeframe)
                self.track_record(symbol, timeframe)
            except (PredictionError, MarketDataUnavailableError, MarketSymbolError, HistoryStorageError) as err:
                logger.warning("auto forecast skipped %s: %s", symbol, err)

    def model_status(self, symbol: str, timeframe: str) -> ModelStatus:
        engine = self._models.get_engine(symbol, timeframe)
        meta = engine.metadata
        return ModelStatus(
            symbol=symbol,
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
            model_kind=self._kind(symbol, timeframe),
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
