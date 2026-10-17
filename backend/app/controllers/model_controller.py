from dataclasses import asdict

from app.controllers.errors import parse_symbol, run_service
from app.ml.inference import DISCLAIMER
from app.schemas.responses import ModelStatusResponse
from app.services.prediction_service import PredictionService


class ModelController:
    def __init__(self, service: PredictionService):
        self._service = service

    def get_status(self, symbol_slug: str, timeframe: str) -> ModelStatusResponse:
        symbol = parse_symbol(symbol_slug)
        status = run_service(lambda: self._service.model_status(symbol, timeframe))
        return ModelStatusResponse(**asdict(status), disclaimer=DISCLAIMER)
