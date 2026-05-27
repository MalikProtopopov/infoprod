from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


LeadStatus = Literal["new", "contacted", "paid", "closed", "cancelled"]

# Статусы, подразумевающие сделку → требуют привязанный платёж.
PAYMENT_REQUIRED_STATUSES = {"paid", "closed"}


class LeadUpdate(BaseModel):
    status: LeadStatus
    # для paid/closed — привязать существующий платёж (если не передан, но платёж
    # уже привязан ранее, используется он; иначе API вернёт 422)
    payment_id: int | None = None
    # для cancelled — причина отмены (пресет или произвольный текст)
    cancel_reason: str | None = Field(default=None, max_length=500)


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
    # --- сделка / отмена ---
    payment_id: int | None = None
    payment_amount: Decimal | None = None
    payment_currency: str | None = None
    cancel_reason: str | None = None
    cancelled_at: datetime | None = None

    model_config = {"from_attributes": True}
