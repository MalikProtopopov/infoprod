"""UserBot — связь «пользователь ↔ бот» (мультибот).

User глобально уникален по telegram_user_id (один человек = одна запись).
Но один и тот же человек может писать в РАЗНЫЕ боты — и нам нужно знать:
в каких ботах он был, когда последний контакт, и заблокирован ли конкретный
бот именно у него. Этого нет в самой записи User (там лишь first_bot_id —
первое касание), поэтому ведём отдельную таблицу пар (user, bot).

Используется для: колонки/фильтра «бот» в списке юзеров, выбора бота для
ручной отправки, индикатора блокировки, статистики по боту.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserBot(Base):
    __tablename__ = "user_bots"
    __table_args__ = (
        UniqueConstraint("user_id", "bot_id", name="uq_user_bot"),
        Index("ix_user_bots_bot", "bot_id"),
        Index("ix_user_bots_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    bot_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Заблокировал ли пользователь ИМЕННО этого бота (per-bot).
    is_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    blocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
