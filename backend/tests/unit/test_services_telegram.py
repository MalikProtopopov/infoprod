"""Unit-тесты services/telegram.

Используем AsyncMock на aiogram.Bot — не делаем реальных HTTP-вызовов.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.exceptions import TelegramAPIError

from app.services.telegram import (
    create_one_time_invite,
    ensure_bot_can_invite,
    get_chat_title,
    kick_user,
    send_message_safe,
)


# ───────── ensure_bot_can_invite ─────────


@pytest.mark.asyncio
async def test_ensure_can_invite_admin_with_rights():
    bot = MagicMock()
    me = MagicMock(); me.id = 1
    bot.get_me = AsyncMock(return_value=me)
    member = MagicMock(); member.status = "administrator"; member.can_invite_users = True
    bot.get_chat_member = AsyncMock(return_value=member)

    ok, reason = await ensure_bot_can_invite(bot, chat_id=-100)
    assert ok is True
    assert reason is None


@pytest.mark.asyncio
async def test_ensure_can_invite_admin_without_right():
    bot = MagicMock()
    me = MagicMock(); me.id = 1
    bot.get_me = AsyncMock(return_value=me)
    member = MagicMock(); member.status = "administrator"; member.can_invite_users = False
    bot.get_chat_member = AsyncMock(return_value=member)

    ok, reason = await ensure_bot_can_invite(bot, chat_id=-100)
    assert ok is False
    assert "приглашать" in reason


@pytest.mark.asyncio
async def test_ensure_can_invite_not_admin():
    bot = MagicMock()
    me = MagicMock(); me.id = 1
    bot.get_me = AsyncMock(return_value=me)
    member = MagicMock(); member.status = "member"
    bot.get_chat_member = AsyncMock(return_value=member)

    ok, reason = await ensure_bot_can_invite(bot, chat_id=-100)
    assert ok is False
    assert "администратор" in reason.lower()


@pytest.mark.asyncio
async def test_ensure_can_invite_handles_api_error():
    bot = MagicMock()
    bot.get_me = AsyncMock(side_effect=TelegramAPIError(method="X", message="boom"))

    ok, reason = await ensure_bot_can_invite(bot, chat_id=-100)
    assert ok is False
    assert "Telegram API" in reason


# ───────── get_chat_title ─────────


@pytest.mark.asyncio
async def test_get_chat_title_returns_title_and_username():
    bot = MagicMock()
    chat = MagicMock(); chat.title = "My Channel"; chat.username = "mych"
    bot.get_chat = AsyncMock(return_value=chat)

    title, username = await get_chat_title(bot, chat_id=-100)
    assert title == "My Channel"
    assert username == "mych"


@pytest.mark.asyncio
async def test_get_chat_title_on_error_returns_nones():
    bot = MagicMock()
    bot.get_chat = AsyncMock(side_effect=TelegramAPIError(method="X", message="boom"))

    title, username = await get_chat_title(bot, chat_id=-100)
    assert title is None
    assert username is None


# ───────── create_one_time_invite ─────────


@pytest.mark.asyncio
async def test_create_invite_basic():
    bot = MagicMock()
    link_obj = MagicMock(); link_obj.invite_link = "https://t.me/+abc"
    bot.create_chat_invite_link = AsyncMock(return_value=link_obj)

    result = await create_one_time_invite(bot, chat_id=-100)
    assert result == "https://t.me/+abc"
    bot.create_chat_invite_link.assert_awaited_once()
    call_kwargs = bot.create_chat_invite_link.await_args.kwargs
    assert call_kwargs["chat_id"] == -100
    assert call_kwargs["member_limit"] == 1
    assert "expire_date" not in call_kwargs


@pytest.mark.asyncio
async def test_create_invite_with_expire_at_passes_unix_timestamp():
    bot = MagicMock()
    link_obj = MagicMock(); link_obj.invite_link = "https://t.me/+xyz"
    bot.create_chat_invite_link = AsyncMock(return_value=link_obj)

    expire = datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    result = await create_one_time_invite(bot, chat_id=-100, expire_at=expire)
    assert result == "https://t.me/+xyz"
    call_kwargs = bot.create_chat_invite_link.await_args.kwargs
    assert call_kwargs["expire_date"] == int(expire.timestamp())


@pytest.mark.asyncio
async def test_create_invite_returns_none_on_api_error():
    bot = MagicMock()
    bot.create_chat_invite_link = AsyncMock(
        side_effect=TelegramAPIError(method="X", message="rate-limited"),
    )
    result = await create_one_time_invite(bot, chat_id=-100)
    assert result is None


# ───────── kick_user ─────────


@pytest.mark.asyncio
async def test_kick_user_bans_then_unbans():
    bot = MagicMock()
    bot.ban_chat_member = AsyncMock(return_value=True)
    bot.unban_chat_member = AsyncMock(return_value=True)

    ok = await kick_user(bot, chat_id=-100, telegram_user_id=42)
    assert ok is True
    bot.ban_chat_member.assert_awaited_once_with(chat_id=-100, user_id=42)
    bot.unban_chat_member.assert_awaited_once()


@pytest.mark.asyncio
async def test_kick_user_unban_error_is_swallowed():
    bot = MagicMock()
    bot.ban_chat_member = AsyncMock(return_value=True)
    bot.unban_chat_member = AsyncMock(
        side_effect=TelegramAPIError(method="X", message="not banned"),
    )

    ok = await kick_user(bot, chat_id=-100, telegram_user_id=42)
    assert ok is True  # main ban прошёл — успех


@pytest.mark.asyncio
async def test_kick_user_returns_false_on_ban_error():
    bot = MagicMock()
    bot.ban_chat_member = AsyncMock(
        side_effect=TelegramAPIError(method="X", message="forbidden"),
    )
    ok = await kick_user(bot, chat_id=-100, telegram_user_id=42)
    assert ok is False


# ───────── send_message_safe ─────────


@pytest.mark.asyncio
async def test_send_message_safe_returns_true_on_success():
    bot = MagicMock()
    bot.send_message = AsyncMock(return_value=MagicMock())
    ok = await send_message_safe(bot, chat_id=42, text="Hi")
    assert ok is True


@pytest.mark.asyncio
async def test_send_message_safe_returns_false_on_error():
    bot = MagicMock()
    bot.send_message = AsyncMock(
        side_effect=TelegramAPIError(method="X", message="user blocked"),
    )
    ok = await send_message_safe(bot, chat_id=42, text="Hi")
    assert ok is False
