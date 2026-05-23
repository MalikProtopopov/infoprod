from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class TrackingLinkCreate(BaseModel):
    product_id: int
    utm_source: str = Field(min_length=1, max_length=255)
    utm_medium: str | None = Field(default=None, max_length=255)
    utm_campaign: str | None = Field(default=None, max_length=255)
    utm_content: str | None = Field(default=None, max_length=255)
    bot_id: int | None = None
    funnel_id: int | None = None
    notes: str | None = None
    custom_slug: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{4,64}$")


class TrackingLinkUpdate(BaseModel):
    notes: str | None = None
    is_active: bool | None = None
    funnel_id: int | None = None


class TrackingLinkProductRef(BaseModel):
    id: int
    code: str
    name: str


class TrackingLinkBotRef(BaseModel):
    id: int
    username: str


class TrackingLinkOut(BaseModel):
    id: int
    slug: str
    url: str
    product: TrackingLinkProductRef
    bot: TrackingLinkBotRef | None
    utm_source: str
    utm_medium: str | None
    utm_campaign: str | None
    utm_content: str | None
    notes: str | None
    is_active: bool
    click_count: int
    unique_users: int
    leads_count: int
    payments_count: int
    revenue: str
    created_at: datetime
