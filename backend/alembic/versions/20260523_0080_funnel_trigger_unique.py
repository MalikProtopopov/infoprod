"""funnel_triggers — unique-индекс на lower(word)

Закрывает race condition при создании дубля кодового слова:
два администратора могли одновременно создать триггер с одним словом
до коммита первого, потому что валидация была только на уровне приложения
(SELECT перед INSERT). Уникальный индекс на lower(word) делает дубль
невозможным на уровне БД.

Revision ID: 0080_funnel_trigger_unique
Revises: 0070_analytics_indexes
Create Date: 2026-05-23 16:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


revision: str = "0080_funnel_trigger_unique"
down_revision: Union[str, None] = "0070_analytics_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # На случай, если в БД уже есть дубли (теоретически возможно из-за race),
    # сначала схлопываем их: оставляем самый ранний триггер с этим словом,
    # остальные удаляем. Безопасно, потому что бот всё равно не смог бы их
    # резолвить (scalar_one_or_none() падал бы на MultipleResultsFound).
    op.execute(text("""
        DELETE FROM funnel_triggers
        WHERE id IN (
            SELECT id FROM (
                SELECT id, ROW_NUMBER() OVER (
                    PARTITION BY lower(word) ORDER BY created_at, id
                ) AS rn
                FROM funnel_triggers
            ) t
            WHERE t.rn > 1
        )
    """))

    op.create_index(
        "uq_funnel_triggers_word_lower",
        "funnel_triggers",
        [text("lower(word)")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_funnel_triggers_word_lower", table_name="funnel_triggers")
