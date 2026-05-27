"""Глобальные обработчики ошибок: Exception→JSON 500, IntegrityError→JSON 409.

Цель — гарантировать, что 500/409 всегда отдаются как JSON (а не plain-text
«Internal Server Error», на котором падал фронт), и что IntegrityError маппится
в 409 системно.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError

from app.main import app

# Временные маршруты, провоцирующие глобальные handler'ы (регистрируются один раз
# при импорте модуля; безвредны — только в тестовом процессе).
if not any(getattr(r, "path", None) == "/api/_test_boom" for r in app.routes):

    @app.get("/api/_test_boom")
    async def _boom():  # pragma: no cover - тело не важно, важен handler
        raise RuntimeError("boom")

    @app.get("/api/_test_integrity")
    async def _integrity():  # pragma: no cover
        raise IntegrityError("INSERT ...", {}, Exception("duplicate key"))


@pytest_asyncio.fixture
async def lenient_client():
    """httpx-клиент с raise_app_exceptions=False.

    Starlette ServerErrorMiddleware отдаёт 500-ответ И ре-райзит исключение (чтобы
    сервер мог его залогировать). В проде браузер получает JSON-ответ; в тестах
    дефолтный ASGITransport ре-райзит → нужен этот флаг, чтобы увидеть сам ответ.
    """
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_unhandled_exception_returns_json_500(lenient_client):
    r = await lenient_client.get("/api/_test_boom")
    assert r.status_code == 500
    assert r.headers["content-type"].startswith("application/json")
    body = r.json()  # не должно падать — это и есть фикс «Unexpected token I»
    assert "detail" in body
    assert "request_id" in body


@pytest.mark.asyncio
async def test_integrity_error_returns_json_409(lenient_client):
    r = await lenient_client.get("/api/_test_integrity")
    assert r.status_code == 409
    assert r.headers["content-type"].startswith("application/json")
    body = r.json()
    assert "detail" in body
    assert "целостност" in body["detail"].lower()
