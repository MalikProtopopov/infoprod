"""GET /api/config/features — эффективный набор фичефлагов для фронта.

Под аутентификацией (не светим состав фич публично). И бэкенд (роутеры/scheduler/
бот), и админка читают один и тот же отрезолвленный набор отсюда, чтобы не было
рассинхрона между слоями.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import current_admin
from app.core.features import FEATURE_REGISTRY, current_features
from app.models.admin import Admin

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/features")
async def get_features(_: Admin = Depends(current_admin)) -> dict:
    return {
        "features": current_features(),
        "registry": [
            {"key": d.key, "label": d.label, "depends_on": list(d.depends_on)}
            for d in FEATURE_REGISTRY.values()
        ],
    }
