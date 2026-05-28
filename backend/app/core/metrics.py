"""
Prometheus Metrics & Observability
Production-ready metrics collection for:
- FastAPI HTTP requests
- WebSocket traffic
- OpenSearch latency
- Collector pipeline health
"""

from __future__ import annotations

import time
from typing import Callable

from fastapi import FastAPI, Request, Response
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    make_asgi_app,
)
from starlette.middleware.base import BaseHTTPMiddleware

# =========================================================
# HTTP Metrics
# =========================================================

HTTP_REQUEST_COUNT = Counter(
    "soc_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

HTTP_REQUEST_DURATION = Histogram(
    "soc_http_request_duration_seconds",
    "HTTP request duration",
    ["method", "path"],
    buckets=(
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1.0,
        2.5,
        5.0,
    ),
)

HTTP_EXCEPTIONS = Counter(
    "soc_http_exceptions_total",
    "Unhandled HTTP exceptions",
    ["method", "path"],
)

# =========================================================
# OpenSearch Metrics
# =========================================================

OS_QUERY_DURATION = Histogram(
    "soc_opensearch_query_duration_seconds",
    "OpenSearch query duration",
    ["operation"],
)

OS_QUERY_ERRORS = Counter(
    "soc_opensearch_query_errors_total",
    "OpenSearch query errors",
    ["operation"],
)

# =========================================================
# WebSocket Metrics
# =========================================================

WS_ACTIVE_CONNECTIONS = Gauge(
    "soc_ws_active_connections",
    "Current active websocket connections",
)

WS_MESSAGES_SENT = Counter(
    "soc_ws_messages_sent_total",
    "WebSocket messages sent",
    ["severity"],
)

WS_SEND_ERRORS = Counter(
    "soc_ws_send_errors_total",
    "WebSocket send failures",
)

# =========================================================
# Collector Metrics
# =========================================================

COLLECTOR_EVENTS_PROCESSED = Counter(
    "soc_collector_events_processed_total",
    "Total processed collector events",
)

COLLECTOR_EVENTS_SKIPPED = Counter(
    "soc_collector_events_skipped_total",
    "Total skipped collector events",
)

COLLECTOR_ERRORS = Counter(
    "soc_collector_errors_total",
    "Collector processing errors",
)

REDIS_PUBLISH_ERRORS = Counter(
    "soc_redis_publish_errors_total",
    "Redis publish failures",
)

SUPPRESSED_ALERTS = Counter(
    "soc_suppressed_alerts_total",
    "Suppressed alerts",
)

# =========================================================
# Helpers
# =========================================================

def normalize_path(request: Request) -> str:
    """
    Prevent Prometheus cardinality explosion.

    /api/users/123 -> /api/users/{id}
    """
    route = request.scope.get("route")

    if route and hasattr(route, "path"):
        return route.path

    return request.url.path


# =========================================================
# HTTP Middleware
# =========================================================

class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:

        method = request.method
        path = normalize_path(request)

        start = time.perf_counter()

        try:
            response = await call_next(request)

            duration = time.perf_counter() - start

            HTTP_REQUEST_DURATION.labels(
                method=method,
                path=path,
            ).observe(duration)

            HTTP_REQUEST_COUNT.labels(
                method=method,
                path=path,
                status=response.status_code,
            ).inc()

            return response

        except Exception:
            duration = time.perf_counter() - start

            HTTP_REQUEST_DURATION.labels(
                method=method,
                path=path,
            ).observe(duration)

            HTTP_EXCEPTIONS.labels(
                method=method,
                path=path,
            ).inc()

            HTTP_REQUEST_COUNT.labels(
                method=method,
                path=path,
                status=500,
            ).inc()

            raise


# =========================================================
# Setup
# =========================================================

def setup_metrics(app: FastAPI) -> None:
    """
    Register Prometheus metrics endpoint and middleware.
    """

    app.add_middleware(MetricsMiddleware)

    metrics_app = make_asgi_app()

    app.mount("/metrics", metrics_app)