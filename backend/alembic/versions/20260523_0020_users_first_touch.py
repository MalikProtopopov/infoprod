"""users first-touch attribution

Revision ID: 0020_users_first_touch
Revises: 0010_tracking_links
Create Date: 2026-05-23 00:01:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0020_users_first_touch"
down_revision: Union[str, None] = "0010_tracking_links"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as b:
        b.add_column(sa.Column("first_product_id", sa.BigInteger(), nullable=True))
        b.add_column(sa.Column("first_tracking_link_id", sa.BigInteger(), nullable=True))
        b.add_column(sa.Column("first_utm_source", sa.String(255), nullable=True))
        b.add_column(sa.Column("first_utm_medium", sa.String(255), nullable=True))
        b.add_column(sa.Column("first_utm_campaign", sa.String(255), nullable=True))
        b.add_column(sa.Column("first_bot_id", sa.BigInteger(), nullable=True))
        b.add_column(sa.Column("current_tracking_link_id", sa.BigInteger(), nullable=True))
        b.add_column(sa.Column("current_link_set_at", sa.DateTime(timezone=True), nullable=True))

    op.create_foreign_key(
        "fk_users_first_product", "users", "products",
        ["first_product_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_users_first_tracking_link", "users", "tracking_links",
        ["first_tracking_link_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_users_first_bot", "users", "bots",
        ["first_bot_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_users_current_tracking_link", "users", "tracking_links",
        ["current_tracking_link_id"], ["id"], ondelete="SET NULL",
    )

    op.create_index(
        "idx_users_first_source", "users", ["first_utm_source"],
        postgresql_where=sa.text("first_utm_source IS NOT NULL"),
    )
    op.create_index(
        "idx_users_first_product", "users", ["first_product_id"],
        postgresql_where=sa.text("first_product_id IS NOT NULL"),
    )
    op.create_index(
        "idx_users_first_seen", "users", [sa.text("first_seen_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_users_first_seen", table_name="users")
    op.drop_index("idx_users_first_product", table_name="users")
    op.drop_index("idx_users_first_source", table_name="users")
    op.drop_constraint("fk_users_current_tracking_link", "users", type_="foreignkey")
    op.drop_constraint("fk_users_first_bot", "users", type_="foreignkey")
    op.drop_constraint("fk_users_first_tracking_link", "users", type_="foreignkey")
    op.drop_constraint("fk_users_first_product", "users", type_="foreignkey")
    with op.batch_alter_table("users") as b:
        b.drop_column("current_link_set_at")
        b.drop_column("current_tracking_link_id")
        b.drop_column("first_bot_id")
        b.drop_column("first_utm_campaign")
        b.drop_column("first_utm_medium")
        b.drop_column("first_utm_source")
        b.drop_column("first_tracking_link_id")
        b.drop_column("first_product_id")
