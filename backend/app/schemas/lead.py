from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


LeadStatus = Literal["new", "contacted", "paid", "closed"]


class LeadUpdate(BaseModel):
    status: LeadStatus


class LeadOut(BaseModel):
    id: int
    status: str
    created_at: datetime
    # пользователь (read-only из telegram)
    user_id: int
    user_telegram_id: int
    user_username: str | None
    user_first_name: str | None
    user_last_name: str | None
    user_language: str | None = None
    user_phone: str | None = None
    user_email: str | None = None
    user_notes: str | None = None
    # продукт
    product_id: int
    product_code: str
    product_name: str
    product_description: str | None = None
    product_currency: str
    product_price_3m: Decimal
    product_price_6m: Decimal
    product_price_12m: Decimal
    # канал, к которому ведёт продукт
    channel_id: int
    channel_title: str

    model_config = {"from_attributes": True}
