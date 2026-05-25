"""Pydantic-схемы квиза."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# ───────────── Input (write) ─────────────


class QuizOptionIn(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    score: int = 0
    order_idx: int | None = None


class QuizQuestionIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    prefix: str | None = None
    order_idx: int | None = None
    options: list[QuizOptionIn] = Field(default_factory=list)


class QuizVerdictIn(BaseModel):
    max_score: int = Field(ge=0)
    text: str = Field(min_length=1, max_length=4000)
    button_text: str | None = Field(default=None, max_length=64)
    # URL или callback_data (например 'form:start:6')
    button_action: str | None = Field(default=None, max_length=255)
    order_idx: int | None = None


class QuizCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    questions: list[QuizQuestionIn] = Field(default_factory=list)
    verdicts: list[QuizVerdictIn] = Field(default_factory=list)


class QuizUpdate(BaseModel):
    """PATCH /api/quizzes/{id} — заменяет квиз целиком, включая вложенные.

    Любое из полей опционально. Если передан список — старые записи
    удаляются и пересоздаются по новым данным (полная замена). Это
    проще для UI «отредактируй и сохрани целиком».
    """

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    questions: list[QuizQuestionIn] | None = None
    verdicts: list[QuizVerdictIn] | None = None


# ───────────── Output (read) ─────────────


class QuizOptionOut(BaseModel):
    id: int
    order_idx: int
    text: str
    score: int

    model_config = {"from_attributes": True}


class QuizQuestionOut(BaseModel):
    id: int
    order_idx: int
    text: str
    prefix: str | None = None
    options: list[QuizOptionOut] = []

    model_config = {"from_attributes": True}


class QuizVerdictOut(BaseModel):
    id: int
    order_idx: int
    max_score: int
    text: str
    button_text: str | None = None
    button_action: str | None = None

    model_config = {"from_attributes": True}


class QuizBriefOut(BaseModel):
    id: int
    name: str
    description: str | None = None
    questions_count: int = 0
    verdicts_count: int = 0
    attempts_total: int = 0
    attempts_completed: int = 0
    created_at: datetime


class QuizDetailOut(BaseModel):
    id: int
    name: str
    description: str | None = None
    questions: list[QuizQuestionOut] = []
    verdicts: list[QuizVerdictOut] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
