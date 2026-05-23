"""AuditLogService — единая точка записи событий.

Используется через decorator или вручную из endpoint'ов.
"""
from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

logger = structlog.get_logger("audit")


# Никогда не пишем эти поля в payload (защита от утечки секретов)
SECRET_KEYS = {"password", "password_hash", "old_password", "new_password",
                "token", "jwt", "authorization", "cookie", "set-cookie",
                "access_token", "api_key", "x-api-key", "secret"}


def _scrub(payload: dict | None) -> dict | None:
    if not payload or not isinstance(payload, dict):
        return payload
    out = {}
    for k, v in payload.items():
        if k.lower() in SECRET_KEYS:
            out[k] = "***REDACTED***"
        elif isinstance(v, dict):
            out[k] = _scrub(v)
        else:
            out[k] = v
    return out


async def log_action(
    session: AsyncSession,
    *,
    admin_id: int | None,
    action: str,
    resource_type: str,
    resource_id: int | None = None,
    method: str | None = None,
    path: str | None = None,
    summary: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    payload: dict | None = None,
) -> AuditLog:
    """Записывает событие в audit_log. Должно вызываться в той же session что и сама мутация."""
    entry = AuditLog(
        admin_id=admin_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        method=method,
        path=path,
        summary=summary,
        ip=ip,
        user_agent=user_agent,
        payload=_scrub(payload),
    )
    session.add(entry)
    await session.flush()
    logger.info("audit", action=action, resource=resource_type, resource_id=resource_id,
                admin_id=admin_id)
    return entry
