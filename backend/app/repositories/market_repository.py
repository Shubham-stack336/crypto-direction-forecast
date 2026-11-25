"""Market-data access. Only this module knows about the exchange provider (CCXT)."""
import logging
import re
import threading
import time
from dataclasses import dataclass
from typing import Callable, Protocol

import ccxt
import pandas as pd

from app.core.symbols import SYMBOL_PATH_PATTERN, is_forecastable

logger = logging.getLogger(__name__)

COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]


TICKER_CACHE_S = 60
# Binance also lists tokenized stocks (NVDAB, TSLAB...) without labelling them. Observed on
# 2026-11-24: crypto pairs carry this permission group and stock tokens do not. Undocumented,
# so the filter switches itself off if no pair carries the group.
CRYPTO_PERMISSION_GROUP = "TRD_GRP_016"


def _is_crypto(market: dict) -> bool:
    sets = (market.get("info") or {}).get("permissionSets") or []
    return any(CRYPTO_PERMISSION_GROUP in group for group in sets)


@dataclass(frozen=True)
class Ticker:
    symbol: str
    last: float
    change_pct: float
    quote_volume: float


class MarketDataUnavailableError(Exception):
    """The provider could not be reached or failed after bounded retries."""


class MarketSymbolError(Exception):
    """The provider does not know this symbol."""


class MarketRepository(Protocol):
    def fetch_candles(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame: ...

    def list_tickers(self) -> list[Ticker]: ...


class CcxtMarketRepository:
    def __init__(
        self,
        exchange_id: str,
        timeout_ms: int,
        max_retries: int,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if not hasattr(ccxt, exchange_id):
            raise ValueError(f"Unknown exchange: {exchange_id}")
        options = {"fetchMarkets": {"types": ["spot"]}} if exchange_id == "binance" else {}
        self._exchange = getattr(ccxt, exchange_id)(
            {"enableRateLimit": True, "timeout": timeout_ms, "options": options}
        )
        self._markets_lock = threading.Lock()
        self._max_retries = max_retries
        self._sleep = sleep
        self._tickers: tuple[float, list[Ticker]] | None = None
        self._tickers_lock = threading.Lock()
        self.source = f"{exchange_id} via ccxt"

    def _retry(self, action: Callable):
        for attempt in range(1, self._max_retries + 1):
            try:
                return action()
            except ccxt.NetworkError as err:
                logger.warning("market fetch attempt %d/%d failed: %s", attempt, self._max_retries, err)
                if attempt == self._max_retries:
                    raise
                self._sleep(0.5 * 2**attempt)

    def _markets(self) -> dict:
        """The market list is large: after a cold start one request loads it and the others wait for it."""
        with self._markets_lock:
            return self._exchange.load_markets()

    def list_tickers(self) -> list[Ticker]:
        """Every active spot USDT pair that can be forecast, busiest first. Cached for a minute."""
        with self._tickers_lock:
            if self._tickers and time.monotonic() - self._tickers[0] < TICKER_CACHE_S:
                return self._tickers[1]
            try:
                markets = self._retry(self._markets)
                raw = self._retry(self._exchange.fetch_tickers)
            except ccxt.BaseError as err:
                logger.warning("ticker fetch failed: %s", err)
                raise MarketDataUnavailableError("ticker list unavailable") from err
            tickers = []
            labelled = any(_is_crypto(market) for market in markets.values())
            for symbol, market in markets.items():
                ticker = raw.get(symbol)
                if not (market.get("spot") and market.get("active") and ticker and ticker.get("last")):
                    continue
                if labelled and not _is_crypto(market):
                    continue
                if not is_forecastable(symbol) or not re.match(SYMBOL_PATH_PATTERN, symbol.replace("/", "-")):
                    continue
                tickers.append(
                    Ticker(
                        symbol,
                        float(ticker["last"]),
                        float(ticker.get("percentage") or 0.0),
                        float(ticker.get("quoteVolume") or 0.0),
                    )
                )
            tickers.sort(key=lambda t: t.quote_volume, reverse=True)
            self._tickers = (time.monotonic(), tickers)
            return tickers

    def fetch_candles(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        def fetch():
            if not getattr(self._exchange, "markets", True):
                self._markets()
            return self._exchange.fetch_ohlcv(symbol, timeframe, limit=limit)

        try:
            raw = self._retry(fetch)
        except ccxt.BadSymbol as err:
            raise MarketSymbolError(symbol) from err
        except ccxt.NetworkError as err:
            raise MarketDataUnavailableError("market data provider unreachable") from err
        except ccxt.ExchangeError as err:
            logger.warning("market provider error: %s", err)
            raise MarketDataUnavailableError("market data provider error") from err

        df = pd.DataFrame(raw, columns=COLUMNS)
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        return df
