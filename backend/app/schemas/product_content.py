from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

BlockKind = Literal["text", "media", "video_note", "voice"]


class ContentBlockCreate(BaseModel):
    kind: BlockKind = "text"
    text: str | None = None
    delay_ms: int = Field(default=800, ge=0, le=10000)


class ContentBlockUpdate(BaseModel):
    text: str | None = None
    delay_ms: int | None = Field(default=None, ge=0, le=10000)
    is_active: bool | None = None
    kind: BlockKind | None = None


class ReorderIn(BaseModel):
    ordered_ids: list[int]


class ContentMediaOut(BaseModel):
    id: int
    media_type: str
    is_image: bool
    original_filename: str | None = None
    caption: str | None = None
    order_idx: int

    model_config = {"from_attributes": True}


class ContentBlockOut(BaseModel):
    id: int
    product_id: int
    order_idx: int
    kind: str
    text: str | None = None
    delay_ms: int
    is_active: bool
    media: list[ContentMediaOut] = []
    created_at: datetime

    model_config = {"from_attributes": True}
