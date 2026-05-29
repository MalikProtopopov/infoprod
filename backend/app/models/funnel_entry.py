from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FunnelEntry(Base):
    __tablename__ = "funnel_entries"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    funnel_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("funnels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # 'tracking_link' | 'code_word' | 'lead_created' | 'manual'
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_ref: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 'active' | 'completed' | 'cancelled'
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    # Теги сегментации, проставленные track-кнопками (напр. ["hot"]). Шаги с
    # audience_tags показываются только если у entry есть нужный тег.
    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # Тестовый прогон (кнопка «Тест»): шаги идут даже на неактивной воронке;
    # исключается из аналитики.
    is_test: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
