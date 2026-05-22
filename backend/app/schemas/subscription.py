from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SubscriptionExtend(BaseModel):
    days: int | None = Field(default=None, ge=1, le=3650)
    months: int | None = Field(default=None, ge=1, le=120)


class SubscriptionOut(BaseModel):
    id: int
    user_id: int
    user_username: str | None = None
    user_first_name: str | None = None
    channel_id: int
    channel_title: str | None = None
    product_id: int | None
    product_name: str | None = None
    payment_id: int | None
    starts_at: datetime
    ends_at: datetime
    status: str
    invite_link: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
