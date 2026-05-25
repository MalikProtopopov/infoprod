from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FunnelStep(Base):
    __tablename__ = "funnel_steps"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('message','quiz','form')",
            name="ck_funnel_steps_kind",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    funnel_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("funnels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_idx: Mapped[int] = mapped_column(Integer, nullable=False)
    delay_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    parse_mode: Mapped[str | None] = mapped_column(String(16), nullable=True, default="HTML")
    lead_magnet_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("lead_magnets.id", ondelete="SET NULL"), nullable=True
    )
    buttons: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Тип шага: 'message' — обычный, 'quiz' — интерактивный квиз с подсчётом,
    # 'form' — последовательный сбор ответов с сохранением в Lead.extra_data.
    # У quiz/form шагов используются quiz_data/form_data; у message — нет.
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="message", server_default="message")
    quiz_data: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    form_data: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
