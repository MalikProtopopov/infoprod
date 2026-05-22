from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ChannelCreate(BaseModel):
    bot_id: int
    telegram_chat_id: int = Field(description="ID канала (как int, например -1001234...)")
    title: str | None = None
    username: str | None = None


class ChannelUpdate(BaseModel):
    title: str | None = None
    username: str | None = None


class ChannelOut(BaseModel):
    id: int
    telegram_chat_id: int
    title: str
    username: str | None
    bot_id: int
    created_at: datetime
    bot_username: str | None = None
    products_count: int = 0
    active_subs_count: int = 0

    model_config = {"from_attributes": True}
