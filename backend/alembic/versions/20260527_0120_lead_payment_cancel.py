"""leads: привязка к платежу + причина отмены.

- leads.payment_id (FK → payments.id, SET NULL) — какой платёж закрыл заявку.
  Статусы paid/closed теперь требуют привязанный платёж (enforced в API).
- leads.cancel_reason (Text) — причина для статуса cancelled (пресет или своя).
- leads.cancelled_at — таймстамп отмены.

Новый статус 'cancelled' — это строковое значение leads.status, отдельной
миграции типа не требует (status хранится как String).

Revision ID: 0120_lead_payment_cancel
Revises:    0110_quizzes_forms_tables
Create Date: 2026-05-27 14:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0120_lead_payment_cancel"
down_revision: Union[str, None] = "0110_quizzes_forms_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("payment_id", sa.BigInteger(), nullable=True))
    op.add_column("leads", sa.Column("cancel_reason", sa.Text(), nullable=True))
    op.add_column(
        "leads", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_foreign_key(
        "fk_leads_payment_id",
        "leads",
        "payments",
        ["payment_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_leads_payment_id", "leads", ["payment_id"])


def downgrade() -> None:
    op.drop_index("ix_leads_payment_id", table_name="leads")
    op.drop_constraint("fk_leads_payment_id", "leads", type_="foreignkey")
    op.drop_column("leads", "cancelled_at")
    op.drop_column("leads", "cancel_reason")
    op.drop_column("leads", "payment_id")
