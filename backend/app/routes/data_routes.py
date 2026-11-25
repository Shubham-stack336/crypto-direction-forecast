"""Data Routes Layer (FastAPI Router).

Exposes HTTP endpoints for cryptocurrency historical data ingestion and retrieval.
"""

from fastapi import APIRouter, Query
from app.controllers.data_controller import DataController

router = APIRouter(prefix="/api/v1/data", tags=["Data"])
controller = DataController()


@router.get("/fetch/{symbol}")
def fetch_data(
    symbol: str,
    period: str = Query("5y", description="Data period, e.g. 1y, 2y, 5y, max"),
    refresh: bool = Query(False, description="Force re-download from source"),
):
    """Fetch, clean, validate, and store historical daily data for a cryptocurrency."""
    return controller.fetch_data(symbol=symbol, period=period, refresh=refresh)


@router.get("/summary/{symbol}")
def get_data_summary(symbol: str):
    """Get stored dataset summary and recent 10 daily candles."""
    return controller.get_summary(symbol=symbol)


@router.get("/list")
def list_available_symbols():
    """List all cryptocurrency symbols available in local storage."""
    return controller.list_symbols()
