"""analytics indexes — для timeline / funnel-conversion / pareto

Revision ID: 0070_analytics_indexes
Revises: 0060_audit_rbac
Create Date: 2026-05-23 14:30:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "0070_analytics_indexes"
down_revision: Union[str, None] = "0060_audit_rbac"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Lead timeline: GROUP BY date_trunc(day, created_at) + utm_source / tracking_link_id
    op.create_index(
        "ix_leads_created_utm",
        "leads",
        ["created_at", "utm_source"],
    )
    op.create_index(
        "ix_leads_created_link",
        "leads",
        ["created_at", "tracking_link_id"],
    )
    op.create_index(
        "ix_leads_created_product",
        "leads",
        ["created_at", "product_id"],
    )

    # Payment timeline
    op.create_index(
        "ix_payments_created_link",
        "payments",
        ["created_at", "tracking_link_id"],
    )
    op.create_index(
        "ix_payments_created_product",
        "payments",
        ["created_at", "product_id"],
    )

    # Funnel step-conversion (по ScheduledMessage)
    op.create_index(
        "ix_scheduled_step_sent",
        "scheduled_messages",
        ["funnel_step_id", "sent_at"],
    )

    # Funnel entries timeline + completion
    op.create_index(
        "ix_funnel_entries_funnel_started",
        "funnel_entries",
        ["funnel_id", "started_at"],
    )
    op.create_index(
        "ix_funnel_entries_status",
        "funnel_entries",
        ["funnel_id", "status"],
    )

    # First-touch attribution (User.first_utm_source)
    op.create_index(
        "ix_users_first_utm_source",
        "users",
        ["first_utm_source"],
        postgresql_where="first_utm_source IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_index("ix_users_first_utm_source", table_name="users")
    op.drop_index("ix_funnel_entries_status", table_name="funnel_entries")
    op.drop_index("ix_funnel_entries_funnel_started", table_name="funnel_entries")
    op.drop_index("ix_scheduled_step_sent", table_name="scheduled_messages")
    op.drop_index("ix_payments_created_product", table_name="payments")
    op.drop_index("ix_payments_created_link", table_name="payments")
    op.drop_index("ix_leads_created_product", table_name="leads")
    op.drop_index("ix_leads_created_link", table_name="leads")
    op.drop_index("ix_leads_created_utm", table_name="leads")
