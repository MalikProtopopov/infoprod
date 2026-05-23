from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ScheduledMessage(Base):
    __tablename__ = "scheduled_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    funnel_entry_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("funnel_entries.id", ondelete="CASCADE"), nullable=True
    )
    funnel_step_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("funnel_steps.id", ondelete="SET NULL"), nullable=True
    )
    template_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
