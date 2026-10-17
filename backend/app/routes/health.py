from fastapi import APIRouter, Depends

from app.controllers.health_controller import HealthController
from app.dependencies import get_health_controller
from app.schemas.responses import ErrorResponse, HealthResponse, ReadinessResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=HealthResponse)
def live(controller: HealthController = Depends(get_health_controller)):
    return controller.live()


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={503: {"model": ErrorResponse}},
)
def ready(controller: HealthController = Depends(get_health_controller)):
    return controller.ready()
