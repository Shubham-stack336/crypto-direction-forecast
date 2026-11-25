"""Data Controller Layer.

Translates HTTP requests into DataService operations and formats JSON responses.
"""

import logging
from typing import Any
from fastapi import HTTPException
from app.services.data_service import DataService

logger = logging.getLogger("app.controller.data")


class DataController:
    def __init__(self, data_service: DataService | None = None):
        self.service = data_service or DataService()

    def fetch_data(self, symbol: str, period: str = "5y", refresh: bool = False) -> dict[str, Any]:
        try:
            ticker = self.service.normalize_symbol(symbol)
            if refresh or not self.service.repository.exists(ticker):
                df, paths, validation = self.service.fetch_and_save(ticker, period=period)
            else:
                df = self.service.get_data(ticker, force_refresh=False)
                validation = self.service.validate_data(df)
                paths = {
                    "parquet": str(self.service.repository._get_raw_path(ticker, "parquet")),
                    "csv": str(self.service.repository._get_raw_path(ticker, "csv")),
                }

            latest_row = df.iloc[-1]
            latest_date = str(df.index[-1].date()) if hasattr(df.index[-1], "date") else str(df.index[-1])

            return {
                "symbol": ticker,
                "period": period,
                "latest_date": latest_date,
                "latest_close": round(float(latest_row["close"]), 2),
                "latest_volume": round(float(latest_row["volume"]), 2),
                "total_records": len(df),
                "validation": validation,
                "stored_paths": paths,
            }
        except ValueError as e:
            logger.warning(f"Validation or data fetch error: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.exception(f"Unexpected error fetching data for {symbol}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch data: {str(e)}")

    def get_summary(self, symbol: str) -> dict[str, Any]:
        try:
            ticker = self.service.normalize_symbol(symbol)
            df = self.service.get_data(ticker)
            validation = self.service.validate_data(df)
            recent_candles = []
            for date, row in df.tail(10).iterrows():
                recent_candles.append({
                    "date": str(date.date()) if hasattr(date, "date") else str(date),
                    "open": round(float(row["open"]), 2),
                    "high": round(float(row["high"]), 2),
                    "low": round(float(row["low"]), 2),
                    "close": round(float(row["close"]), 2),
                    "volume": round(float(row["volume"]), 2),
                })
            return {
                "symbol": ticker,
                "total_rows": len(df),
                "validation": validation,
                "recent_candles": recent_candles,
            }
        except Exception as e:
            logger.exception(f"Error getting summary for {symbol}: {e}")
            raise HTTPException(status_code=404, detail=f"Data not available for {symbol}: {str(e)}")

    def list_symbols(self) -> dict[str, list[str]]:
        symbols = self.service.repository.list_available_symbols()
        return {"available_symbols": symbols}
