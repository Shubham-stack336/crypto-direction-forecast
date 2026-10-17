from fastapi import HTTPException

from app.schemas.responses import HealthResponse, ReadinessResponse
from app.services.prediction_service import PredictionService


class HealthController:
    def __init__(self, service: PredictionService):
        self._service = service

    def live(self) -> HealthResponse:
        return HealthResponse(status="ok")

    def ready(self) -> ReadinessResponse:
        readiness = self._service.readiness()
        if not readiness.models:
            raise HTTPException(status_code=503, detail="No usable model is loaded")
        if readiness.database == "unavailable":
            raise HTTPException(status_code=503, detail="Database is unavailable")
        return ReadinessResponse(status="ready", models=readiness.models, database=readiness.database)
