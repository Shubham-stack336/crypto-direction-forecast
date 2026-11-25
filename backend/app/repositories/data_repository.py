"""Data Repository Layer.

Handles storage and retrieval of raw and processed cryptocurrency data
from disk (Parquet / CSV).
"""

from pathlib import Path
import pandas as pd
import logging

logger = logging.getLogger("app.repository.data")

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"


class DataRepository:
    def __init__(self, raw_dir: Path | None = None, processed_dir: Path | None = None):
        self.raw_dir = raw_dir or RAW_DATA_DIR
        self.processed_dir = processed_dir or PROCESSED_DATA_DIR
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def _get_raw_path(self, symbol: str, ext: str = "parquet") -> Path:
        sanitized = symbol.replace("/", "_").replace("-", "_").lower()
        return self.raw_dir / f"{sanitized}_daily.{ext}"

    def save_raw(self, symbol: str, df: pd.DataFrame) -> dict[str, str]:
        """Save raw OHLCV DataFrame to both Parquet and CSV for redundancy."""
        if df.empty:
            raise ValueError(f"Cannot save empty DataFrame for symbol {symbol}")

        parquet_path = self._get_raw_path(symbol, "parquet")
        csv_path = self._get_raw_path(symbol, "csv")

        # Save parquet
        df.to_parquet(parquet_path, engine="pyarrow", index=True)
        # Also save CSV for easy human inspection
        df.to_csv(csv_path, index=True)

        logger.info(f"Saved {len(df)} rows for {symbol} to {parquet_path}")
        return {"parquet": str(parquet_path), "csv": str(csv_path)}

    def load_raw(self, symbol: str) -> pd.DataFrame:
        """Load raw OHLCV DataFrame, preferring Parquet and falling back to CSV."""
        parquet_path = self._get_raw_path(symbol, "parquet")
        csv_path = self._get_raw_path(symbol, "csv")

        if parquet_path.exists():
            df = pd.read_parquet(parquet_path, engine="pyarrow")
            return df
        elif csv_path.exists():
            df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
            return df
        else:
            raise FileNotFoundError(f"No stored data found for symbol '{symbol}' in {self.raw_dir}")

    def exists(self, symbol: str) -> bool:
        """Check if cached data exists for the given symbol."""
        parquet_path = self._get_raw_path(symbol, "parquet")
        csv_path = self._get_raw_path(symbol, "csv")
        return parquet_path.exists() or csv_path.exists()

    def list_available_symbols(self) -> list[str]:
        """List all symbols that have stored raw data."""
        files = list(self.raw_dir.glob("*_daily.parquet"))
        symbols = [f.name.replace("_daily.parquet", "") for f in files]
        return symbols
