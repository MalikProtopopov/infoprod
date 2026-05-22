"""Auth: login / logout / me / wrong-password / rate-limit."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

import pytest


@pytest.mark.asyncio
async def test_login_with_wrong_password_returns_401(api_client, engine, clean_db):
    # Создаём админа в БД (отдельно от api_client сессии)
    from app.core.security import hash_password
    from app.models.admin import Admin

    async with async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)() as s:
        s.add(Admin(username="admin", password_hash=hash_password("rightpass")))
        await s.commit()

    r = await api_client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401
    assert "Неверный" in r.json()["detail"]


@pytest.mark.asyncio
async def test_login_success_sets_cookie(api_client, engine, clean_db):
    from app.core.security import hash_password
    from app.models.admin import Admin

    async with async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)() as s:
        s.add(Admin(username="admin", password_hash=hash_password("goodpass")))
        await s.commit()

    r = await api_client.post("/api/auth/login", json={"username": "admin", "password": "goodpass"})
    assert r.status_code == 200
    assert r.json()["ok"] is True
    set_cookie = r.headers.get("set-cookie", "").lower()
    assert "access_token=" in set_cookie
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie


@pytest.mark.asyncio
async def test_me_requires_auth(api_client):
    # Без cookie — 401
    r = await api_client.get("/api/auth/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_admin_info(admin_client, clean_db):
    r = await admin_client.get("/api/auth/me")
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "test_admin"
    assert isinstance(body["id"], int)
