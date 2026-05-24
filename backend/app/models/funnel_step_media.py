"""FunnelStepMedia — медиа-вложения одного шага воронки.

Один шаг может содержать от 0 до 10 медиа (Telegram-лимит на media-group).
Если 0 — шаг шлётся как обычное текстовое сообщение. Если 1 — корректным
одиночным методом (send_photo / send_video / send_document / ...). Если ≥2 —
через send_media_group.

Поля по образцу `PostMedia` в проекте smmplaner — это позволяет в будущем
шарить логику отправки.

`lead_magnet_id` в `FunnelStep` остаётся для обратной совместимости: если
у шага media записей нет, но есть lead_magnet_id — отправляем как раньше.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


# Допустимые значения media_type — должны совпадать с
# `app.share.limits.infer_media_type`.
ALLOWED_MEDIA_TYPES = ("photo", "video", "animation", "audio", "document", "voice")


class FunnelStepMedia(Base):
    __tablename__ = "funnel_step_media"
    __table_args__ = (
        Index("ix_funnel_step_media_step_order", "funnel_step_id", "order_idx"),
        # Внутри одного шага каждый order_idx уникален. DEFERRABLE INITIALLY
        # DEFERRED, чтобы при reorder можно было свопить значения в одной
        # транзакции (см. PATCH /reorder).
        UniqueConstraint(
            "funnel_step_id",
            "order_idx",
            name="uq_funnel_step_media_step_order",
            deferrable=True,
            initially="DEFERRED",
        ),
        Index("ix_funnel_step_media_checksum", "checksum_sha256"),
        CheckConstraint(
            "media_type IN ('photo','video','animation','audio','document','voice')",
            name="ck_funnel_step_media_type",
        ),
        CheckConstraint(
            "order_idx >= 0 AND order_idx < 10",
            name="ck_funnel_step_media_order_range",
        ),
        CheckConstraint(
            "file_size > 0 AND file_size <= 2147483648",
            name="ck_funnel_step_media_size_range",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    funnel_step_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("funnel_steps.id", ondelete="CASCADE"),
        nullable=False,
    )

    media_type: Mapped[str] = mapped_column(String(16), nullable=False)
    # Полный путь к файлу на диске (или ключ в объектном хранилище, если перейдём).
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # Для photo/video — пикселы; для audio — None.
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Для video/audio/voice — в секундах. Извлекается на загрузке если возможно.
    duration: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Порядок внутри media-group. 0..9.
    order_idx: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0, server_default="0"
    )

    # Подпись к конкретному медиа. В Telegram media-group caption берётся
    # с первого элемента, но мы храним per-item для гибкости — пользователь
    # может назначить caption любому элементу, мы сами решим какой использовать.
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Telegram CDN file_id после первой отправки — переиспользуется без
    # повторной заливки. Привязан к конкретному боту: при смене бота нужно
    # пересохранять. Для простоты пока храним один глобальный — если бот
    # сменился, file_id просто не сработает и мы зальём заново.
    telegram_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Авто-кадр из видео для миниатюры в UI (генерируется async-task'ом).
    thumbnail_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    thumbnail_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # SHA-256 — для дедупликации и проверки целостности.
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
