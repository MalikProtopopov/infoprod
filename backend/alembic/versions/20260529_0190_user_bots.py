"""user_bots — связь пользователь↔бот (мультибот).

Таблица пар (user, bot): какие боты были у пользователя, last_seen,
блокировка per-bot. Бэкофилл из users.first_bot_id (что знаем сейчас).

Revision ID: 0190_user_bots
Revises:    0180_step_audience_condition
Create Date: 2026-05-29 13:10:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0190_user_bots"
down_revision: Union[str, None] = "0180_step_audience_condition"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_bots",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("bot_id", sa.BigInteger(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("blocked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["bot_id"], ["bots.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "bot_id", name="uq_user_bot"),
    )
    op.create_index("ix_user_bots_bot", "user_bots", ["bot_id"])
    op.create_index("ix_user_bots_user", "user_bots", ["user_id"])

    # Бэкофилл: то, что знаем — first_bot_id первого касания.
    op.execute(
        """
        INSERT INTO user_bots (user_id, bot_id, first_seen_at, last_seen_at)
        SELECT id, first_bot_id, first_seen_at, last_seen_at
        FROM users
        WHERE first_bot_id IS NOT NULL
        ON CONFLICT (user_id, bot_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("ix_user_bots_user", table_name="user_bots")
    op.drop_index("ix_user_bots_bot", table_name="user_bots")
    op.drop_table("user_bots")
