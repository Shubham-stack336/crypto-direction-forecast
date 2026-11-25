from dataclasses import asdict

from app.controllers.errors import run_service
from app.ml.inference import DISCLAIMER
from app.schemas.responses import CoinsResponse, ScanResponse
from app.services.prediction_service import PredictionService


class CoinController:
    def __init__(self, service: PredictionService):
        self._service = service

    def list_coins(self, timeframe: str) -> CoinsResponse:
        return CoinsResponse(items=[asdict(c) for c in run_service(lambda: self._service.coins(timeframe))])

    def scan(self, timeframe: str, limit: int) -> ScanResponse:
        rows = run_service(lambda: self._service.scan(timeframe, limit))
        return ScanResponse(items=[asdict(r) for r in rows], disclaimer=DISCLAIMER)
