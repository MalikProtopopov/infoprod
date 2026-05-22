"""Утилиты работы с Telegram через aiogram.

Все функции принимают aiogram.Bot и не хранят токен сами — это позволяет
переиспользовать активные экземпляры из multi-bot менеджера.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

logger = logging.getLogger(__name__)


async def get_me(token: str) -> dict:
    """Проверка токена. Возвращает dict с id/username/first_name."""
    bot = Bot(token=token)
    try:
        me = await bot.get_me()
        return {
            "id": me.id,
            "username": me.username or "",
            "first_name": me.first_name or "",
            "is_bot": me.is_bot,
        }
    finally:
        await bot.session.close()


async def ensure_bot_can_invite(bot: Bot, chat_id: int) -> tuple[bool, str | None]:
    """Проверка, что бот — администратор в канале и может приглашать."""
    try:
        me = await bot.get_me()
        member = await bot.get_chat_member(chat_id=chat_id, user_id=me.id)
        status = getattr(member, "status", "")
        if status not in ("administrator", "creator"):
            return False, "Бот не является администратором канала"
        can_invite = getattr(member, "can_invite_users", None)
        if can_invite is False:
            return False, "У бота нет прав приглашать пользователей"
        return True, None
    except TelegramAPIError as e:
        return False, f"Telegram API: {e}"


async def get_chat_title(bot: Bot, chat_id: int) -> tuple[str | None, str | None]:
    try:
        chat = await bot.get_chat(chat_id=chat_id)
        return chat.title, chat.username
    except TelegramAPIError as e:
        logger.warning("get_chat failed for %s: %s", chat_id, e)
        return None, None


async def create_one_time_invite(bot: Bot, chat_id: int, expire_at: Optional[datetime] = None) -> str | None:
    """Создаёт invite‑ссылку с member_limit=1."""
    try:
        kwargs: dict = {"chat_id": chat_id, "member_limit": 1}
        if expire_at:
            # aiogram примет datetime, но безопаснее передать int unix
            kwargs["expire_date"] = int(expire_at.replace(tzinfo=expire_at.tzinfo or timezone.utc).timestamp())
        link = await bot.create_chat_invite_link(**kwargs)
        return link.invite_link
    except TelegramAPIError as e:
        logger.warning("create_chat_invite_link failed for %s: %s", chat_id, e)
        return None


async def kick_user(bot: Bot, chat_id: int, telegram_user_id: int) -> bool:
    """Удалить пользователя из канала. После ban сразу unban, чтобы можно было вернуться."""
    try:
        await bot.ban_chat_member(chat_id=chat_id, user_id=telegram_user_id)
        try:
            await bot.unban_chat_member(chat_id=chat_id, user_id=telegram_user_id, only_if_banned=True)
        except TelegramAPIError:
            pass
        return True
    except TelegramAPIError as e:
        logger.warning("kick_user failed for chat=%s user=%s: %s", chat_id, telegram_user_id, e)
        return False


async def send_message_safe(bot: Bot, chat_id: int, text: str, reply_markup=None) -> bool:
    try:
        await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, disable_web_page_preview=True)
        return True
    except TelegramAPIError as e:
        logger.warning("send_message failed for chat=%s: %s", chat_id, e)
        return False
