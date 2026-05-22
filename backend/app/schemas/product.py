from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_\-]+$")
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    cover_url: str | None = None
    channel_id: int
    price_3m: Decimal = Field(ge=0)
    price_6m: Decimal = Field(ge=0)
    price_12m: Decimal = Field(ge=0)
    currency: str | None = None
    is_active: bool = True


class ProductUpdate(BaseModel):
    code: str | None = Field(default=None, max_length=64, pattern=r"^[A-Za-z0-9_\-]+$")
    name: str | None = None
    description: str | None = None
    cover_url: str | None = None
    channel_id: int | None = None
    price_3m: Decimal | None = None
    price_6m: Decimal | None = None
    price_12m: Decimal | None = None
    currency: str | None = None
    is_active: bool | None = None


class ProductOut(BaseModel):
    id: int
    code: str
    name: str
    description: str | None
    cover_url: str | None
    channel_id: int
    channel_title: str | None = None
    price_3m: Decimal
    price_6m: Decimal
    price_12m: Decimal
    currency: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
