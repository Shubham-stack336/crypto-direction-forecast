from app.controllers.errors import parse_symbol, run_service
from app.schemas.responses import MarketResponse, SavedCandlesResponse
from app.services.prediction_service import PredictionService


class MarketController:
    def __init__(self, service: PredictionService):
        self._service = service

    def get_market(self, symbol_slug: str, timeframe: str) -> MarketResponse:
        symbol = parse_symbol(symbol_slug)
        snapshot = run_service(lambda: self._service.market_snapshot(symbol, timeframe))
        return MarketResponse(**snapshot.__dict__)

    def get_saved_candles(self, symbol_slug: str, timeframe: str) -> SavedCandlesResponse:
        symbol = parse_symbol(symbol_slug)
        saved = run_service(lambda: self._service.saved_candles(symbol, timeframe))
        return SavedCandlesResponse(**saved.__dict__)
