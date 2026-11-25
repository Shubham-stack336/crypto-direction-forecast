"""Unit tests for Phase 1: Data Pipeline, Repository, and Validation."""

import pandas as pd
import pytest

from app.repositories.data_repository import DataRepository
from app.services.data_service import DataService


@pytest.fixture
def sample_ohlcv_df():
    """Create a realistic sample OHLCV DataFrame for testing."""
    dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
    data = {
        "open": [50000.0 + i * 10 for i in range(100)],
        "high": [50500.0 + i * 10 for i in range(100)],
        "low": [49500.0 + i * 10 for i in range(100)],
        "close": [50200.0 + i * 10 for i in range(100)],
        "volume": [1000000.0 + i * 500 for i in range(100)],
    }
    df = pd.DataFrame(data, index=dates)
    df.index.name = "date"
    return df


class TestDataRepository:
    def test_save_and_load_raw(self, tmp_path, sample_ohlcv_df):
        repo = DataRepository(raw_dir=tmp_path / "raw", processed_dir=tmp_path / "processed")
        symbol = "BTC-USD"

        paths = repo.save_raw(symbol, sample_ohlcv_df)
        assert "parquet" in paths
        assert "csv" in paths
        assert repo.exists(symbol) is True

        loaded_df = repo.load_raw(symbol)
        assert len(loaded_df) == len(sample_ohlcv_df)
        assert list(loaded_df.columns) == list(sample_ohlcv_df.columns)
        assert loaded_df["close"].iloc[0] == sample_ohlcv_df["close"].iloc[0]

    def test_empty_dataframe_save_raises(self, tmp_path):
        repo = DataRepository(raw_dir=tmp_path / "raw", processed_dir=tmp_path / "processed")
        with pytest.raises(ValueError):
            repo.save_raw("BTC-USD", pd.DataFrame())


class TestDataService:
    def test_normalize_symbol(self):
        assert DataService.normalize_symbol("btc") == "BTC-USD"
        assert DataService.normalize_symbol("ETH") == "ETH-USD"
        assert DataService.normalize_symbol("BTC-USDT") == "BTC-USD"
        assert DataService.normalize_symbol("eth/usd") == "ETH-USD"
        assert DataService.normalize_symbol("SOL") == "SOL-USD"
        assert DataService.normalize_symbol("DOGE") == "DOGE-USD"
        assert DataService.normalize_symbol("ada-usdt") == "ADA-USD"
        assert DataService.normalize_symbol("xrp/usd") == "XRP-USD"

    def test_validate_data_valid(self, sample_ohlcv_df):
        service = DataService()
        result = service.validate_data(sample_ohlcv_df)
        assert result["valid"] is True
        assert result["row_count"] == 100
        assert result["is_chronological"] is True
        assert result["null_values"] == 0

    def test_validate_data_detects_non_monotonic(self, sample_ohlcv_df):
        # Reverse order
        reversed_df = sample_ohlcv_df.iloc[::-1].copy()
        service = DataService()
        result = service.validate_data(reversed_df)
        assert result["is_chronological"] is False
        assert result["valid"] is False

    def test_validate_data_detects_negative_price(self, sample_ohlcv_df):
        corrupt_df = sample_ohlcv_df.copy()
        corrupt_df.iloc[10, corrupt_df.columns.get_loc("close")] = -500.0
        service = DataService()
        result = service.validate_data(corrupt_df)
        assert result["prices_positive"] is False
        assert result["valid"] is False

    def test_validate_data_detects_high_lower_than_low(self, sample_ohlcv_df):
        corrupt_df = sample_ohlcv_df.copy()
        corrupt_df.iloc[5, corrupt_df.columns.get_loc("high")] = 100.0
        corrupt_df.iloc[5, corrupt_df.columns.get_loc("low")] = 200.0
        service = DataService()
        result = service.validate_data(corrupt_df)
        assert result["high_low_valid"] is False
        assert result["valid"] is False

    def test_missing_data_is_an_error_not_an_invention(self, monkeypatch):
        import yfinance

        monkeypatch.setattr(yfinance, "download", lambda *a, **k: pd.DataFrame())
        with pytest.raises(ValueError, match="No market data"):
            DataService().fetch_historical("NOSUCHCOIN")
