"""UserStepState — state-machine для quiz/form шагов воронки.

Один шаг типа `quiz` или `form` запускается у юзера кнопкой
(`quiz:start:{step_id}` или `form:start:{step_id}`). Бот создаёт запись
UserStepState и отправляет первый вопрос/поле; на каждом ответе
current_idx инкрементируется, answers пополняется, в конце
status='completed' и (для form) создаётся Lead с extra_data.

Партершиал-индекс по (user_id, mode) WHERE status='in_progress'
гарантирует, что у юзера не может быть одновременно двух активных
квизов / двух активных форм — повторный `quiz:start` просто покажет
текущий вопрос (идемпотентно).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserStepState(Base):
    __tablename__ = "user_step_states"
    __table_args__ = (
        CheckConstraint("mode IN ('quiz','form')", name="ck_uss_mode"),
        CheckConstraint(
            "status IN ('in_progress','completed','cancelled')",
            name="ck_uss_status",
        ),
        CheckConstraint("current_idx >= 0", name="ck_uss_current_idx_nonneg"),
        Index("ix_user_step_states_user_status", "user_id", "status"),
        Index("ix_user_step_states_step", "funnel_step_id"),
        Index(
            "uq_user_step_states_user_mode_active",
            "user_id",
            "mode",
            unique=True,
            postgresql_where=text("status = 'in_progress'"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    funnel_step_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("funnel_steps.id", ondelete="CASCADE"), nullable=False
    )
    funnel_entry_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("funnel_entries.id", ondelete="SET NULL"), nullable=True
    )
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="in_progress", server_default="in_progress"
    )
    current_idx: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    answers: Mapped[Any] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
