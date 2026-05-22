"""leads attribution + status timestamps

Revision ID: 0030_leads_attribution
Revises: 0020_users_first_touch
Create Date: 2026-05-23 00:02:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0030_leads_attribution"
down_revision: Union[str, None] = "0020_users_first_touch"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("leads") as b:
        b.add_column(sa.Column("tracking_link_id", sa.BigInteger(), nullable=True))
        b.add_column(sa.Column("utm_source", sa.String(255), nullable=True))
        b.add_column(sa.Column("utm_medium", sa.String(255), nullable=True))
        b.add_column(sa.Column("utm_campaign", sa.String(255), nullable=True))
        b.add_column(sa.Column("contacted_at", sa.DateTime(timezone=True), nullable=True))
        b.add_column(sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True))
        b.add_column(sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))

    op.create_foreign_key(
        "fk_leads_tracking_link", "leads", "tracking_links",
        ["tracking_link_id"], ["id"], ondelete="SET NULL",
    )

    op.create_index(
        "idx_leads_tracking_link", "leads", ["tracking_link_id"],
        postgresql_where=sa.text("tracking_link_id IS NOT NULL"),
    )
    op.create_index(
        "idx_leads_status_created", "leads", ["status", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_leads_source", "leads", ["utm_source"],
        postgresql_where=sa.text("utm_source IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_leads_source", table_name="leads")
    op.drop_index("idx_leads_status_created", table_name="leads")
    op.drop_index("idx_leads_tracking_link", table_name="leads")
    op.drop_constraint("fk_leads_tracking_link", "leads", type_="foreignkey")
    with op.batch_alter_table("leads") as b:
        b.drop_column("closed_at")
        b.drop_column("paid_at")
        b.drop_column("contacted_at")
        b.drop_column("utm_campaign")
        b.drop_column("utm_medium")
        b.drop_column("utm_source")
        b.drop_column("tracking_link_id")
