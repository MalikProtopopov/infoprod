"""Message — лог переписки пользователя с конкретным ботом (мультибот).

direction: 'in' — пользователь написал боту, 'out' — отправили мы (воронка
или менеджер вручную). Для 'out' от менеджера проставляется sent_by_admin_id.
Это даёт экран чата в админке и историю по каждому (user, bot).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_user_bot_time", "user_id", "bot_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    bot_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False
    )
    direction: Mapped[str] = mapped_column(String(3), nullable=False)  # 'in' | 'out'
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    tg_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # Кто отправил (для исходящих из админки). None — авто (воронка) или входящее.
    sent_by_admin_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("admins.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
