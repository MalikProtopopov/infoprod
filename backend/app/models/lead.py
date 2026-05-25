from __future__ import annotations

from datetime import datetime

from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # nullable: лид может прийти из form-шага воронки без привязки к продукту
    product_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="CASCADE"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="new", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # form-шаг, из которого пришёл лид (если применимо)
    form_step_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("funnel_steps.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # ответы юзера на поля формы (ключ-значение по схеме form_data.fields[].key)
    extra_data: Mapped[Any | None] = mapped_column(JSONB, nullable=True)

    # --- атрибуция last-touch (Phase 1) ---
    tracking_link_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("tracking_links.id", ondelete="SET NULL"), nullable=True
    )
    utm_source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    utm_medium: Mapped[str | None] = mapped_column(String(255), nullable=True)
    utm_campaign: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # --- материализованные таймстампы смены статуса ---
    contacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
