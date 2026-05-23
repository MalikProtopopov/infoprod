from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_admin, get_session
from app.models.admin import Admin
from app.models.funnel import Funnel
from app.models.funnel_trigger import FunnelTrigger
from app.schemas.funnel_trigger import TriggerCreate, TriggerOut, TriggerUpdate
from app.services.funnel_triggers import (
    FunnelTriggersService,
    InvalidTriggerWordError,
    TriggerConflictError,
)

router = APIRouter(prefix="/funnel-triggers", tags=["funnel-triggers"])


def _to_out(t: FunnelTrigger, funnel_name: str | None = None) -> TriggerOut:
    return TriggerOut(
        id=t.id, word=t.word, funnel_id=t.funnel_id, funnel_name=funnel_name,
        is_active=t.is_active, use_count=t.use_count, created_at=t.created_at,
    )


@router.get("", response_model=list[TriggerOut])
async def list_triggers(
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> list[TriggerOut]:
    rows = (
        await session.execute(
            select(FunnelTrigger, Funnel.name)
            .join(Funnel, Funnel.id == FunnelTrigger.funnel_id)
            .order_by(FunnelTrigger.id.desc())
        )
    ).all()
    return [_to_out(t, name) for t, name in rows]


@router.post("", response_model=TriggerOut, status_code=201)
async def create_trigger(
    payload: TriggerCreate,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> TriggerOut:
    f = await session.get(Funnel, payload.funnel_id)
    if f is None:
        raise HTTPException(status_code=400, detail="Funnel not found")
    svc = FunnelTriggersService(session)
    try:
        t = await svc.create(word=payload.word, funnel_id=payload.funnel_id)
    except TriggerConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except InvalidTriggerWordError as e:
        raise HTTPException(status_code=422, detail=str(e))
    await session.commit()
    await session.refresh(t)
    return _to_out(t, funnel_name=f.name)


@router.patch("/{trigger_id}", response_model=TriggerOut)
async def update_trigger(
    trigger_id: int,
    payload: TriggerUpdate,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> TriggerOut:
    svc = FunnelTriggersService(session)
    try:
        t = await svc.update(trigger_id, word=payload.word, is_active=payload.is_active)
    except TriggerConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except InvalidTriggerWordError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if t is None:
        raise HTTPException(status_code=404, detail="Trigger not found")
    await session.commit()
    await session.refresh(t)
    return _to_out(t)


@router.delete("/{trigger_id}", status_code=204, response_class=Response)
async def delete_trigger(
    trigger_id: int,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> Response:
    svc = FunnelTriggersService(session)
    ok = await svc.delete(trigger_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Trigger not found")
    await session.commit()
    return Response(status_code=204)
