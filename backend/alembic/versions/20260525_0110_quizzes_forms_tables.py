"""quizzes/forms как отдельные сущности + перенос JSONB-данных в таблицы.

Архитектурный сдвиг: квиз и форма больше не хранятся как JSONB прямо на
шаге воронки — теперь это самостоятельные модели в админке. Шаг воронки
ссылается на них через FK (quiz_id / form_id).

Что миграция делает в одном transaction:
1. Создаёт таблицы quizzes / quiz_questions / quiz_options / quiz_verdicts
2. Создаёт таблицы forms / form_fields
3. Добавляет funnel_steps.quiz_id и funnel_steps.form_id (FK)
4. Раскладывает существующие funnel_steps.quiz_data JSONB → quizzes + nested,
   проставляет funnel_steps.quiz_id
5. То же для form_data → forms + nested, проставляет funnel_steps.form_id
6. Дропает funnel_steps.quiz_data / .form_data колонки

Backward-compat: user_step_states продолжают ссылаться на funnel_step_id —
ничего не теряем. Их `answers` уже хранят снапшоты текстов вопросов/ответов,
так что прошлые попытки читаются даже если квиз потом отредактируют.

Revision ID: 0110_quizzes_forms_tables
Revises:    0100_quiz_form_states
Create Date: 2026-05-25 14:00:00.000000
"""
from __future__ import annotations

