from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    language_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # --- атрибуция (Phase 1) ---
    # first-touch: записывается один раз при создании пользователя, далее НЕ перезаписывается
    first_product_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    first_tracking_link_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("tracking_links.id", ondelete="SET NULL"), nullable=True
    )
    first_utm_source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_utm_medium: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_utm_campaign: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_bot_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("bots.id", ondelete="SET NULL"), nullable=True
    )
    # current: контекст «откуда пришёл сейчас» для последующего lead, TTL 30 минут
    current_tracking_link_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("tracking_links.id", ondelete="SET NULL"), nullable=True
    )
    current_link_set_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
