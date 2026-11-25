"""Prometheus metrics. Labels use the route template, so one coin does not become one time series."""
from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest

REGISTRY = CollectorRegistry()
REQUESTS = Counter("http_requests", "HTTP requests", ["method", "route", "status"], registry=REGISTRY)
LATENCY = Histogram("http_request_seconds", "HTTP request duration", ["method", "route"], registry=REGISTRY)
EXCHANGE_FAILURES = Counter("exchange_failures", "Failed exchange calls", ["exchange"], registry=REGISTRY)


def render() -> bytes:
    return generate_latest(REGISTRY)
