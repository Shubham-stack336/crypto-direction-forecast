from typing import Literal

from fastapi import APIRouter, Depends, Query

from app.controllers.coin_controller import CoinController
from app.dependencies import get_coin_controller
from app.schemas.responses import CoinsResponse, ErrorResponse, ScanResponse

router = APIRouter(prefix="/api/v1/coins", tags=["coins"])


@router.get("", response_model=CoinsResponse, responses={503: {"model": ErrorResponse}})
def list_coins(
    timeframe: Literal["1h"] = "1h",
    controller: CoinController = Depends(get_coin_controller),
):
    return controller.list_coins(timeframe)


@router.get("/scan", response_model=ScanResponse, responses={503: {"model": ErrorResponse}})
def scan(
    timeframe: Literal["1h"] = "1h",
    limit: int = Query(12, ge=1, le=20),
    controller: CoinController = Depends(get_coin_controller),
):
    return controller.scan(timeframe, limit)
