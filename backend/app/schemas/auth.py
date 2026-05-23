from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=255)


class LoginResponse(BaseModel):
    ok: bool = True
    username: str


class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6, max_length=255)


class AdminInfo(BaseModel):
    id: int
    username: str
    role: str = "admin"
