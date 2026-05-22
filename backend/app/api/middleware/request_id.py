"""Middleware: проставляет request_id в ContextVar для каждого HTTP-запроса.

После — все логи внутри запроса несут поля:
    request_id, method, path, client_ip, user_agent
и финальный лог `request.completed` со статусом и duration_ms.
"""
from __future__ import annotations

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from structlog.contextvars import bind_contextvars, clear_contextvars

logger = structlog.get_logger("http")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Уважаем входящий X-Request-ID (nginx или клиент); иначе генерим
        req_id = request.headers.get("x-request-id") or str(uuid.uuid4())

        clear_contextvars()
        bind_contextvars(
            request_id=req_id,
            method=request.method,
            path=request.url.path,
            client_ip=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )

        t0 = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("request.unhandled_exception")
            raise
        finally:
            dt_ms = round((time.perf_counter() - t0) * 1000, 2)

        logger.info("request.completed", status=response.status_code, duration_ms=dt_ms)
        response.headers["x-request-id"] = req_id
        return response


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "?"
