"""Caching, failover and a circuit breaker around the exchange repositories."""
import json
import logging
import threading
import time
from dataclasses import asdict
from typing import Callable

import pandas as pd

from app.core.cache import CacheStore
from app.core.metrics import EXCHANGE_FAILURES
from app.repositories.market_repository import COLUMNS, MarketDataUnavailableError, MarketRepository, Ticker

logger = logging.getLogger(__name__)

CANDLE_TTL_S = 120
TICKER_FRESH_S = 60
TICKER_STALE_S = 900
BREAKER_FAILURES = 3
BREAKER_OPEN_S = 60
MAX_PARALLEL_CALLS = 4


class _Breaker:
    """After repeated failures skip a provider for a while instead of making every user wait for it."""

    def __init__(self, clock: Callable[[], float]):
        self._clock = clock
        self._failures = 0
        self._open_until = float("-inf")
        self._lock = threading.Lock()

    def allows(self) -> bool:
        return self._clock() >= self._open_until

    def success(self) -> None:
        with self._lock:
            self._failures = 0

    def failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= BREAKER_FAILURES:
                self._open_until = self._clock() + BREAKER_OPEN_S
                self._failures = 0


class FailoverMarketRepository:
    """Ask the exchanges in order. An unknown symbol is an answer, so it does not trigger failover."""

    def __init__(self, repos: list[tuple[str, MarketRepository]], clock: Callable[[], float] = time.monotonic):
        self._repos = [(name, repo, _Breaker(clock)) for name, repo in repos]
        self._slots = threading.BoundedSemaphore(MAX_PARALLEL_CALLS)

    def _first(self, action: Callable[[MarketRepository], object]):
        for name, repo, breaker in self._repos:
            if not breaker.allows():
                continue
            try:
                with self._slots:
                    result = action(repo)
            except MarketDataUnavailableError:
                EXCHANGE_FAILURES.labels(name).inc()
                breaker.failure()
                logger.warning("exchange %s failed", name)
                continue
            breaker.success()
            return name, result
        raise MarketDataUnavailableError("no exchange is available")

    def fetch_candles(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        name, df = self._first(lambda repo: repo.fetch_candles(symbol, timeframe, limit))
        df.attrs["source"] = name
        return df

    def list_tickers(self) -> list[Ticker]:
        return self._first(lambda repo: repo.list_tickers())[1]


class CachingMarketRepository:
    def __init__(self, inner: MarketRepository, store: CacheStore, wall: Callable[[], float] = time.time):
        self._inner = inner
        self._store = store
        self._wall = wall
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    def _lock(self, key: str) -> threading.Lock:
        with self._guard:
            if len(self._locks) > 2_000:
                self._locks = {k: v for k, v in self._locks.items() if v.locked()}
            return self._locks.setdefault(key, threading.Lock())

    def fetch_candles(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        # The candle number is part of the key: an unfinished candle cached before the hour must
        # never be read as a finished one after it.
        length = int(pd.Timedelta(timeframe).total_seconds())
        name = f"candles:{symbol}:{timeframe}:{limit}"
        with_hour = f"{name}:{int(self._wall() // length)}"
        cached = self._read_candles(with_hour)
        if cached is not None:
            return cached
        with self._lock(name):  # one caller fetches, the rest reuse the result
            cached = self._read_candles(with_hour)
            if cached is not None:
                return cached
            df = self._inner.fetch_candles(symbol, timeframe, limit)
            milliseconds = (df["timestamp"] - pd.Timestamp(0, tz="UTC")) // pd.Timedelta(milliseconds=1)
            rows = df.assign(timestamp=milliseconds)[COLUMNS].values.tolist()
            payload = {"source": df.attrs.get("source"), "rows": rows}
            self._store.set(with_hour, json.dumps(payload).encode(), CANDLE_TTL_S)
            return df

    def _read_candles(self, key: str) -> pd.DataFrame | None:
        raw = self._store.get(key)
        if raw is None:
            return None
        payload = json.loads(raw)
        df = pd.DataFrame(payload["rows"], columns=COLUMNS)
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        if payload["source"]:
            df.attrs["source"] = payload["source"]
        return df

    def list_tickers(self) -> list[Ticker]:
        """Slightly old prices are served while one caller refreshes; nobody queues behind a slow exchange."""
        cached = self._read_tickers()
        if cached and self._wall() - cached[0] < TICKER_FRESH_S:
            return cached[1]
        lock = self._lock("tickers")
        if not lock.acquire(blocking=cached is None):
            return cached[1]
        try:
            latest = self._read_tickers()
            if latest and self._wall() - latest[0] < TICKER_FRESH_S:
                return latest[1]
            try:
                tickers = self._inner.list_tickers()
            except MarketDataUnavailableError:
                if cached:
                    return cached[1]
                raise
            payload = {"at": self._wall(), "items": [asdict(t) for t in tickers]}
            self._store.set("tickers", json.dumps(payload).encode(), TICKER_STALE_S)
            return tickers
        finally:
            lock.release()

    def _read_tickers(self) -> tuple[float, list[Ticker]] | None:
        raw = self._store.get("tickers")
        if raw is None:
            return None
        payload = json.loads(raw)
        return payload["at"], [Ticker(**t) for t in payload["items"]]
