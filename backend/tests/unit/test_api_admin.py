"""API: POST /api/admin/password — смена пароля."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_change_password_success(admin_client, clean_db):
    """admin_client поднят с паролем testpass (см. conftest)."""
    r = await admin_client.post(
        "/api/admin/password",
        json={"old_password": "testpass", "new_password": "newPassword123"},
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True}


@pytest.mark.asyncio
async def test_change_password_wrong_old_returns_400(admin_client, clean_db):
    r = await admin_client.post(
        "/api/admin/password",
        json={"old_password": "wrong", "new_password": "newPassword123"},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_change_password_too_short_returns_422(admin_client, clean_db):
    r = await admin_client.post(
        "/api/admin/password",
        json={"old_password": "testpass", "new_password": "a"},  # < 6
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_change_password_requires_auth(api_client):
    r = await api_client.post(
        "/api/admin/password",
        json={"old_password": "x", "new_password": "newPass1234"},
    )
    assert r.status_code == 401
