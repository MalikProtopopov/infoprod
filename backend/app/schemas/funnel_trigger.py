from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TriggerCreate(BaseModel):
    word: str = Field(min_length=2, max_length=64)
    funnel_id: int


class TriggerUpdate(BaseModel):
    word: str | None = Field(default=None, min_length=2, max_length=64)
    is_active: bool | None = None


class TriggerOut(BaseModel):
    id: int
    word: str
    funnel_id: int
    funnel_name: str | None = None
    is_active: bool
    use_count: int
    created_at: datetime

    model_config = {"from_attributes": True}
