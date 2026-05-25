"""Quiz / QuizQuestion / QuizOption / QuizVerdict — самостоятельная сущность.

Один квиз можно прикрепить к нескольким шагам в разных воронках через
FK funnel_steps.quiz_id. Хранит вопросы (ordered), их опции (text + score)
и набор вердиктов (по диапазону score).

Жизненный цикл прохождения — в user_step_states (mode='quiz'):
    user_step_states.funnel_step_id → funnel_steps.quiz_id → quizzes.id
"""
from __future__ import annotations

from datetime import datetime
from typing import List

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Quiz(Base):
    __tablename__ = "quizzes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    questions: Mapped[List["QuizQuestion"]] = relationship(
        back_populates="quiz",
        cascade="all, delete-orphan",
        order_by="QuizQuestion.order_idx",
    )
    verdicts: Mapped[List["QuizVerdict"]] = relationship(
        back_populates="quiz",
        cascade="all, delete-orphan",
        order_by="QuizVerdict.order_idx",
    )


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"
    __table_args__ = (
        Index("ix_quiz_questions_quiz_order", "quiz_id", "order_idx"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    quiz_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False
    )
    order_idx: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # короткая строка-префикс над вопросом, например «вопрос 2/5»
    prefix: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    quiz: Mapped["Quiz"] = relationship(back_populates="questions")
    options: Mapped[List["QuizOption"]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="QuizOption.order_idx",
    )


class QuizOption(Base):
    __tablename__ = "quiz_options"
    __table_args__ = (
        Index("ix_quiz_options_question_order", "question_id", "order_idx"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    question_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("quiz_questions.id", ondelete="CASCADE"), nullable=False
    )
    order_idx: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # вклад в общий score юзера при выборе этой опции
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    question: Mapped["QuizQuestion"] = relationship(back_populates="options")


class QuizVerdict(Base):
    __tablename__ = "quiz_verdicts"
    __table_args__ = (
        Index("ix_quiz_verdicts_quiz_order", "quiz_id", "order_idx"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    quiz_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False
    )
    order_idx: Mapped[int] = mapped_column(Integer, nullable=False)
    # Включительно: вердикт срабатывает если итоговый score юзера <= max_score
    max_score: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # Кнопка под вердиктом — опциональная.
    button_text: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Либо URL ('https://…'/'tg://…'), либо callback_data ('form:start:N' и т.п.).
    # Различаем по наличию '://': если есть — это URL, иначе — callback_data.
    button_action: Mapped[str | None] = mapped_column(String(255), nullable=True)

    quiz: Mapped["Quiz"] = relationship(back_populates="verdicts")
