from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_admin, get_session
from app.models.admin import Admin
from app.models.funnel import Funnel
from app.models.funnel_entry import FunnelEntry
from app.models.funnel_step import FunnelStep
from app.models.product import Product
from app.models.user import User
from app.schemas.funnel import (
    FunnelCreate,
    FunnelDetailOut,
    FunnelEntryOut,
    FunnelOut,
    FunnelStepIn,
    FunnelStepOut,
    FunnelUpdate,
    ReorderStepsIn,
)
from app.services.funnels import FunnelsService

router = APIRouter(prefix="/funnels", tags=["funnels"])


def _to_out(f: Funnel, steps_count: int = 0, active: int = 0, completed: int = 0) -> FunnelOut:
    return FunnelOut(
        id=f.id, name=f.name, description=f.description,
        product_id=f.product_id, bot_id=f.bot_id,
        is_active=f.is_active, ttl_days=f.ttl_days,
        cancel_on_payment=f.cancel_on_payment,
        created_at=f.created_at,
        steps_count=steps_count,
        active_entries=active,
        completed_entries=completed,
    )


def _step_to_out(s: FunnelStep) -> FunnelStepOut:
    return FunnelStepOut(
        id=s.id, funnel_id=s.funnel_id, order_idx=s.order_idx,
        delay_minutes=s.delay_minutes, message_text=s.message_text,
        parse_mode=s.parse_mode, lead_magnet_id=s.lead_magnet_id,
        buttons=s.buttons, is_active=s.is_active,
    )


@router.get("", response_model=list[FunnelOut])
async def list_funnels(
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
    product_id: int | None = Query(default=None),
    is_active: bool | None = Query(default=None),
) -> list[FunnelOut]:
    stmt = select(Funnel).order_by(Funnel.id.desc())
    if product_id is not None:
        stmt = stmt.where(Funnel.product_id == product_id)
    if is_active is not None:
        stmt = stmt.where(Funnel.is_active.is_(is_active))
    rows = (await session.execute(stmt)).scalars().all()
    if not rows:
        return []
    ids = [r.id for r in rows]
    # batch-метрики
    steps_rows = (
        await session.execute(
            select(FunnelStep.funnel_id, func.count(FunnelStep.id))
            .where(FunnelStep.funnel_id.in_(ids))
            .group_by(FunnelStep.funnel_id)
        )
    ).all()
    steps_map = {r[0]: r[1] for r in steps_rows}
    entry_rows = (
        await session.execute(
            select(FunnelEntry.funnel_id, FunnelEntry.status, func.count(FunnelEntry.id))
            .where(FunnelEntry.funnel_id.in_(ids))
            .group_by(FunnelEntry.funnel_id, FunnelEntry.status)
        )
    ).all()
    active_map: dict[int, int] = {}
    completed_map: dict[int, int] = {}
    for fid, st, cnt in entry_rows:
        if st == "active":
            active_map[fid] = cnt
        elif st == "completed":
            completed_map[fid] = cnt
    return [
        _to_out(
            f,
            steps_count=steps_map.get(f.id, 0),
            active=active_map.get(f.id, 0),
            completed=completed_map.get(f.id, 0),
        )
        for f in rows
    ]


