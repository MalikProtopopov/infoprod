"""audit_log table + admins.role (RBAC)

Revision ID: 0060_audit_rbac
Revises: 0050_funnels_module
Create Date: 2026-05-23 11:30:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0060_audit_rbac"
down_revision: Union[str, None] = "0050_funnels_module"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "admins",
        sa.Column("role", sa.String(16), nullable=False, server_default="admin"),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("admin_id", sa.BigInteger,
                  sa.ForeignKey("admins.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("resource_type", sa.String(32), nullable=False),
        sa.Column("resource_id", sa.BigInteger, nullable=True),
        sa.Column("method", sa.String(16), nullable=True),
        sa.Column("path", sa.Text, nullable=True),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("payload", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_audit_admin", "audit_log", ["admin_id", "created_at"])
    op.create_index("idx_audit_resource", "audit_log",
                    ["resource_type", "resource_id", "created_at"])
    op.create_index("idx_audit_action_created",
                    "audit_log", ["action", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_audit_action_created", table_name="audit_log")
    op.drop_index("idx_audit_resource", table_name="audit_log")
    op.drop_index("idx_audit_admin", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_column("admins", "role")
