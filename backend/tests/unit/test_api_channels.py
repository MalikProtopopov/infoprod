"""API: CRUD /api/channels — добавление с проверкой прав бота, FK на удаление."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_bot_admin_can_invite(monkeypatch):
    """Эмулируем что бот — админ канала с правом invite."""
    fake_aiogram_bot = MagicMock()
    monkeypatch.setattr("app.api.channels.bot_manager.get_aiogram_bot", lambda _: fake_aiogram_bot)
    monkeypatch.setattr("app.api.channels.bot_manager.sync", AsyncMock())

    async def _ok(bot, chat_id):
        return True, None
    async def _title(bot, chat_id):
        return f"Channel {chat_id}", None

    monkeypatch.setattr("app.api.channels.tg.ensure_bot_can_invite", _ok)
    monkeypatch.setattr("app.api.channels.tg.get_chat_title", _title)
    return fake_aiogram_bot


@pytest.fixture
def mock_bot_not_admin(monkeypatch):
    monkeypatch.setattr("app.api.channels.bot_manager.get_aiogram_bot", lambda _: MagicMock())
    monkeypatch.setattr("app.api.channels.bot_manager.sync", AsyncMock())
    async def _fail(bot, chat_id):
        return False, "Бот не является администратором канала"
    async def _title(bot, chat_id):
        return None, None
    monkeypatch.setattr("app.api.channels.tg.ensure_bot_can_invite", _fail)
    monkeypatch.setattr("app.api.channels.tg.get_chat_title", _title)


@pytest.mark.asyncio
async def test_list_channels_empty(admin_client, clean_db):
    r = await admin_client.get("/api/channels")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_add_channel_success(admin_client, make_committed, mock_bot_admin_can_invite, clean_db):
    bot = await make_committed.bot()
    r = await admin_client.post(
        "/api/channels",
        json={"bot_id": bot.id, "telegram_chat_id": -1001234567890, "title": "Test channel"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["telegram_chat_id"] == -1001234567890
    assert body["title"] == "Test channel"
    assert body["bot_id"] == bot.id


@pytest.mark.asyncio
async def test_add_channel_with_inactive_bot_returns_400(admin_client, make_committed, clean_db):
    bot = await make_committed.bot(is_active=False)
    r = await admin_client.post(
        "/api/channels",
        json={"bot_id": bot.id, "telegram_chat_id": -1001234567899},
    )
    assert r.status_code == 400
    assert "не найден или неактивен" in r.json()["detail"]


@pytest.mark.asyncio
async def test_add_channel_with_unknown_bot_returns_400(admin_client, clean_db):
    r = await admin_client.post(
        "/api/channels",
        json={"bot_id": 99999, "telegram_chat_id": -100},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_add_channel_when_bot_not_admin_in_channel_returns_400(
    admin_client, make_committed, mock_bot_not_admin, clean_db,
):
    bot = await make_committed.bot()
    r = await admin_client.post(
        "/api/channels",
        json={"bot_id": bot.id, "telegram_chat_id": -1001234567891},
    )
    assert r.status_code == 400
    assert "администратор" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_add_duplicate_channel_returns_409(admin_client, make_committed, mock_bot_admin_can_invite, clean_db):
    bot = await make_committed.bot()
    await make_committed.channel(bot=bot, telegram_chat_id=-1001234567892)
    r = await admin_client.post(
        "/api/channels",
        json={"bot_id": bot.id, "telegram_chat_id": -1001234567892},
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_patch_channel_renames(admin_client, make_committed, clean_db):
    channel = await make_committed.channel(title="Old name")
    r = await admin_client.patch(f"/api/channels/{channel.id}", json={"title": "New name"})
    assert r.status_code == 200
    assert r.json()["title"] == "New name"


@pytest.mark.asyncio
async def test_delete_channel_without_products(admin_client, make_committed, clean_db):
    channel = await make_committed.channel()
    r = await admin_client.delete(f"/api/channels/{channel.id}")
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_delete_channel_with_products_returns_409(admin_client, make_committed, clean_db):
    channel = await make_committed.channel()
    await make_committed.product(channel=channel)
    r = await admin_client.delete(f"/api/channels/{channel.id}")
    assert r.status_code == 409
    assert "продуктов" in r.json()["detail"]


@pytest.mark.asyncio
async def test_delete_channel_with_active_subs_returns_409(admin_client, make_committed, clean_db):
    channel = await make_committed.channel()
    await make_committed.subscription(channel=channel, status="active")
    r = await admin_client.delete(f"/api/channels/{channel.id}")
    assert r.status_code == 409
    assert "подписок" in r.json()["detail"]


@pytest.mark.asyncio
async def test_list_channels_includes_counts(admin_client, make_committed, clean_db):
    channel = await make_committed.channel()
    await make_committed.product(channel=channel)
    await make_committed.product(channel=channel)
    await make_committed.subscription(channel=channel, status="active")
    await make_committed.subscription(channel=channel, status="expired")

    r = await admin_client.get("/api/channels")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["products_count"] == 2
    assert rows[0]["active_subs_count"] == 1  # только active считаются
