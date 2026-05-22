"""payments attribution: admin_id + tracking_link_id

Revision ID: 0040_payments_attribution
Revises: 0030_leads_attribution
Create Date: 2026-05-23 00:03:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0040_payments_attribution"
down_revision: Union[str, None] = "0030_leads_attribution"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("payments") as b:
        b.add_column(sa.Column("admin_id", sa.BigInteger(), nullable=True))
        b.add_column(sa.Column("tracking_link_id", sa.BigInteger(), nullable=True))

    op.create_foreign_key(
        "fk_payments_admin", "payments", "admins",
        ["admin_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_payments_tracking_link", "payments", "tracking_links",
        ["tracking_link_id"], ["id"], ondelete="SET NULL",
    )

    op.create_index(
        "idx_payments_admin", "payments", ["admin_id"],
        postgresql_where=sa.text("admin_id IS NOT NULL"),
    )
    op.create_index(
        "idx_payments_tracking_link", "payments", ["tracking_link_id"],
        postgresql_where=sa.text("tracking_link_id IS NOT NULL"),
    )
    op.create_index(
        "idx_payments_created", "payments", [sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_payments_created", table_name="payments")
    op.drop_index("idx_payments_tracking_link", table_name="payments")
    op.drop_index("idx_payments_admin", table_name="payments")
    op.drop_constraint("fk_payments_tracking_link", "payments", type_="foreignkey")
    op.drop_constraint("fk_payments_admin", "payments", type_="foreignkey")
    with op.batch_alter_table("payments") as b:
        b.drop_column("tracking_link_id")
        b.drop_column("admin_id")
