"""Data Service Layer.

Business logic for fetching, cleaning, validating, and managing
historical cryptocurrency data.
"""

import logging
from typing import Any
import pandas as pd

from app.repositories.data_repository import DataRepository

logger = logging.getLogger("app.service.data")

SUPPORTED_SYMBOLS = {
    "BTC": "BTC-USD",
    "BTC-USD": "BTC-USD",
    "BTC/USD": "BTC-USD",
    "BTC-USDT": "BTC-USD",
    "BTC/USDT": "BTC-USD",
    "ETH": "ETH-USD",
    "ETH-USD": "ETH-USD",
    "ETH/USD": "ETH-USD",
    "ETH-USDT": "ETH-USD",
    "ETH/USDT": "ETH-USD",
    "SOL": "SOL-USD",
    "SOL-USD": "SOL-USD",
    "SOL/USD": "SOL-USD",
    "SOL-USDT": "SOL-USD",
    "DOGE": "DOGE-USD",
    "DOGE-USD": "DOGE-USD",
    "DOGE-USDT": "DOGE-USD",
    "ADA": "ADA-USD",
    "ADA-USD": "ADA-USD",
    "XRP": "XRP-USD",
    "XRP-USD": "XRP-USD",
}

REQUIRED_COLUMNS = ["open", "high", "low", "close", "volume"]


class DataService:
    def __init__(self, repository: DataRepository | None = None):
        self.repository = repository or DataRepository()

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        """Normalize symbol to standard ticker format (e.g. BTC-USD, ETH-USD)."""
        clean = symbol.strip().upper()
        if clean in SUPPORTED_SYMBOLS:
            return SUPPORTED_SYMBOLS[clean]
        base = clean.replace("/USDT", "").replace("-USDT", "").replace("/USD", "").replace("-USD", "")
        return f"{base}-USD"

    def fetch_historical(
        self, symbol: str, period: str = "5y", interval: str = "1d"
    ) -> pd.DataFrame:
        """Fetch historical daily OHLCV from yfinance."""
        ticker = self.normalize_symbol(symbol)
        logger.info(f"Fetching {ticker} historical data (period={period}, interval={interval})")

        df = None
        try:
            import yfinance as yf
            df = yf.download(ticker, period=period, interval=interval, auto_adjust=False, progress=False)
            if df is not None and not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = [c[0].lower() for c in df.columns]
                else:
                    df.columns = [str(c).lower() for c in df.columns]
        except Exception as e:
            logger.warning(f"Live fetch from yfinance failed for {ticker}: {e}.")

        # Never replace missing prices with invented ones.
        if df is None or df.empty:
            raise ValueError(f"No market data available for {ticker}")

        # Verify required columns exist
        missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        df = df[REQUIRED_COLUMNS].copy()

        # Clean index: convert to UTC datetime without timezone offset
        df.index = pd.to_datetime(df.index)
        if df.index.tz is not None:
            df.index = df.index.tz_convert("UTC").tz_localize(None)

        df.index.name = "date"
        df = df[~df.index.duplicated(keep="last")]
        df = df.sort_index(ascending=True)

        for col in REQUIRED_COLUMNS:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        valid_mask = (df["close"] > 0) & (df["open"] > 0) & (~df["close"].isna())
        df = df[valid_mask].copy()
        df = df.ffill().bfill()

        if len(df) < 50:
            raise ValueError(f"Insufficient historical data ({len(df)} rows) for {ticker}")

        logger.info(f"Processed {len(df)} rows for {ticker} ({df.index[0].date()} to {df.index[-1].date()})")
        return df

    def validate_data(self, df: pd.DataFrame) -> dict[str, Any]:
        """Perform data health and validation checks on raw price DataFrame."""
        if df.empty:
            return {"valid": False, "error": "DataFrame is empty"}

        missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing_cols:
            return {"valid": False, "error": f"Missing columns: {missing_cols}"}

        is_monotonic = bool(df.index.is_monotonic_increasing)
        has_nulls = int(df.isna().sum().sum())
        row_count = len(df)
        start_date = str(df.index.min().date()) if hasattr(df.index.min(), "date") else str(df.index.min())
        end_date = str(df.index.max().date()) if hasattr(df.index.max(), "date") else str(df.index.max())

        prices_positive = bool((df[["open", "high", "low", "close"]] > 0).all().all())
        high_low_valid = bool((df["high"] >= df["low"]).all())

        is_valid = is_monotonic and (has_nulls == 0) and prices_positive and high_low_valid and (row_count >= 50)

        return {
            "valid": is_valid,
            "row_count": row_count,
            "start_date": start_date,
            "end_date": end_date,
            "is_chronological": is_monotonic,
            "null_values": has_nulls,
            "prices_positive": prices_positive,
            "high_low_valid": high_low_valid,
        }

    def fetch_and_save(
        self, symbol: str, period: str = "5y", interval: str = "1d"
    ) -> tuple[pd.DataFrame, dict[str, str], dict[str, Any]]:
        """Fetch historical data, validate it, and persist to repository."""
        df = self.fetch_historical(symbol, period=period, interval=interval)
        validation = self.validate_data(df)
        if not validation["valid"]:
            raise ValueError(f"Data validation failed for {symbol}: {validation}")

        paths = self.repository.save_raw(symbol, df)
        return df, paths, validation

    def get_data(self, symbol: str, force_refresh: bool = False) -> pd.DataFrame:
        """Get data from repository or fetch if not present."""
        if not force_refresh and self.repository.exists(symbol):
            try:
                return self.repository.load_raw(symbol)
            except Exception as e:
                logger.warning(f"Failed to load cached data for {symbol}: {e}. Refetching...")

        df, _, _ = self.fetch_and_save(symbol)
        return df
