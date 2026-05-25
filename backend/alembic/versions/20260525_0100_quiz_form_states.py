"""quiz/form-режимы воронки + extra_data в leads + user_step_states.

Добавляет лёгкий механизм интерактивных шагов воронки:
  * funnel_steps.quiz_data JSONB — конфиг квиза (вопросы/опции/вердикты)
  * funnel_steps.form_data JSONB — конфиг формы (поля + success-сообщение)
  * funnel_steps.kind        VARCHAR(16) — 'message' | 'quiz' | 'form'
                              для явного маркера типа шага (default 'message')
  * leads.extra_data         JSONB — ответы формы (FIO, контакт, проект)
  * leads.form_step_id       BIGINT FK funnel_steps SET NULL — какой
                              form-шаг создал лида (для трассировки)
  * leads.product_id         делаем nullable — форма может собирать лид
                              без привязки к продукту
  * user_step_states         таблица состояния квиза/формы для юзера

State-machine квиза/формы хранится в user_step_states. Юзер не может
одновременно проходить два разных квиза или две формы (partial unique).

Revision ID: 0100_quiz_form_states
Revises:    0090_funnel_step_media
Create Date: 2026-05-25 12:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0100_quiz_form_states"
down_revision: Union[str, None] = "0090_funnel_step_media"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- funnel_steps: + kind, quiz_data, form_data ---
    op.add_column(
        "funnel_steps",
        sa.Column(
            "kind",
            sa.String(length=16),
            nullable=False,
            server_default="message",
        ),
    )
    op.add_column(
        "funnel_steps",
        sa.Column("quiz_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "funnel_steps",
        sa.Column("form_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_check_constraint(
        "ck_funnel_steps_kind",
        "funnel_steps",
        "kind IN ('message','quiz','form')",
    )

    # --- leads: product_id nullable + extra_data + form_step_id ---
    op.alter_column("leads", "product_id", existing_type=sa.BigInteger(), nullable=True)
    op.add_column(
        "leads",
        sa.Column("extra_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "leads",
        sa.Column("form_step_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_leads_form_step_id",
        "leads",
        "funnel_steps",
        ["form_step_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_leads_form_step_id", "leads", ["form_step_id"])

    # --- user_step_states: состояние прохождения квиза/формы ---
    op.create_table(
        "user_step_states",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "funnel_step_id",
            sa.BigInteger(),
            sa.ForeignKey("funnel_steps.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "funnel_entry_id",
            sa.BigInteger(),
            sa.ForeignKey("funnel_entries.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="in_progress",
        ),
        sa.Column("current_idx", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column(
            "answers",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("mode IN ('quiz','form')", name="ck_uss_mode"),
        sa.CheckConstraint(
            "status IN ('in_progress','completed','cancelled')",
            name="ck_uss_status",
        ),
        sa.CheckConstraint("current_idx >= 0", name="ck_uss_current_idx_nonneg"),
    )
    op.create_index(
        "ix_user_step_states_user_status",
        "user_step_states",
        ["user_id", "status"],
    )
    op.create_index(
        "ix_user_step_states_step",
        "user_step_states",
        ["funnel_step_id"],
    )
    # Только одно активное состояние конкретного режима для юзера.
    # (без этого юзер мог бы случайно запустить два квиза/формы одновременно).
    op.create_index(
        "uq_user_step_states_user_mode_active",
        "user_step_states",
        ["user_id", "mode"],
        unique=True,
        postgresql_where=sa.text("status = 'in_progress'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_user_step_states_user_mode_active",
        table_name="user_step_states",
    )
    op.drop_index("ix_user_step_states_step", table_name="user_step_states")
    op.drop_index("ix_user_step_states_user_status", table_name="user_step_states")
    op.drop_table("user_step_states")

    op.drop_index("ix_leads_form_step_id", table_name="leads")
    op.drop_constraint("fk_leads_form_step_id", "leads", type_="foreignkey")
    op.drop_column("leads", "form_step_id")
    op.drop_column("leads", "extra_data")
    op.alter_column("leads", "product_id", existing_type=sa.BigInteger(), nullable=False)

    op.drop_constraint("ck_funnel_steps_kind", "funnel_steps", type_="check")
    op.drop_column("funnel_steps", "form_data")
    op.drop_column("funnel_steps", "quiz_data")
    op.drop_column("funnel_steps", "kind")
