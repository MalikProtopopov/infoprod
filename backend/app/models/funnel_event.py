"""FunnelEvent — зафиксированное действие пользователя внутри воронки.

Сейчас тип один — `click` по интерактивной кнопке-отметке (track-кнопка):
фиксирует факт нажатия (для CTR-аналитики) и, опционально, проставляет тег
сегмента на FunnelEntry (для ветвления через audience-фильтр шага) и/или
отвечает текстом. Также служит сигналом «было действие» для условий шага
(например «не слать день 14, если кликал CTA»).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FunnelEvent(Base):
    __tablename__ = "funnel_events"
    __table_args__ = (
        Index("ix_funnel_events_entry", "funnel_entry_id"),
        Index("ix_funnel_events_type_key", "event_type", "key"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    funnel_entry_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("funnel_entries.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # Шаг, на кнопке которого произошло событие (может быть None для системных).
    funnel_step_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # Тип события. Сейчас: 'click'. На будущее — 'answer' и т.п.
    event_type: Mapped[str] = mapped_column(String(16), nullable=False, default="click")
    # Ключ кнопки/действия (для CTR по конкретной кнопке).
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
