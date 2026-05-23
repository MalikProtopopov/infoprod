"""POST /api/feature-requests — собирает feedback по фичам ('Хочу A/B', etc.)

Логи идут в structlog + audit_log. Без отдельной таблицы — это product signal,
не business data.
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_admin, get_session
from app.models.admin import Admin

logger = structlog.get_logger("feature_requests")

router = APIRouter(prefix="/feature-requests", tags=["feedback"])


class FeatureRequestIn(BaseModel):
    feature_key: str = Field(min_length=1, max_length=128)
    context: str | None = Field(default=None, max_length=1000)
    metadata: dict | None = None


@router.post("", response_model=dict, status_code=201)
async def create_feature_request(
    payload: FeatureRequestIn,
    request: Request,
    admin: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    from app.services.audit import log_action

    logger.info(
        "feature_request.received",
        admin_id=admin.id,
        feature=payload.feature_key,
        context=payload.context,
        metadata=payload.metadata,
    )

    await log_action(
        session,
        admin_id=admin.id,
        action="feature_request",
        resource_type="feature_request",
        summary=f"Запрос фичи: {payload.feature_key}",
        method="POST",
        path="/api/feature-requests",
        payload={
            "feature_key": payload.feature_key,
            "context": payload.context,
            "metadata": payload.metadata,
        },
    )
    await session.commit()

    return {"ok": True, "feature_key": payload.feature_key}
