from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LeadMagnet(Base):
    __tablename__ = "lead_magnets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_url: Mapped[str] = mapped_column(Text, nullable=False)
    file_type: Mapped[str] = mapped_column(String(32), nullable=False)  # pdf, image, video, document
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Telegram file_id для reuse — заполняется после первой отправки
    telegram_file_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    download_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("admins.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
