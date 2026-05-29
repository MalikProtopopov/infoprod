"""Канал продукта необязателен.

Продукты-«лид-магниты» (бесплатная консультация / бриф) собирают заявки
без привязки к Telegram-каналу. Снимаем NOT NULL с products.channel_id.

Revision ID: 0150_product_channel_optional
Revises:    0140_product_content
Create Date: 2026-05-29 09:30:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0150_product_channel_optional"
down_revision: Union[str, None] = "0140_product_content"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "products",
        "channel_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )


def downgrade() -> None:
    # Перед возвратом NOT NULL продукты без канала нужно либо удалить, либо
    # привязать к каналу вручную — иначе ALTER упадёт. Оставляем строгий откат.
    op.alter_column(
        "products",
        "channel_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
