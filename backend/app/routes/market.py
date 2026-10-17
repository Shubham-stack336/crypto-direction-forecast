from typing import Literal

from fastapi import APIRouter, Depends, Path

from app.controllers.market_controller import MarketController
from app.core.symbols import SYMBOL_PATH_PATTERN
from app.dependencies import get_market_controller
from app.schemas.responses import ErrorResponse, MarketResponse

router = APIRouter(prefix="/api/v1/market", tags=["market"])


@router.get(
    "/{symbol}",
    response_model=MarketResponse,
    responses={404: {"model": ErrorResponse}, 502: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def get_market(
    symbol: str = Path(pattern=SYMBOL_PATH_PATTERN, description="e.g. BTC-USDT"),
    timeframe: Literal["1h"] = "1h",
    controller: MarketController = Depends(get_market_controller),
):
    return controller.get_market(symbol, timeframe)
