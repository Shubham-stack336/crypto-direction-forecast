from typing import Literal

from fastapi import APIRouter, Depends, Path, Query

from app.controllers.prediction_controller import PredictionController
from app.core.symbols import SYMBOL_PATH_PATTERN
from app.dependencies import get_prediction_controller
from app.schemas.responses import ErrorResponse, HistoryResponse, PredictionRequest, PredictionResponse

router = APIRouter(prefix="/api/v1/predictions", tags=["predictions"])


@router.post(
    "/{symbol}",
    response_model=PredictionResponse,
    responses={404: {"model": ErrorResponse}, 502: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def create_prediction(
    symbol: str = Path(pattern=SYMBOL_PATH_PATTERN, description="e.g. BTC-USDT"),
    body: PredictionRequest | None = None,
    controller: PredictionController = Depends(get_prediction_controller),
):
    request = body or PredictionRequest()
    return controller.create_prediction(symbol, request.timeframe)


@router.get(
    "/{symbol}/history",
    response_model=HistoryResponse,
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def get_history(
    symbol: str = Path(pattern=SYMBOL_PATH_PATTERN, description="e.g. BTC-USDT"),
    timeframe: Literal["1h"] = "1h",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0, le=100_000),
    controller: PredictionController = Depends(get_prediction_controller),
):
    return controller.get_history(symbol, timeframe, limit, offset)
