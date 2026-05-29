"""Сегментация шага: audience_tags + send_condition.

- funnel_steps.audience_tags — показывать шаг только сегменту (по тегам entry).
- funnel_steps.send_condition — условие доставки ('always' | 'if_no_click_since_prev').

Revision ID: 0180_step_audience_condition
Revises:    0170_funnel_events_tags
Create Date: 2026-05-29 11:25:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0180_step_audience_condition"
down_revision: Union[str, None] = "0170_funnel_events_tags"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "funnel_steps",
        sa.Column("audience_tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "funnel_steps",
        sa.Column(
            "send_condition",
            sa.String(length=32),
            nullable=False,
            server_default="always",
        ),
    )


def downgrade() -> None:
    op.drop_column("funnel_steps", "send_condition")
    op.drop_column("funnel_steps", "audience_tags")
