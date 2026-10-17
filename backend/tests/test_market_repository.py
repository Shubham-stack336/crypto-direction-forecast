import ccxt
import pytest

from app.repositories.market_repository import (
    CcxtMarketRepository,
    MarketDataUnavailableError,
    MarketSymbolError,
)

ROW = [1_700_000_000_000, 1.0, 2.0, 0.5, 1.5, 10.0]


class StubExchange:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def fetch_ohlcv(self, symbol, timeframe, limit):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def make_repo(outcomes, retries=3):
    repo = CcxtMarketRepository("binance", timeout_ms=1000, max_retries=retries, sleep=lambda s: None)
    repo._exchange = StubExchange(outcomes)
    return repo


def test_retries_then_succeeds():
    repo = make_repo([ccxt.NetworkError("a"), ccxt.RequestTimeout("b"), [ROW]])
    df = repo.fetch_candles("BTC/USDT", "1h", 10)
    assert repo._exchange.calls == 3
    assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
    assert str(df["timestamp"].dt.tz) == "UTC"


def test_retries_are_bounded():
    repo = make_repo([ccxt.NetworkError("x")] * 5, retries=3)
    with pytest.raises(MarketDataUnavailableError):
        repo.fetch_candles("BTC/USDT", "1h", 10)
    assert repo._exchange.calls == 3


def test_bad_symbol_is_not_retried():
    repo = make_repo([ccxt.BadSymbol("nope")])
    with pytest.raises(MarketSymbolError):
        repo.fetch_candles("XXX/USDT", "1h", 10)
    assert repo._exchange.calls == 1


def test_exchange_error_is_wrapped_without_retry():
    repo = make_repo([ccxt.ExchangeError("boom")])
    with pytest.raises(MarketDataUnavailableError):
        repo.fetch_candles("BTC/USDT", "1h", 10)
    assert repo._exchange.calls == 1


def test_unknown_exchange_is_rejected_at_startup():
    with pytest.raises(ValueError):
        CcxtMarketRepository("not_an_exchange", timeout_ms=1000, max_retries=1)
