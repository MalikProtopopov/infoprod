"""API: CRUD /api/bots — добавление с моком tg.get_me, FK-проверки."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def mock_tg_get_me(monkeypatch):
    """Мокаем services.telegram.get_me — не делаем реальных запросов в TG."""
    async def _ok(token: str):
        return {"id": 99999, "is_bot": True, "username": "mockedbot", "first_name": "Mocked"}
    monkeypatch.setattr("app.api.bots.tg.get_me", _ok)
    return _ok


@pytest.fixture
def mock_tg_bad_token(monkeypatch):
    async def _bad(token: str):
        raise RuntimeError("Token is invalid!")
    monkeypatch.setattr("app.api.bots.tg.get_me", _bad)


@pytest.fixture
def mock_bot_manager_sync(monkeypatch):
    """bot_manager.sync() ходит в Telegram — мокаем."""
    monkeypatch.setattr("app.bot.manager.sync", AsyncMock())


@pytest.mark.asyncio
async def test_list_bots_empty(admin_client, clean_db):
    r = await admin_client.get("/api/bots")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_list_bots_requires_auth(api_client):
    r = await api_client.get("/api/bots")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_create_bot_with_valid_token(admin_client, mock_tg_get_me, mock_bot_manager_sync, clean_db):
    r = await admin_client.post(
        "/api/bots",
        json={"token": "12345678:AAAAAABBBBBBCCCCCCDDDDDDEEEEEEFFFFFF"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["username"] == "mockedbot"
    assert body["telegram_bot_id"] == 99999
    assert body["is_active"] is True
    assert "…" in body["token_mask"]  # маска


@pytest.mark.asyncio
async def test_create_bot_with_invalid_token_returns_400(admin_client, mock_tg_bad_token, clean_db):
    r = await admin_client.post(
        "/api/bots",
        json={"token": "12345678:invalidtokenforsure_yes_invalid"},
    )
    assert r.status_code == 400
    assert "Token is invalid" in r.json()["detail"]


@pytest.mark.asyncio
async def test_create_bot_with_short_token_returns_422(admin_client, clean_db):
    r = await admin_client.post("/api/bots", json={"token": "short"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_duplicate_bot_returns_409(
    admin_client, mock_tg_get_me, mock_bot_manager_sync, clean_db,
):
    token = "12345678:DUPDUPDUPDUPDUPDUPDUPDUPDUPDUP"
    r1 = await admin_client.post("/api/bots", json={"token": token})
    assert r1.status_code == 201
    r2 = await admin_client.post("/api/bots", json={"token": token})
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_patch_bot_toggles_is_active(
    admin_client, make_committed, mock_bot_manager_sync, clean_db,
):
    bot = await make_committed.bot(is_active=True)
    r = await admin_client.patch(f"/api/bots/{bot.id}", json={"is_active": False})
    assert r.status_code == 200
    assert r.json()["is_active"] is False


@pytest.mark.asyncio
async def test_patch_unknown_bot_returns_404(admin_client, clean_db):
    r = await admin_client.patch("/api/bots/99999", json={"is_active": False})
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_bot_without_channels(admin_client, make_committed, mock_bot_manager_sync, clean_db):
    bot = await make_committed.bot()
    r = await admin_client.delete(f"/api/bots/{bot.id}")
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_delete_bot_with_channels_returns_409(admin_client, make_committed, clean_db):
    bot = await make_committed.bot()
    await make_committed.channel(bot=bot)
    r = await admin_client.delete(f"/api/bots/{bot.id}")
    assert r.status_code == 409
    assert "каналов" in r.json()["detail"]


@pytest.mark.asyncio
async def test_list_bots_includes_channels_and_products_count(admin_client, make_committed, clean_db):
    bot = await make_committed.bot()
    ch1 = await make_committed.channel(bot=bot)
    ch2 = await make_committed.channel(bot=bot)
    await make_committed.product(channel=ch1)
    await make_committed.product(channel=ch1)
    await make_committed.product(channel=ch2)

    r = await admin_client.get("/api/bots")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["channels_count"] == 2
    assert rows[0]["products_count"] == 3
