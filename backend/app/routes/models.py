from typing import Literal

from fastapi import APIRouter, Depends, Path

from app.controllers.model_controller import ModelController
from app.core.symbols import SYMBOL_PATH_PATTERN
from app.dependencies import get_model_controller
from app.schemas.responses import ErrorResponse, ModelStatusResponse

router = APIRouter(prefix="/api/v1/models", tags=["models"])


@router.get(
    "/{symbol}/status",
    response_model=ModelStatusResponse,
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def get_model_status(
    symbol: str = Path(pattern=SYMBOL_PATH_PATTERN, description="e.g. BTC-USDT"),
    timeframe: Literal["1h"] = "1h",
    controller: ModelController = Depends(get_model_controller),
):
    return controller.get_status(symbol, timeframe)
