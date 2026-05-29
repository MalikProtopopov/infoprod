"""Трекинг-кнопки: события воронки + теги сегментации на entry.

- funnel_events — фиксация кликов по track-кнопкам (CTR-аналитика, сигнал
  «было действие» для условий шага).
- funnel_entries.tags — теги сегментации, проставляемые track-кнопками.

Revision ID: 0170_funnel_events_tags
Revises:    0160_step_media_video_note
Create Date: 2026-05-29 11:10:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0170_funnel_events_tags"
down_revision: Union[str, None] = "0160_step_media_video_note"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "funnel_entries",
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_table(
        "funnel_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("funnel_entry_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("funnel_step_id", sa.BigInteger(), nullable=True),
        sa.Column("event_type", sa.String(length=16), nullable=False, server_default="click"),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["funnel_entry_id"], ["funnel_entries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_funnel_events_entry", "funnel_events", ["funnel_entry_id"])
    op.create_index("ix_funnel_events_type_key", "funnel_events", ["event_type", "key"])


def downgrade() -> None:
    op.drop_index("ix_funnel_events_type_key", table_name="funnel_events")
    op.drop_index("ix_funnel_events_entry", table_name="funnel_events")
    op.drop_table("funnel_events")
    op.drop_column("funnel_entries", "tags")
