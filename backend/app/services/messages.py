"""Лог сообщений (чат). Тонкий helper поверх модели Message."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message


async def log(
    session: AsyncSession,
    *,
    user_id: int,
    bot_id: int,
    direction: str,
    text: str | None,
    tg_message_id: int | None = None,
    sent_by_admin_id: int | None = None,
) -> None:
    """Записать сообщение в лог переписки. Не коммитит — коммитит вызывающий."""
    session.add(Message(
        user_id=user_id,
        bot_id=bot_id,
        direction=direction,
        text=(text or None),
        tg_message_id=tg_message_id,
        sent_by_admin_id=sent_by_admin_id,
    ))
