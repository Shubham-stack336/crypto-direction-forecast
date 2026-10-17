from dataclasses import asdict

from app.controllers.errors import parse_symbol, run_service
from app.schemas.responses import HistoryItem, HistoryResponse, PredictionResponse
from app.services.prediction_service import PredictionService


class PredictionController:
    def __init__(self, service: PredictionService):
        self._service = service

    def create_prediction(self, symbol_slug: str, timeframe: str) -> PredictionResponse:
        symbol = parse_symbol(symbol_slug)
        outcome = run_service(lambda: self._service.predict(symbol, timeframe))
        return PredictionResponse(**asdict(outcome.prediction), saved=outcome.saved)

    def get_history(self, symbol_slug: str, timeframe: str, limit: int, offset: int) -> HistoryResponse:
        symbol = parse_symbol(symbol_slug)
        page = run_service(lambda: self._service.history(symbol, timeframe, limit, offset))
        return HistoryResponse(
            items=[HistoryItem(**asdict(item)) for item in page.items],
            total=page.total,
            limit=page.limit,
            offset=page.offset,
        )
