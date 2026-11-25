import hmac
import logging
import time
import uuid
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core import metrics, rate_limit
from app.core.config import get_settings
from app.core.log import configure_logging
from app.dependencies import build_background_worker, dispose_db_engine, get_cache_store
from app.repositories.local_schema import upgrade_local_schema
from app.routes import coins, health, market, models, predictions

logger = logging.getLogger("app.request")


@asynccontextmanager
async def lifespan(app: FastAPI):
    database_url = get_settings().database_url
    if database_url:
        upgrade_local_schema(database_url)
    worker = build_background_worker() if get_settings().background_jobs else None
    if worker:
        worker.start()
    yield
    if worker:
        worker.stop()
    dispose_db_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.json_logs)
    if settings.sentry_dsn:
        sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.environment, send_default_pii=False)
    limits = rate_limit.Limits(settings.rate_limit_general, settings.rate_limit_predict, settings.rate_limit_scan)

    app = FastAPI(title="Crypto Direction Prediction API", version="0.1.0", lifespan=lifespan)

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = uuid.uuid4().hex
        started = time.perf_counter()
        try:
            store = app.dependency_overrides.get(get_cache_store, get_cache_store)()
            wait = await run_in_threadpool(rate_limit.check, store, limits, request, settings.client_ip_header)
            if wait is None:
                response = await call_next(request)
            else:
                response = JSONResponse(
                    status_code=429,
                    content={"detail": f"Too many requests. Try again in {wait} seconds."},
                    headers={"Retry-After": str(wait)},
                )
        except Exception as err:
            if settings.sentry_dsn:
                sentry_sdk.capture_exception(err)
            logger.exception(
                "unhandled error",
                extra={"request_id": request_id, "method": request.method, "path": request.url.path},
            )
            response = JSONResponse(status_code=500, content={"detail": "Internal server error"})

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        elapsed = time.perf_counter() - started
        route = getattr(request.scope.get("route"), "path", "unmatched")
        metrics.REQUESTS.labels(request.method, route, response.status_code).inc()
        metrics.LATENCY.labels(request.method, route).observe(elapsed)
        logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round(elapsed * 1000, 1),
            },
        )
        return response

    # Added last so it is outermost: 429 and 500 answers need CORS headers too.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    if settings.metrics_token:

        @app.get("/metrics", include_in_schema=False)
        def prometheus_metrics(authorization: str = Header("")):
            if not hmac.compare_digest(authorization.encode(), f"Bearer {settings.metrics_token}".encode()):
                raise HTTPException(status_code=401, detail="Unauthorized")
            return Response(metrics.render(), media_type="text/plain; version=0.0.4")

    app.include_router(health.router)
    app.include_router(coins.router)
    app.include_router(market.router)
    app.include_router(predictions.router)
    app.include_router(models.router)
    return app

app = create_app()
