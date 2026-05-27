"""Контент продукта: блоки презентации + медиа + поля карточки/благодарности.

- products: card_text (styled HTML), thank_you_message (styled HTML),
  presentation_enabled (слать ли блоки при открытии продукта).
- product_content_block: упорядоченные блоки презентации (text/media/video_note/voice).
- product_media: медиа блока (зеркало funnel_step_media), media_type включает video_note.

Revision ID: 0140_product_content
Revises:    0130_payment_receipts
Create Date: 2026-05-27 16:30:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0140_product_content"
down_revision: Union[str, None] = "0130_payment_receipts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("products", sa.Column("card_text", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("thank_you_message", sa.Text(), nullable=True))
    op.add_column(
        "products",
        sa.Column(
            "presentation_enabled", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
    )

    op.create_table(
        "product_content_block",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("order_idx", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("kind", sa.String(length=16), nullable=False, server_default="text"),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("delay_ms", sa.Integer(), nullable=False, server_default="800"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "kind IN ('text','media','video_note','voice')",
            name="ck_product_content_block_kind",
        ),
    )
    op.create_index(
        "ix_product_content_block_product_order",
        "product_content_block",
        ["product_id", "order_idx"],
    )

    op.create_table(
        "product_media",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("block_id", sa.BigInteger(), nullable=False),
        sa.Column("media_type", sa.String(length=16), nullable=False),
        sa.Column("storage_path", sa.String(length=512), nullable=False),
        sa.Column("original_filename", sa.String(length=512), nullable=True),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("duration", sa.Integer(), nullable=True),
        sa.Column("order_idx", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("telegram_file_id", sa.String(length=255), nullable=True),
        sa.Column("thumbnail_path", sa.String(length=512), nullable=True),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["block_id"], ["product_content_block.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "media_type IN ('photo','video','animation','audio','document','voice','video_note')",
            name="ck_product_media_type",
        ),
        sa.CheckConstraint("order_idx >= 0 AND order_idx < 10", name="ck_product_media_order"),
    )
    op.create_index("ix_product_media_block_order", "product_media", ["block_id", "order_idx"])


def downgrade() -> None:
    op.drop_index("ix_product_media_block_order", table_name="product_media")
    op.drop_table("product_media")
    op.drop_index("ix_product_content_block_product_order", table_name="product_content_block")
    op.drop_table("product_content_block")
    op.drop_column("products", "presentation_enabled")
    op.drop_column("products", "thank_you_message")
    op.drop_column("products", "card_text")
