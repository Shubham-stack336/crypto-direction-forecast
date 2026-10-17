"""Market-data access. Only this module knows about the exchange provider (CCXT)."""
import logging
import time
from typing import Callable, Protocol

import ccxt
import pandas as pd

logger = logging.getLogger(__name__)

COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]


class MarketDataUnavailableError(Exception):
    """The provider could not be reached or failed after bounded retries."""


class MarketSymbolError(Exception):
    """The provider does not know this symbol."""


class MarketRepository(Protocol):
    def fetch_candles(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame: ...


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
        self._exchange = getattr(ccxt, exchange_id)(
            {"enableRateLimit": True, "timeout": timeout_ms}
        )
        self._max_retries = max_retries
        self._sleep = sleep
        self.source = f"{exchange_id} via ccxt"

    def fetch_candles(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        for attempt in range(1, self._max_retries + 1):
            try:
                raw = self._exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
                break
            except ccxt.BadSymbol as err:
                raise MarketSymbolError(symbol) from err
            except ccxt.NetworkError as err:
                logger.warning("market fetch attempt %d/%d failed: %s", attempt, self._max_retries, err)
                if attempt == self._max_retries:
                    raise MarketDataUnavailableError("market data provider unreachable") from err
                self._sleep(0.5 * 2**attempt)
            except ccxt.ExchangeError as err:
                logger.warning("market provider error: %s", err)
                raise MarketDataUnavailableError("market data provider error") from err

        df = pd.DataFrame(raw, columns=COLUMNS)
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        return df
