"""GET /api/audit-log — просмотр аудит-журнала."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_admin, get_session, require_role
from app.models.admin import Admin
from app.models.audit_log import AuditLog

router = APIRouter(prefix="/audit-log", tags=["audit"])


@router.get("", response_model=dict)
async def list_audit_log(
    _: Admin = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
    admin_id: int | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    action: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict:
    stmt = select(AuditLog).order_by(AuditLog.id.desc())
    if admin_id is not None:
        stmt = stmt.where(AuditLog.admin_id == admin_id)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    rows = (await session.execute(stmt.limit(limit).offset(offset))).scalars().all()
    return {
        "total": len(rows),
        "items": [
            {
                "id": r.id,
                "admin_id": r.admin_id,
                "action": r.action,
                "resource_type": r.resource_type,
                "resource_id": r.resource_id,
                "method": r.method,
                "path": r.path,
                "summary": r.summary,
                "ip": r.ip,
                "user_agent": r.user_agent,
                "payload": r.payload,
                "created_at": r.created_at.isoformat() if isinstance(r.created_at, datetime) else r.created_at,
            }
            for r in rows
        ],
    }
