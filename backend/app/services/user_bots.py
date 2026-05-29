"""Сервис связей user↔bot: отметить контакт, выставить/снять блокировку."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_bot import UserBot


async def touch(session: AsyncSession, *, user_id: int, bot_id: int) -> None:
    """Зафиксировать контакт пользователя с ботом (insert или обновить last_seen).

    Контакт «оживляет» пару: если бот ранее был помечен заблокированным, а юзер
    снова написал — снимаем флаг (значит разблокировал/перезапустил).
    """
    now = datetime.now(tz=timezone.utc)
    stmt = pg_insert(UserBot).values(
        user_id=user_id, bot_id=bot_id, first_seen_at=now, last_seen_at=now,
        is_blocked=False, blocked_at=None,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_user_bot",
        set_={"last_seen_at": now, "is_blocked": False, "blocked_at": None},
    )
    await session.execute(stmt)


async def set_blocked(session: AsyncSession, *, user_id: int, bot_id: int, blocked: bool = True) -> None:
    """Пометить пару (user, bot) как заблокированную (или снять). Если пары
    ещё нет — создаём её (на случай блокировки до записи контакта)."""
    now = datetime.now(tz=timezone.utc)
    res = await session.execute(
        update(UserBot)
        .where(UserBot.user_id == user_id, UserBot.bot_id == bot_id)
        .values(is_blocked=blocked, blocked_at=now if blocked else None)
    )
    if res.rowcount == 0 and blocked:
        stmt = pg_insert(UserBot).values(
            user_id=user_id, bot_id=bot_id, first_seen_at=now, last_seen_at=now,
            is_blocked=True, blocked_at=now,
        ).on_conflict_do_update(
            constraint="uq_user_bot",
            set_={"is_blocked": True, "blocked_at": now},
        )
        await session.execute(stmt)
