"""Видео-кружок (video_note) в медиа шагов воронки.

Расширяем CHECK-ограничение funnel_step_media.media_type значением
'video_note' — кружок CEO/менеджера прямо в шаге воронки (как в блоках продукта).

Revision ID: 0160_step_media_video_note
Revises:    0150_product_channel_optional
Create Date: 2026-05-29 10:50:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0160_step_media_video_note"
down_revision: Union[str, None] = "0150_product_channel_optional"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD = "media_type IN ('photo','video','animation','audio','document','voice')"
_NEW = "media_type IN ('photo','video','animation','audio','document','voice','video_note')"


def upgrade() -> None:
    op.drop_constraint("ck_funnel_step_media_type", "funnel_step_media", type_="check")
    op.create_check_constraint("ck_funnel_step_media_type", "funnel_step_media", _NEW)


def downgrade() -> None:
    # Кружки нужно сначала убрать/переконвертировать, иначе откат CHECK упадёт.
    op.drop_constraint("ck_funnel_step_media_type", "funnel_step_media", type_="check")
    op.create_check_constraint("ck_funnel_step_media_type", "funnel_step_media", _OLD)
