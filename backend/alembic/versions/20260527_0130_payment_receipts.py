"""payment_receipts — чеки платежа (загрузка менеджером, до 3 на платёж).

Только загрузка: редактирование/удаление чеков на уровне продукта не
предусмотрено (нет UI/эндпойнтов). Файлы хранятся на диске
(/var/lib/infobizbot/receipts/{payment_id}/...), в БД — метаданные.

Revision ID: 0130_payment_receipts
Revises:    0120_lead_payment_cancel
Create Date: 2026-05-27 16:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0130_payment_receipts"
down_revision: Union[str, None] = "0120_lead_payment_cancel"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment_receipts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("payment_id", sa.BigInteger(), nullable=False),
        sa.Column("storage_path", sa.String(length=512), nullable=False),
        sa.Column("original_filename", sa.String(length=512), nullable=True),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("uploaded_by", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["admins.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_payment_receipts_payment_id", "payment_receipts", ["payment_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_payment_receipts_payment_id", table_name="payment_receipts")
    op.drop_table("payment_receipts")
