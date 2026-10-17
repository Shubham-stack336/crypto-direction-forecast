from app.controllers.errors import parse_symbol, run_service
from app.schemas.responses import MarketResponse
from app.services.prediction_service import PredictionService


class MarketController:
    def __init__(self, service: PredictionService):
        self._service = service

    def get_market(self, symbol_slug: str, timeframe: str) -> MarketResponse:
        symbol = parse_symbol(symbol_slug)
        snapshot = run_service(lambda: self._service.market_snapshot(symbol, timeframe))
        return MarketResponse(**snapshot.__dict__)
