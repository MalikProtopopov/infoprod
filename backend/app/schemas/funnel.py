from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class FunnelStepIn(BaseModel):
    order_idx: int = Field(ge=0)
    delay_minutes: int = Field(ge=0)
    message_text: str = Field(min_length=1, max_length=4000)
    parse_mode: str | None = "HTML"
    lead_magnet_id: int | None = None
    buttons: list[list[dict[str, Any]]] | None = None
    is_active: bool = True
    kind: str = "message"
    quiz_id: int | None = None
    form_id: int | None = None


class StepMediaBrief(BaseModel):
    """Краткая инфо о медиа шага — для отображения в студии. Полные данные
    выдаёт отдельный endpoint /funnel-steps/{id}/media."""
    id: int
    media_type: str
    mime_type: str
    file_size: int
    order_idx: int
    has_telegram_file_id: bool
    has_thumbnail: bool
    original_filename: str | None = None
    caption: str | None = None

    model_config = {"from_attributes": True}


class FunnelStepOut(BaseModel):
    id: int
    funnel_id: int
    order_idx: int
    delay_minutes: int
    message_text: str
    parse_mode: str | None
    lead_magnet_id: int | None
    buttons: list[list[dict[str, Any]]] | None
    is_active: bool
    kind: str = "message"
    quiz_id: int | None = None
    form_id: int | None = None
    media: list[StepMediaBrief] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class FunnelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    product_id: int
    bot_id: int | None = None
    ttl_days: int = Field(default=90, ge=1, le=365)
    cancel_on_payment: bool = True
    steps: list[FunnelStepIn] = []


class FunnelUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    bot_id: int | None = None
    is_active: bool | None = None
    ttl_days: int | None = Field(default=None, ge=1, le=365)
    cancel_on_payment: bool | None = None


class FunnelOut(BaseModel):
    id: int
    name: str
    description: str | None
    product_id: int
    bot_id: int | None
    is_active: bool
    ttl_days: int
    cancel_on_payment: bool
    created_at: datetime
    steps_count: int = 0
    active_entries: int = 0
    completed_entries: int = 0


class FunnelDetailOut(FunnelOut):
    steps: list[FunnelStepOut] = []


class FunnelEntryOut(BaseModel):
    id: int
    funnel_id: int
    user_id: int
    user_first_name: str | None = None
    user_username: str | None = None
    source: str
    source_ref: int | None
    started_at: datetime
    completed_at: datetime | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    status: str


class ReorderStepsIn(BaseModel):
    ordered_step_ids: list[int]
