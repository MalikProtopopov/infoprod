"""messages — лог переписки пользователь↔бот (чат в админке).

Revision ID: 0200_messages
Revises:    0190_user_bots
Create Date: 2026-05-29 13:30:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0200_messages"
down_revision: Union[str, None] = "0190_user_bots"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "messages",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("bot_id", sa.BigInteger(), nullable=False),
        sa.Column("direction", sa.String(length=3), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("tg_message_id", sa.BigInteger(), nullable=True),
        sa.Column("sent_by_admin_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["bot_id"], ["bots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sent_by_admin_id"], ["admins.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_messages_user_bot_time", "messages", ["user_id", "bot_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_messages_user_bot_time", table_name="messages")
    op.drop_table("messages")