import json
from typing import Any, Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0110_quizzes_forms_tables"
down_revision: Union[str, None] = "0100_quiz_form_states"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================
    # 1) Таблицы квиза
    # =========================================================
    op.create_table(
        "quizzes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "quiz_questions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "quiz_id",
            sa.BigInteger(),
            sa.ForeignKey("quizzes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("order_idx", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("prefix", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_quiz_questions_quiz_order", "quiz_questions", ["quiz_id", "order_idx"])

    op.create_table(
        "quiz_options",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "question_id",
            sa.BigInteger(),
            sa.ForeignKey("quiz_questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("order_idx", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_quiz_options_question_order", "quiz_options", ["question_id", "order_idx"])

    op.create_table(
        "quiz_verdicts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "quiz_id",
            sa.BigInteger(),
            sa.ForeignKey("quizzes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("order_idx", sa.Integer(), nullable=False),
        sa.Column(
            "max_score",
            sa.Integer(),
            nullable=False,
            comment="Включительно: вердикт срабатывает если score юзера <= max_score",
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("button_text", sa.String(length=64), nullable=True),
        sa.Column(
            "button_action",
            sa.String(length=255),
            nullable=True,
            comment="Либо URL, либо callback_data; различаются по наличию '://'",
        ),
    )
    op.create_index("ix_quiz_verdicts_quiz_order", "quiz_verdicts", ["quiz_id", "order_idx"])

    # =========================================================
    # 2) Таблицы формы
    # =========================================================
    op.create_table(
        "forms",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "product_id",
            sa.BigInteger(),
            sa.ForeignKey("products.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("success_message", sa.Text(), nullable=True),
        sa.Column("cancel_message", sa.Text(), nullable=True),
        sa.Column(
            "completion_buttons",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="двумерный массив кнопок после success-сообщения",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_forms_product_id", "forms", ["product_id"])

    op.create_table(
        "form_fields",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "form_id",
            sa.BigInteger(),
            sa.ForeignKey("forms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("order_idx", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("prefix", sa.Text(), nullable=True),
        sa.Column(
            "field_type",
            sa.String(length=16),
            nullable=False,
            server_default="text",
        ),
        sa.Column("required", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("max_length", sa.Integer(), nullable=False, server_default="500"),
        sa.CheckConstraint(
            "field_type IN ('text','phone','email','url','number')",
            name="ck_form_fields_field_type",
        ),
    )
    op.create_index("ix_form_fields_form_order", "form_fields", ["form_id", "order_idx"])
    op.create_index("ix_form_fields_form_key", "form_fields", ["form_id", "key"], unique=True)

    # =========================================================
    # 3) FK на funnel_steps
    # =========================================================
    op.add_column(
        "funnel_steps",
        sa.Column("quiz_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "funnel_steps",
        sa.Column("form_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_funnel_steps_quiz_id",
        "funnel_steps",
        "quizzes",
        ["quiz_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_funnel_steps_form_id",
        "funnel_steps",
        "forms",
        ["form_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_funnel_steps_quiz_id", "funnel_steps", ["quiz_id"])
    op.create_index("ix_funnel_steps_form_id", "funnel_steps", ["form_id"])

    # =========================================================
    # 4) Перенос данных JSONB → реляционные таблицы
    # =========================================================
    conn = op.get_bind()
    _migrate_quizzes(conn)
    _migrate_forms(conn)

    # =========================================================
    # 5) Дропаем JSONB-колонки
    # =========================================================
    op.drop_column("funnel_steps", "quiz_data")
    op.drop_column("funnel_steps", "form_data")


def downgrade() -> None:
    # Восстанавливаем JSONB-колонки (пустые — старые данные не возвращаем).
    op.add_column(
        "funnel_steps",
        sa.Column("quiz_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "funnel_steps",
        sa.Column("form_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    op.drop_index("ix_funnel_steps_form_id", table_name="funnel_steps")
    op.drop_index("ix_funnel_steps_quiz_id", table_name="funnel_steps")
    op.drop_constraint("fk_funnel_steps_form_id", "funnel_steps", type_="foreignkey")
    op.drop_constraint("fk_funnel_steps_quiz_id", "funnel_steps", type_="foreignkey")
    op.drop_column("funnel_steps", "form_id")
    op.drop_column("funnel_steps", "quiz_id")

    op.drop_index("ix_form_fields_form_key", table_name="form_fields")
    op.drop_index("ix_form_fields_form_order", table_name="form_fields")
    op.drop_table("form_fields")
    op.drop_index("ix_forms_product_id", table_name="forms")
    op.drop_table("forms")

    op.drop_index("ix_quiz_verdicts_quiz_order", table_name="quiz_verdicts")
    op.drop_table("quiz_verdicts")
    op.drop_index("ix_quiz_options_question_order", table_name="quiz_options")
    op.drop_table("quiz_options")
    op.drop_index("ix_quiz_questions_quiz_order", table_name="quiz_questions")
    op.drop_table("quiz_questions")
    op.drop_table("quizzes")


# ───────────────────────── data migration helpers ─────────────────────────


def _migrate_quizzes(conn) -> None:
    """Для каждого funnel_step с quiz_data JSONB создаёт Quiz + nested,
    проставляет funnel_steps.quiz_id."""
    rows = conn.execute(
        sa.text(
            """
            SELECT fs.id AS step_id, fs.funnel_id, fs.quiz_data, f.name AS funnel_name
            FROM funnel_steps fs
            LEFT JOIN funnels f ON f.id = fs.funnel_id
            WHERE fs.quiz_data IS NOT NULL
            ORDER BY fs.id
            """
        )
    ).mappings().all()

    for row in rows:
        qd = _ensure_dict(row["quiz_data"])
        if not qd:
            continue

        quiz_name = f"Квиз · {row['funnel_name'] or 'без названия'} (step {row['step_id']})"

        # 1) Quiz
        quiz_id = conn.execute(
            sa.text(
                "INSERT INTO quizzes (name, description) VALUES (:name, :desc) RETURNING id"
            ),
            {"name": quiz_name[:255], "desc": "Перенесено из quiz_data JSONB"},
        ).scalar()

        # 2) Questions + Options
        for q_idx, q in enumerate(qd.get("questions") or []):
            qq_id = conn.execute(
                sa.text(
                    """
                    INSERT INTO quiz_questions (quiz_id, order_idx, text, prefix)
                    VALUES (:qid, :oi, :text, :prefix)
                    RETURNING id
                    """
                ),
                {
                    "qid": quiz_id,
                    "oi": q_idx,
                    "text": q.get("text") or "",
                    "prefix": q.get("prefix"),
                },
            ).scalar()

            for o_idx, opt in enumerate(q.get("options") or []):
                conn.execute(
                    sa.text(
                        """
                        INSERT INTO quiz_options (question_id, order_idx, text, score)
                        VALUES (:qid, :oi, :text, :score)
                        """
                    ),
                    {
                        "qid": qq_id,
                        "oi": o_idx,
                        "text": opt.get("text") or "",
                        "score": int(opt.get("score") or 0),
                    },
                )

        # 3) Verdicts
        for v_idx, v in enumerate(qd.get("verdicts") or []):
            btn = v.get("button") or v.get("buttons")
            btn_text = btn_action = None
            if isinstance(btn, dict):
                btn_text = btn.get("text")
                btn_action = btn.get("callback_data") or btn.get("url")
            conn.execute(
                sa.text(
                    """
                    INSERT INTO quiz_verdicts
                        (quiz_id, order_idx, max_score, text, button_text, button_action)
                    VALUES (:qid, :oi, :ms, :t, :bt, :ba)
                    """
                ),
                {
                    "qid": quiz_id,
                    "oi": v_idx,
                    "ms": int(v.get("max_score", 1_000_000)),
                    "t": v.get("text") or "",
                    "bt": btn_text,
                    "ba": btn_action,
                },
            )

        # 4) FK на funnel_step
        conn.execute(
            sa.text("UPDATE funnel_steps SET quiz_id = :qid WHERE id = :sid"),
            {"qid": quiz_id, "sid": row["step_id"]},
        )


def _migrate_forms(conn) -> None:
    """Для каждого funnel_step с form_data JSONB создаёт Form + nested,
    проставляет funnel_steps.form_id."""
    rows = conn.execute(
        sa.text(
            """
            SELECT fs.id AS step_id, fs.funnel_id, fs.form_data, f.name AS funnel_name
            FROM funnel_steps fs
            LEFT JOIN funnels f ON f.id = fs.funnel_id
            WHERE fs.form_data IS NOT NULL
            ORDER BY fs.id
            """
        )
    ).mappings().all()

    for row in rows:
        fd = _ensure_dict(row["form_data"])
        if not fd:
            continue

        form_name = f"Форма · {row['funnel_name'] or 'без названия'} (step {row['step_id']})"
        completion_buttons = fd.get("completion_buttons")
        # JSONB-колонка ждёт сериализованный JSON
        completion_buttons_json = (
            json.dumps(completion_buttons) if completion_buttons is not None else None
        )

        form_id = conn.execute(
            sa.text(
                """
                INSERT INTO forms
                    (name, description, product_id, success_message,
                     cancel_message, completion_buttons)
                VALUES (:name, :desc, :pid, :sm, :cm, CAST(:cb AS JSONB))
                RETURNING id
                """
            ),
            {
                "name": form_name[:255],
                "desc": "Перенесено из form_data JSONB",
                "pid": fd.get("product_id"),
                "sm": fd.get("success_message"),
                "cm": fd.get("cancel_message"),
                "cb": completion_buttons_json,
            },
        ).scalar()

        for f_idx, fld in enumerate(fd.get("fields") or []):
            field_type = fld.get("type") or "text"
            if field_type not in {"text", "phone", "email", "url", "number"}:
                field_type = "text"
            conn.execute(
                sa.text(
                    """
                    INSERT INTO form_fields
                        (form_id, order_idx, key, question, prefix,
                         field_type, required, max_length)
                    VALUES (:fid, :oi, :key, :q, :prefix, :ft, :req, :ml)
                    """
                ),
                {
                    "fid": form_id,
                    "oi": f_idx,
                    "key": (fld.get("key") or f"field_{f_idx}")[:64],
                    "q": fld.get("question") or fld.get("label") or "",
                    "prefix": fld.get("prefix"),
                    "ft": field_type,
                    "req": bool(fld.get("required", True)),
                    "ml": int(fld.get("max_length") or 500),
                },
            )

        conn.execute(
            sa.text("UPDATE funnel_steps SET form_id = :fid WHERE id = :sid"),
            {"fid": form_id, "sid": row["step_id"]},
        )


def _ensure_dict(value: Any) -> dict | None:
    """asyncpg/psycopg могут вернуть JSONB либо dict, либо str — нормализуем."""
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return None
    return None
