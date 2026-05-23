"""Тесты rate-limit на /api/auth/login."""
from __future__ import annotations

import pytest

from app.api.auth import _login_attempts, _check_login_rate_limit


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    _login_attempts.clear()
    yield
    _login_attempts.clear()


def test_rate_limit_allows_below_threshold():
    for _ in range(9):
        _check_login_rate_limit("1.2.3.4")
    # 10-я попытка пройдёт
    _check_login_rate_limit("1.2.3.4")


def test_rate_limit_blocks_at_threshold():
    from fastapi import HTTPException
    for _ in range(10):
        _check_login_rate_limit("1.2.3.4")
    with pytest.raises(HTTPException) as exc:
        _check_login_rate_limit("1.2.3.4")
    assert exc.value.status_code == 429
    assert "много попыток" in exc.value.detail


def test_rate_limit_isolated_per_ip():
    for _ in range(10):
        _check_login_rate_limit("1.2.3.4")
    # Другой IP — свободен
    _check_login_rate_limit("5.6.7.8")


@pytest.mark.asyncio
async def test_login_returns_401_for_unknown_user(api_client):
    r = await api_client.post(
        "/api/auth/login", json={"username": "nosuch", "password": "x"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_logout_clears_cookie(admin_client):
    r = await admin_client.post("/api/auth/logout")
    assert r.status_code == 200
    set_cookie = r.headers.get("set-cookie", "").lower()
    assert "max-age=0" in set_cookie or "expires=" in set_cookie or "deleted" in set_cookie


@pytest.mark.asyncio
async def test_me_returns_id_and_username(admin_client):
    r = await admin_client.get("/api/auth/me")
    assert r.status_code == 200
    body = r.json()
    assert "id" in body
    assert "username" in body
