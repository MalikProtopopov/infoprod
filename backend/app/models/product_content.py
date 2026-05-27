"""Контент-блоки продукта для презентации в боте.

Упорядоченная последовательность блоков, доставляемых при открытии продукта —
эффект «живого» менеджера: текст со стилями, медиа-галерея, кружок (video_note),
голосовое. Медиа блока — в ProductMedia (зеркало FunnelStepMedia).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# kind блока: text | media (1..10 фото/видео/док) | video_note (кружок) | voice (голос)
BLOCK_KINDS = ("text", "media", "video_note", "voice")
# типы медиа (как у funnel_step_media + video_note)
PRODUCT_MEDIA_TYPES = (
    "photo", "video", "animation", "audio", "document", "voice", "video_note",
)


class ProductContentBlock(Base):
    __tablename__ = "product_content_block"
    __table_args__ = (
        Index("ix_product_content_block_product_order", "product_id", "order_idx"),
        CheckConstraint(
            "kind IN ('text','media','video_note','voice')",
            name="ck_product_content_block_kind",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    order_idx: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="text", server_default="text")
    # Текст блока (для kind='text') или подпись к одиночному медиа/голосу.
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Задержка перед отправкой (мс) — имитация набора «живым» менеджером.
    delay_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=800, server_default="800")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    media: Mapped[list["ProductMedia"]] = relationship(
        back_populates="block",
        cascade="all, delete-orphan",
        order_by="ProductMedia.order_idx",
    )


class ProductMedia(Base):
    __tablename__ = "product_media"
    __table_args__ = (
        Index("ix_product_media_block_order", "block_id", "order_idx"),
        CheckConstraint(
            "media_type IN ('photo','video','animation','audio','document','voice','video_note')",
            name="ck_product_media_type",
        ),
        CheckConstraint("order_idx >= 0 AND order_idx < 10", name="ck_product_media_order"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    block_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("product_content_block.id", ondelete="CASCADE"), nullable=False
    )
    media_type: Mapped[str] = mapped_column(String(16), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    order_idx: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, server_default="0")
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    telegram_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    block: Mapped["ProductContentBlock"] = relationship(back_populates="media")
