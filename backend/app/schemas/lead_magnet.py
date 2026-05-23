from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class LeadMagnetOut(BaseModel):
    id: int
    name: str
    description: str | None
    file_type: str
    file_size: int | None
    product_id: int | None
    is_active: bool
    download_count: int
    has_telegram_file_id: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class LeadMagnetUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    product_id: int | None = None
    is_active: bool | None = None
