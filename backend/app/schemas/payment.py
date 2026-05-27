from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


PeriodMonths = Literal[3, 6, 12]


class PaymentCreate(BaseModel):
    user_id: int
    product_id: int
    period_months: PeriodMonths
    amount: Decimal | None = Field(default=None, description="Если не указан — берётся цена продукта за период")
    comment: str | None = None


class PaymentUpdate(BaseModel):
    comment: str | None = None


class ReceiptOut(BaseModel):
    id: int
    mime_type: str
    is_image: bool
    original_filename: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PaymentOut(BaseModel):
    id: int
    user_id: int
    user_username: str | None = None
    user_first_name: str | None = None
    product_id: int
    product_name: str | None = None
    period_months: int
    amount: Decimal
    currency: str
    comment: str | None
    created_at: datetime
    receipts: list[ReceiptOut] = []

    model_config = {"from_attributes": True}
