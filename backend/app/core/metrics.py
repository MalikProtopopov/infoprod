"""Prometheus метрики.

Экспортируется:
- `http_requests_total` (Counter) — все запросы, лейблы method/path/status
- `http_request_duration_seconds` (Histogram) — латенси
- `http_requests_in_flight` (Gauge) — текущая нагрузка
- `bot_polling_status` (Gauge per bot_id) — 1 если бот polls, 0 если нет
- `subscription_active_total` (Gauge) — активных подписок
"""
from __future__ import annotations

import time

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# --- Метрики ---

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    labelnames=["method", "path", "status"],
)

HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    labelnames=["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

HTTP_REQUESTS_IN_FLIGHT = Gauge(
    "http_requests_in_flight",
    "Current HTTP requests in-flight",
)

BOT_POLLING_STATUS = Gauge(
    "bot_polling_status",
    "1 if bot is currently polling, 0 if not",
    labelnames=["bot_id", "bot_username"],
)

SUBSCRIPTION_ACTIVE_TOTAL = Gauge(
    "subscription_active_total",
    "Total active subscriptions",
)

PAYMENT_TOTAL = Counter(
    "payment_total",
    "Total payments registered",
    labelnames=["currency"],
)

LEAD_TOTAL = Counter(
    "lead_total",
    "Total leads created",
    labelnames=["source"],
)


# --- Middleware ---


def _normalize_path(path: str) -> str:
    """Заменяем числовые id в пути на :id чтобы кардинальность лейблов не взорвалась."""
    parts = path.split("/")
    out = []
    for p in parts:
        if p.isdigit():
            out.append(":id")
        else:
            out.append(p)
    return "/".join(out)


class PrometheusMetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # /metrics само не считаем — иначе циклически растёт
        if request.url.path == "/metrics":
            return await call_next(request)

        method = request.method
        path = _normalize_path(request.url.path)

        HTTP_REQUESTS_IN_FLIGHT.inc()
        t0 = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration = time.perf_counter() - t0
            HTTP_REQUEST_DURATION.labels(method=method, path=path).observe(duration)
            HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status=str(status_code)).inc()
            HTTP_REQUESTS_IN_FLIGHT.dec()


# --- /metrics endpoint ---


def metrics_response() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
