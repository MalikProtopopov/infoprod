from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.channel import Channel


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # Канал необязателен: продукты-«лид-магниты» (бесплатная консультация/бриф)
    # собирают заявки без выдачи доступа в Telegram-канал.
    channel_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("channels.id", ondelete="RESTRICT"), nullable=True
    )
    price_3m: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    price_6m: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    price_12m: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="RUB", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Воронка, запускаемая автоматически при создании лида на этот продукт
    default_funnel_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("funnels.id", ondelete="SET NULL"), nullable=True
    )
    # --- Контент карточки в боте ---
    # Стилизованный текст карточки (HTML: b/i/u/s, blockquote expandable, spoiler, ссылки).
    # Если пусто — используется plain `description`.
    card_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Благодарственное сообщение после покупки (стилизованное).
    thank_you_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Слать ли блоки презентации при открытии продукта.
    presentation_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    channel: Mapped["Channel | None"] = relationship(back_populates="products")
