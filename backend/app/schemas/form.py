"""Pydantic-схемы формы."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ───────────── Input ─────────────


class FormFieldIn(BaseModel):
    key: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    question: str = Field(min_length=1, max_length=2000)
    prefix: str | None = None
    field_type: str = Field(default="text")  # text|phone|email|url|number
    required: bool = True
    max_length: int = Field(default=500, ge=1, le=4000)
    order_idx: int | None = None


class FormCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    product_id: int | None = None
    success_message: str | None = None
    cancel_message: str | None = None
    completion_buttons: list[list[dict[str, Any]]] | None = None
    fields: list[FormFieldIn] = Field(default_factory=list)


class FormUpdate(BaseModel):
    """Полная замена с возможностью пропустить поля (PATCH-семантика)."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    product_id: int | None = None
    success_message: str | None = None
    cancel_message: str | None = None
    completion_buttons: list[list[dict[str, Any]]] | None = None
    fields: list[FormFieldIn] | None = None


# ───────────── Output ─────────────


class FormFieldOut(BaseModel):
    id: int
    order_idx: int
    key: str
    question: str
    prefix: str | None = None
    field_type: str
    required: bool
    max_length: int

    model_config = {"from_attributes": True}


class FormBriefOut(BaseModel):
    id: int
    name: str
    description: str | None = None
    product_id: int | None = None
    fields_count: int = 0
    submissions_total: int = 0
    submissions_completed: int = 0
    leads_created: int = 0
    created_at: datetime


class FormDetailOut(BaseModel):
    id: int
    name: str
    description: str | None = None
    product_id: int | None = None
    success_message: str | None = None
    cancel_message: str | None = None
    completion_buttons: list[list[dict[str, Any]]] | None = None
    fields: list[FormFieldOut] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