@router.post("", response_model=FunnelDetailOut, status_code=201)
async def create_funnel(
    payload: FunnelCreate,
    admin: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> FunnelDetailOut:
    # Проверка продукта
    prod = await session.get(Product, payload.product_id)
    if prod is None:
        raise HTTPException(status_code=400, detail="Продукт не найден")

    svc = FunnelsService(session)
    steps_data = [s.model_dump() for s in payload.steps]
    f = await svc.create(
        name=payload.name,
        product_id=payload.product_id,
        description=payload.description,
        bot_id=payload.bot_id,
        ttl_days=payload.ttl_days,
        cancel_on_payment=payload.cancel_on_payment,
        created_by=admin.id,
        steps=steps_data,
    )
    await session.commit()
    await session.refresh(f)

    steps = (
        await session.execute(
            select(FunnelStep).where(FunnelStep.funnel_id == f.id).order_by(FunnelStep.order_idx)
        )
    ).scalars().all()
    out = _to_out(f, steps_count=len(steps))
    return FunnelDetailOut(**out.model_dump(), steps=[_step_to_out(s) for s in steps])


@router.get("/{funnel_id}", response_model=FunnelDetailOut)
async def get_funnel(
    funnel_id: int,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> FunnelDetailOut:
    f = await session.get(Funnel, funnel_id)
    if f is None:
        raise HTTPException(status_code=404, detail="Funnel not found")
    steps = (
        await session.execute(
            select(FunnelStep).where(FunnelStep.funnel_id == f.id).order_by(FunnelStep.order_idx)
        )
    ).scalars().all()
    active_cnt = (
        await session.execute(
            select(func.count()).select_from(FunnelEntry).where(
                FunnelEntry.funnel_id == f.id, FunnelEntry.status == "active"
            )
        )
    ).scalar_one()
    completed_cnt = (
        await session.execute(
            select(func.count()).select_from(FunnelEntry).where(
                FunnelEntry.funnel_id == f.id, FunnelEntry.status == "completed"
            )
        )
    ).scalar_one()
    out = _to_out(f, steps_count=len(steps), active=active_cnt, completed=completed_cnt)
    return FunnelDetailOut(**out.model_dump(), steps=[_step_to_out(s) for s in steps])


@router.patch("/{funnel_id}", response_model=FunnelOut)
async def update_funnel(
    funnel_id: int,
    payload: FunnelUpdate,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> FunnelOut:
    svc = FunnelsService(session)
    f = await svc.update(funnel_id, **payload.model_dump(exclude_unset=True))
    if f is None:
        raise HTTPException(status_code=404, detail="Funnel not found")
    await session.commit()
    await session.refresh(f)
    return _to_out(f)


@router.delete("/{funnel_id}", status_code=204, response_class=Response)
async def delete_funnel(
    funnel_id: int,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> Response:
    f = await session.get(Funnel, funnel_id)
    if f is None:
        raise HTTPException(status_code=404, detail="Funnel not found")
    active = (
        await session.execute(
            select(func.count()).select_from(FunnelEntry).where(
                FunnelEntry.funnel_id == funnel_id, FunnelEntry.status == "active"
            )
        )
    ).scalar_one()
    if active > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Воронка имеет {active} активных подписок. Сначала остановите их.",
        )
    await session.delete(f)
    await session.commit()
    return Response(status_code=204)


@router.post("/{funnel_id}/steps", response_model=FunnelStepOut, status_code=201)
async def add_step(
    funnel_id: int,
    payload: FunnelStepIn,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> FunnelStepOut:
    f = await session.get(Funnel, funnel_id)
    if f is None:
        raise HTTPException(status_code=404, detail="Funnel not found")
    svc = FunnelsService(session)
    step = await svc.add_step(
        funnel_id, order_idx=payload.order_idx,
        delay_minutes=payload.delay_minutes,
        message_text=payload.message_text,
        lead_magnet_id=payload.lead_magnet_id,
        buttons=payload.buttons,
        parse_mode=payload.parse_mode or "HTML",
    )
    await session.commit()
    await session.refresh(step)
    return _step_to_out(step)


@router.post("/{funnel_id}/reorder", status_code=204, response_class=Response)
async def reorder_steps(
    funnel_id: int,
    payload: ReorderStepsIn,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> Response:
    f = await session.get(Funnel, funnel_id)
    if f is None:
        raise HTTPException(status_code=404, detail="Funnel not found")
    svc = FunnelsService(session)
    await svc.reorder_steps(funnel_id, payload.ordered_step_ids)
    await session.commit()
    return Response(status_code=204)


@router.get("/{funnel_id}/entries", response_model=list[FunnelEntryOut])
async def list_entries(
    funnel_id: int,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[FunnelEntryOut]:
    stmt = (
        select(FunnelEntry, User.first_name, User.username)
        .join(User, User.id == FunnelEntry.user_id)
        .where(FunnelEntry.funnel_id == funnel_id)
        .order_by(FunnelEntry.id.desc())
        .limit(limit)
    )
    if status:
        stmt = stmt.where(FunnelEntry.status == status)
    rows = (await session.execute(stmt)).all()
    return [
        FunnelEntryOut(
            id=e.id, funnel_id=e.funnel_id, user_id=e.user_id,
            user_first_name=fn, user_username=un,
            source=e.source, source_ref=e.source_ref,
            started_at=e.started_at, completed_at=e.completed_at,
            cancelled_at=e.cancelled_at, cancel_reason=e.cancel_reason,
            status=e.status,
        )
        for e, fn, un in rows
    ]


# ===== entries endpoints (отдельный router без funnel_id) =====
entries_router = APIRouter(prefix="/funnel-entries", tags=["funnels"])


@entries_router.post("/{entry_id}/cancel", status_code=204, response_class=Response)
async def cancel_entry(
    entry_id: int,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> Response:
    svc = FunnelsService(session)
    ok = await svc.cancel_entry(entry_id, reason="manual")
    if not ok:
        raise HTTPException(status_code=404, detail="Entry not found or not active")
    await session.commit()
    return Response(status_code=204)


# ===== funnel_steps endpoints =====
steps_router = APIRouter(prefix="/funnel-steps", tags=["funnels"])


@steps_router.patch("/{step_id}", response_model=FunnelStepOut)
async def update_step(
    step_id: int,
    payload: FunnelStepIn,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> FunnelStepOut:
    step = await session.get(FunnelStep, step_id)
    if step is None:
        raise HTTPException(status_code=404, detail="Step not found")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        if v is not None:
            setattr(step, k, v)
    await session.commit()
    await session.refresh(step)
    return _step_to_out(step)


@steps_router.delete("/{step_id}", status_code=204, response_class=Response)
async def delete_step(
    step_id: int,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> Response:
    step = await session.get(FunnelStep, step_id)
    if step is None:
        raise HTTPException(status_code=404, detail="Step not found")
    await session.delete(step)
    await session.commit()
    return Response(status_code=204)
