"""Fixed-window request limits per client. Expensive endpoints get a tighter limit."""
import time
from dataclasses import dataclass

from starlette.requests import Request

from app.core.cache import CacheStore

WINDOW_S = 60


@dataclass(frozen=True)
class Limits:
    general: int
    predict: int
    scan: int


def client_key(request: Request, ip_header: str | None) -> str:
    """Only trust a proxy header the operator named: anyone can send X-Forwarded-For."""
    if ip_header:
        value = request.headers.get(ip_header)
        if value:
            return value.strip()[:64]
    return request.client.host if request.client else "unknown"


def check(
    store: CacheStore, limits: Limits, request: Request, ip_header: str | None, now: float | None = None
) -> int | None:
    """None when allowed, otherwise the number of seconds to wait."""
    path = request.url.path
    if not path.startswith("/api/"):
        return None
    if path.startswith("/api/v1/predictions/") and request.method == "POST":
        bucket, limit = "predict", limits.predict
    elif path.startswith("/api/v1/coins/scan"):
        bucket, limit = "scan", limits.scan
    else:
        bucket, limit = "general", limits.general
    if limit <= 0:
        return None
    now = time.time() if now is None else now
    key = f"rl:{bucket}:{client_key(request, ip_header)}:{int(now // WINDOW_S)}"
    if store.incr(key, WINDOW_S) <= limit:
        return None
    return max(1, int(WINDOW_S - now % WINDOW_S))
