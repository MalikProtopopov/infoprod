from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FunnelTrigger(Base):
    __tablename__ = "funnel_triggers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # Хранится в lowercase + uniq index по lower(word)
    word: Mapped[str] = mapped_column(Text, nullable=False)
    funnel_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("funnels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    use_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
