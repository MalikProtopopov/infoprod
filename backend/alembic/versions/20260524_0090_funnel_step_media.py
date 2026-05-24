"""funnel_step_media — медиа-вложения на шагах воронок (mediaGroup)

Создаёт таблицу funnel_step_media для хранения 0..10 файлов на каждом
шаге. Текущие записи lead_magnet_id у funnel_steps НЕ удаляются — это
обратная совместимость. Worker отправки в первую очередь смотрит
funnel_step_media; если их нет — fallback на старый lead_magnet_id.

Миграция данных: для каждого funnel_steps.lead_magnet_id != NULL,
у которого есть валидный lead_magnets.file_url с существующим файлом
на диске — создаётся одна запись funnel_step_media (order_idx=0,
media_type детектируется по lead_magnets.file_type). Это сохраняет
поведение для уже настроенных воронок при первой отправке после
деплоя; повторного аплоада не требуется.

Revision ID: 0090_funnel_step_media
Revises: 0080_funnel_trigger_unique
Create Date: 2026-05-24 12:00:00.000000
"""
from __future__ import annotations

import os
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0090_funnel_step_media"
down_revision: Union[str, None] = "0080_funnel_trigger_unique"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Маппинг lead_magnets.file_type → funnel_step_media.media_type
# `pdf` отправляется как document (это не специальный тип для Telegram).
_FILETYPE_TO_MEDIA: dict[str, str] = {
    "image": "photo",
    "video": "video",
    "pdf": "document",
    "document": "document",
}

# Маппинг file_type → MIME-fallback, когда мы не знаем точно
_FILETYPE_TO_MIME: dict[str, str] = {
    "image": "image/jpeg",
    "video": "video/mp4",
    "pdf": "application/pdf",
    "document": "application/octet-stream",
}


def upgrade() -> None:
    op.create_table(
        "funnel_step_media",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "funnel_step_id",
            sa.BigInteger(),
            sa.ForeignKey("funnel_steps.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("media_type", sa.String(length=16), nullable=False),
        sa.Column("storage_path", sa.String(length=512), nullable=False),
        sa.Column("original_filename", sa.String(length=512), nullable=True),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("duration", sa.Integer(), nullable=True),
        sa.Column(
            "order_idx",
            sa.SmallInteger(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("telegram_file_id", sa.String(length=255), nullable=True),
        sa.Column("thumbnail_path", sa.String(length=512), nullable=True),
        sa.Column("thumbnail_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "media_type IN ('photo','video','animation','audio','document','voice')",
            name="ck_funnel_step_media_type",
        ),
        sa.CheckConstraint(
            "order_idx >= 0 AND order_idx < 10",
            name="ck_funnel_step_media_order_range",
        ),
        sa.CheckConstraint(
            "file_size > 0 AND file_size <= 2147483648",
            name="ck_funnel_step_media_size_range",
        ),
    )

    op.create_index(
        "ix_funnel_step_media_step_order",
        "funnel_step_media",
        ["funnel_step_id", "order_idx"],
    )
    op.create_index(
        "ix_funnel_step_media_checksum",
        "funnel_step_media",
        ["checksum_sha256"],
    )

    # Уникальность (funnel_step_id, order_idx) — DEFERRABLE INITIALLY DEFERRED,
    # чтобы reorder мог свопить значения в одной транзакции.
    op.create_unique_constraint(
        "uq_funnel_step_media_step_order",
        "funnel_step_media",
        ["funnel_step_id", "order_idx"],
        deferrable=True,
        initially="DEFERRED",
    )

    # Миграция данных: переносим существующие lead_magnet_id ссылки.
    # Делаем это в Python (а не в SQL) потому что нужно прочитать размер
    # файла с диска (lead_magnets.file_size может быть NULL для старых записей).
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            """
            SELECT fs.id AS step_id,
                   lm.id AS lm_id,
                   lm.name AS lm_name,
                   lm.file_url AS file_url,
                   lm.file_type AS file_type,
                   lm.file_size AS file_size,
                   lm.telegram_file_id AS file_id
            FROM funnel_steps fs
            JOIN lead_magnets lm ON lm.id = fs.lead_magnet_id
            WHERE fs.lead_magnet_id IS NOT NULL
            """
        )
    ).mappings().all()

    for row in rows:
        file_path = row["file_url"]
        # Проверяем, что файл на месте. Если нет — пропускаем (старая
        # битая запись, лучше не создавать step_media с невалидным путём).
        if not file_path or not os.path.exists(file_path):
            continue

        file_size = row["file_size"] or os.path.getsize(file_path)
        if file_size <= 0:
            continue

        media_type = _FILETYPE_TO_MEDIA.get(row["file_type"], "document")
        mime = _FILETYPE_TO_MIME.get(row["file_type"], "application/octet-stream")
        filename = row["lm_name"] or os.path.basename(file_path)

        conn.execute(
            sa.text(
                """
                INSERT INTO funnel_step_media
                    (funnel_step_id, media_type, storage_path, original_filename,
                     mime_type, file_size, order_idx, telegram_file_id)
                VALUES
                    (:step_id, :media_type, :storage_path, :filename,
                     :mime, :file_size, 0, :file_id)
                """
            ),
            {
                "step_id": row["step_id"],
                "media_type": media_type,
                "storage_path": file_path,
                "filename": filename[:512],
                "mime": mime,
                "file_size": file_size,
                "file_id": row["file_id"],
            },
        )


def downgrade() -> None:
    op.drop_index("ix_funnel_step_media_checksum", table_name="funnel_step_media")
    op.drop_index("ix_funnel_step_media_step_order", table_name="funnel_step_media")
    op.drop_constraint("uq_funnel_step_media_step_order", "funnel_step_media", type_="unique")
    op.drop_table("funnel_step_media")
