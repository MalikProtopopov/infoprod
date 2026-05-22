"""tracking_links

Revision ID: 0010_tracking_links
Revises: 0001_init
Create Date: 2026-05-23 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0010_tracking_links"
down_revision: Union[str, None] = "0001_init"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tracking_links",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("slug", sa.String(64), nullable=False, unique=True),
        sa.Column("product_id", sa.BigInteger(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bot_id", sa.BigInteger(), sa.ForeignKey("bots.id", ondelete="SET NULL"), nullable=True),
        sa.Column("utm_source", sa.String(255), nullable=False),
        sa.Column("utm_medium", sa.String(255), nullable=True),
        sa.Column("utm_campaign", sa.String(255), nullable=True),
        sa.Column("utm_content", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("click_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unique_users", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("admins.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("slug ~ '^[A-Za-z0-9_-]{4,64}$'", name="slug_valid_format"),
    )
    op.create_index("idx_tracking_links_product", "tracking_links", ["product_id"])
    op.create_index("idx_tracking_links_active", "tracking_links", ["is_active", sa.text("created_at DESC")])
    op.create_index("idx_tracking_links_source", "tracking_links", ["utm_source"])


def downgrade() -> None:
    op.drop_index("idx_tracking_links_source", table_name="tracking_links")
    op.drop_index("idx_tracking_links_active", table_name="tracking_links")
    op.drop_index("idx_tracking_links_product", table_name="tracking_links")
    op.drop_table("tracking_links")
