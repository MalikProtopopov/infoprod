from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = Field(default="postgresql+asyncpg://postgres:postgres@db:5432/postgres")
    jwt_secret: str = Field(default="dev-secret-change-me")
    jwt_ttl_min: int = Field(default=60 * 24 * 7)

    admin_username: str = Field(default="admin")
    admin_password: str = Field(default="")  # обязателен в проде, проверяется при старте

    default_currency: str = Field(default="RUB")
    cors_origins: str = Field(default="")
    public_base_url: str = Field(default="")
    cookie_secure: bool = Field(default=True)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False)

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
