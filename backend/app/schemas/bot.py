from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class BotCreate(BaseModel):
    token: str = Field(min_length=20, max_length=255)


class BotUpdate(BaseModel):
    is_active: bool | None = None


class BotOut(BaseModel):
    id: int
    telegram_bot_id: int
    username: str
    title: str | None
    is_active: bool
    created_at: datetime
    # token не отдаём целиком, только маску
    token_mask: str
    channels_count: int = 0
    products_count: int = 0

    model_config = {"from_attributes": True}
