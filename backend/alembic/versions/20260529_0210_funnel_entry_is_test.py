"""funnel_entries.is_test — флаг тестового прогона воронки.

Тест-прогоны идут даже на неактивной воронке (для проверки до запуска) и
исключаются из аналитики.

Revision ID: 0210_funnel_entry_is_test
Revises:    0200_messages
Create Date: 2026-05-29 15:40:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0210_funnel_entry_is_test"
down_revision: Union[str, None] = "0200_messages"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "funnel_entries",
        sa.Column("is_test", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("funnel_entries", "is_test")
