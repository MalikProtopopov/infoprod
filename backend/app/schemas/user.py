from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserUpdate(BaseModel):
    phone: str | None = Field(default=None, max_length=64)
    email: EmailStr | None = None
    notes: str | None = None


class UserOut(BaseModel):
    id: int
    telegram_user_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    language_code: str | None
    phone: str | None
    email: str | None
    notes: str | None
    first_seen_at: datetime
    last_seen_at: datetime

    model_config = {"from_attributes": True}
