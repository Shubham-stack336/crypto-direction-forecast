import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.log import configure_logging
from app.dependencies import dispose_db_engine
from app.routes import health, market, models, predictions

logger = logging.getLogger("app.request")


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    dispose_db_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.json_logs)

    app = FastAPI(title="Crypto Direction Prediction API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = uuid.uuid4().hex
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "unhandled error",
                extra={"request_id": request_id, "method": request.method, "path": request.url.path},
            )
            response = JSONResponse(status_code=500, content={"detail": "Internal server error"})

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            },
        )
        return response

    app.include_router(health.router)
    app.include_router(market.router)
    app.include_router(predictions.router)
    app.include_router(models.router)
    return app


app = create_app()
