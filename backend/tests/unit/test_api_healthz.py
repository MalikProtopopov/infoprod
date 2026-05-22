"""Smoke-тест: healthz без авторизации."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_healthz_returns_ok(api_client):
    r = await api_client.get("/api/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


@pytest.mark.asyncio
async def test_healthz_does_not_require_auth(api_client):
    r = await api_client.get("/api/healthz")
    assert r.status_code != 401
