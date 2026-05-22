"""Edge cases для api/channels add_channel — все ветки."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_add_channel_bot_not_running_calls_sync(
    admin_client, make_committed, monkeypatch, clean_db,
):
    """get_aiogram_bot returns None → manager.sync() → второй get_aiogram_bot."""
    sync_called = AsyncMock()
    monkeypatch.setattr("app.api.channels.bot_manager.sync", sync_called)
    # Первый раз None, потом возвращаем bot
    fake_bot = MagicMock()
    calls = [0]
    def _get(_):
        calls[0] += 1
        return None if calls[0] == 1 else fake_bot
    monkeypatch.setattr("app.api.channels.bot_manager.get_aiogram_bot", _get)

    async def _ok(*a, **kw): return True, None
    async def _title(*a, **kw): return "Title", None
    monkeypatch.setattr("app.api.channels.tg.ensure_bot_can_invite", _ok)
    monkeypatch.setattr("app.api.channels.tg.get_chat_title", _title)

    bot = await make_committed.bot()
    r = await admin_client.post(
        "/api/channels",
        json={"bot_id": bot.id, "telegram_chat_id": -1009999999999},
    )
    assert r.status_code == 201
    sync_called.assert_awaited()


@pytest.mark.asyncio
async def test_add_channel_bot_still_not_running_after_sync(
    admin_client, make_committed, monkeypatch, clean_db,
):
    """Если sync ничего не дал — возвращаем 400."""
    monkeypatch.setattr("app.api.channels.bot_manager.sync", AsyncMock())
    monkeypatch.setattr("app.api.channels.bot_manager.get_aiogram_bot", lambda _: None)

    bot = await make_committed.bot()
    r = await admin_client.post(
        "/api/channels",
        json={"bot_id": bot.id, "telegram_chat_id": -1009999999998},
    )
    assert r.status_code == 400
    assert "запущен" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_add_channel_with_explicit_title_and_username(
    admin_client, make_committed, monkeypatch, clean_db,
):
    """Если передали title/username — они берутся, а не из tg.get_chat_title."""
    monkeypatch.setattr("app.api.channels.bot_manager.get_aiogram_bot", lambda _: MagicMock())
    monkeypatch.setattr("app.api.channels.bot_manager.sync", AsyncMock())
    async def _ok(*a, **kw): return True, None
    async def _title(*a, **kw): return "Other Title", "other_user"
    monkeypatch.setattr("app.api.channels.tg.ensure_bot_can_invite", _ok)
    monkeypatch.setattr("app.api.channels.tg.get_chat_title", _title)

    bot = await make_committed.bot()
    r = await admin_client.post(
        "/api/channels",
        json={
            "bot_id": bot.id,
            "telegram_chat_id": -1009999999997,
            "title": "My Custom Title",
            "username": "my_username",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["title"] == "My Custom Title"
    assert body["username"] == "my_username"


@pytest.mark.asyncio
async def test_add_channel_uses_tg_title_when_not_provided(
    admin_client, make_committed, monkeypatch, clean_db,
):
    monkeypatch.setattr("app.api.channels.bot_manager.get_aiogram_bot", lambda _: MagicMock())
    monkeypatch.setattr("app.api.channels.bot_manager.sync", AsyncMock())
    async def _ok(*a, **kw): return True, None
    async def _title(*a, **kw): return "From TG", "tg_user"
    monkeypatch.setattr("app.api.channels.tg.ensure_bot_can_invite", _ok)
    monkeypatch.setattr("app.api.channels.tg.get_chat_title", _title)

    bot = await make_committed.bot()
    r = await admin_client.post(
        "/api/channels",
        json={"bot_id": bot.id, "telegram_chat_id": -1009999999996},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["title"] == "From TG"
    assert body["username"] == "tg_user"


@pytest.mark.asyncio
async def test_add_channel_fallback_title_when_tg_none(
    admin_client, make_committed, monkeypatch, clean_db,
):
    """Если tg.get_chat_title вернул None — title = 'Channel <chat_id>'."""
    monkeypatch.setattr("app.api.channels.bot_manager.get_aiogram_bot", lambda _: MagicMock())
    monkeypatch.setattr("app.api.channels.bot_manager.sync", AsyncMock())
    async def _ok(*a, **kw): return True, None
    async def _title(*a, **kw): return None, None
    monkeypatch.setattr("app.api.channels.tg.ensure_bot_can_invite", _ok)
    monkeypatch.setattr("app.api.channels.tg.get_chat_title", _title)

    bot = await make_committed.bot()
    r = await admin_client.post(
        "/api/channels",
        json={"bot_id": bot.id, "telegram_chat_id": -1009999999995},
    )
    assert r.status_code == 201
    body = r.json()
    assert "Channel" in body["title"]
