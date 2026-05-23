from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Funnel(Base):
    __tablename__ = "funnels"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bot_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("bots.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ttl_days: Mapped[int] = mapped_column(Integer, nullable=False, default=90)
    cancel_on_payment: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("admins.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
