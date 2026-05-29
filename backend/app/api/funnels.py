from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_admin, get_session
from app.models.admin import Admin
from app.models.funnel import Funnel
from app.models.funnel_entry import FunnelEntry
from app.models.funnel_step import FunnelStep
from app.models.funnel_step_media import FunnelStepMedia
from app.models.funnel_trigger import FunnelTrigger
from app.models.product import Product
from app.models.scheduled_message import ScheduledMessage
from app.models.tracking_link import TrackingLink
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


def _step_to_out(s: FunnelStep, media: list | None = None) -> FunnelStepOut:
    from app.schemas.funnel import StepMediaBrief

    media_briefs: list[StepMediaBrief] = []
    if media:
        for m in media:
            media_briefs.append(StepMediaBrief(
                id=m.id, media_type=m.media_type, mime_type=m.mime_type,
                file_size=m.file_size, order_idx=m.order_idx,
                has_telegram_file_id=bool(m.telegram_file_id),
                has_thumbnail=bool(m.thumbnail_path),
                original_filename=m.original_filename, caption=m.caption,
            ))
    return FunnelStepOut(
        id=s.id, funnel_id=s.funnel_id, order_idx=s.order_idx,
        delay_minutes=s.delay_minutes, message_text=s.message_text,
        parse_mode=s.parse_mode, lead_magnet_id=s.lead_magnet_id,
        buttons=s.buttons, is_active=s.is_active,
        kind=getattr(s, "kind", "message") or "message",
        quiz_id=s.quiz_id, form_id=s.form_id,
        audience_tags=getattr(s, "audience_tags", None),
        send_condition=getattr(s, "send_condition", "always") or "always",
        media=media_briefs,
    )


async def _load_media_by_step(session, step_ids: list[int]) -> dict[int, list]:
    """Batch-загрузка media для нескольких шагов. Возвращает dict step_id -> [media]."""
    from sqlalchemy import select

    if not step_ids:
        return {}
    rows = (
        await session.execute(
            select(FunnelStepMedia)
            .where(FunnelStepMedia.funnel_step_id.in_(step_ids))
            .order_by(FunnelStepMedia.funnel_step_id, FunnelStepMedia.order_idx)
        )
    ).scalars().all()
    out: dict[int, list] = {sid: [] for sid in step_ids}
    for m in rows:
        out.setdefault(m.funnel_step_id, []).append(m)
    return out


@router.get("", response_model=list[FunnelOut])
async def list_funnels(
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
    product_id: int | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    bot_id: int | None = Query(default=None),
) -> list[FunnelOut]:
    stmt = select(Funnel).order_by(Funnel.id.desc())
    if product_id is not None:
        stmt = stmt.where(Funnel.product_id == product_id)
    if is_active is not None:
        stmt = stmt.where(Funnel.is_active.is_(is_active))
    if bot_id is not None:
        stmt = stmt.where(Funnel.bot_id == bot_id)
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
    media_by_step = await _load_media_by_step(session, [s.id for s in steps])
    out = _to_out(f, steps_count=len(steps))
    return FunnelDetailOut(
        **out.model_dump(),
        steps=[_step_to_out(s, media_by_step.get(s.id, [])) for s in steps],
    )


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
    # Active/completed считаем одним GROUP BY — не два отдельных query.
    entry_counts = dict(
        (
            await session.execute(
                select(FunnelEntry.status, func.count(FunnelEntry.id))
                .where(FunnelEntry.funnel_id == f.id)
                .group_by(FunnelEntry.status)
            )
        ).all()
    )
    media_by_step = await _load_media_by_step(session, [s.id for s in steps])
    out = _to_out(
        f,
        steps_count=len(steps),
        active=entry_counts.get("active", 0),
        completed=entry_counts.get("completed", 0),
    )
    return FunnelDetailOut(
        **out.model_dump(),
        steps=[_step_to_out(s, media_by_step.get(s.id, [])) for s in steps],
    )


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
        is_active=payload.is_active,
        kind=payload.kind,
        quiz_id=payload.quiz_id,
        form_id=payload.form_id,
        audience_tags=payload.audience_tags,
        send_condition=payload.send_condition,
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


@router.get("/{funnel_id}/entry-points", response_model=dict)
async def get_entry_points(
    funnel_id: int,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Агрегат всех точек входа в одну воронку: trackable links, triggers, default-flag.

    Используется в Студии (§3 UI) — за 1 запрос даёт полный статус готовности.
    """
    f = await session.get(Funnel, funnel_id)
    if f is None:
        raise HTTPException(status_code=404, detail="Funnel not found")

    # 1) Trackable links с этой воронкой
    link_rows = (
        await session.execute(
            select(TrackingLink)
            .where(TrackingLink.funnel_id == funnel_id, TrackingLink.is_active.is_(True))
            .order_by(TrackingLink.id.desc())
        )
    ).scalars().all()
    links = [
        {
            "id": l.id,
            "slug": l.slug,
            "utm_source": l.utm_source,
            "utm_medium": l.utm_medium,
            "utm_campaign": l.utm_campaign,
            "click_count": l.click_count,
            "unique_users": l.unique_users,
        }
        for l in link_rows
    ]

    # 2) Кодовые слова
    trigger_rows = (
        await session.execute(
            select(FunnelTrigger)
            .where(FunnelTrigger.funnel_id == funnel_id)
            .order_by(FunnelTrigger.id.desc())
        )
    ).scalars().all()
    triggers = [
        {
            "id": t.id,
            "word": t.word,
            "is_active": t.is_active,
            "use_count": t.use_count,
        }
        for t in trigger_rows
    ]

    # 3) Является ли default-воронкой для своего продукта
    prod = await session.get(Product, f.product_id)
    is_default = bool(prod and prod.default_funnel_id == funnel_id)

    return {
        "funnel_id": funnel_id,
        "product_id": f.product_id,
        "tracking_links": links,
        "triggers": triggers,
        "is_product_default": is_default,
        "has_any": bool(links or triggers or is_default),
    }


class TestRunIn(BaseModel):
    # Кому слать тест: внутренний user_id ИЛИ telegram_user_id (хотя бы одно).
    target_user_id: int | None = None
    telegram_user_id: int | None = None


@router.post("/{funnel_id}/test-run", response_model=dict, status_code=201)
async def test_run(
    funnel_id: int,
    payload: TestRunIn | None = None,
    admin: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Тестовый прогон воронки на ВЫБРАННОГО пользователя со скоростью x60.

    Каждый шаг с delay_minutes=N отправляется через N секунд. Сообщения реально
    придут пользователю в Telegram через бота воронки (выбранный юзер должен
    был запускать этого бота). Тест-прогоны идут даже если воронка ещё не активна.
    """
    from datetime import datetime, timedelta, timezone

    payload = payload or TestRunIn()

    f = await session.get(Funnel, funnel_id)
    if f is None:
        raise HTTPException(status_code=404, detail="Funnel not found")

    # Определяем целевого пользователя: по внутреннему id, по telegram_user_id,
    # либо (без цели) — виртуальный тест-юзер от админа (прогон-симуляция).
    test_user: User | None = None
    if payload.target_user_id is not None:
        test_user = await session.get(User, payload.target_user_id)
        if test_user is None:
            raise HTTPException(status_code=404, detail="Выбранный пользователь не найден")
    elif payload.telegram_user_id is not None:
        test_user = (
            await session.execute(
                select(User).where(User.telegram_user_id == payload.telegram_user_id)
            )
        ).scalar_one_or_none()
        if test_user is None:
            # Юзер с таким TG id ещё не в базе — заводим. Доставка получится,
            # только если он уже запускал бота (иначе Telegram не даст написать).
            test_user = User(
                telegram_user_id=payload.telegram_user_id,
                notifications_enabled=True,
            )
            session.add(test_user)
            await session.flush()
    else:
        # Без явной цели — виртуальный юзер от админа (симуляция расписания).
        # Ищем по тому же отрицательному id, с которым создаём, иначе повторный
        # тест не находит юзера и падает на UNIQUE telegram_user_id.
        virtual_tg_id = -(admin.id)
        test_user = (
            await session.execute(
                select(User).where(User.telegram_user_id == virtual_tg_id).limit(1)
            )
        ).scalar_one_or_none()
        if test_user is None:
            test_user = User(
                telegram_user_id=virtual_tg_id,
                first_name=admin.username,
                username=admin.username,
                notifications_enabled=True,
            )
            session.add(test_user)
            await session.flush()

    steps = (
        await session.execute(
            select(FunnelStep)
            .where(FunnelStep.funnel_id == funnel_id, FunnelStep.is_active.is_(True))
            .order_by(FunnelStep.order_idx)
        )
    ).scalars().all()

    if not steps:
        raise HTTPException(status_code=422, detail="В воронке нет активных шагов")

    now = datetime.now(tz=timezone.utc)

    # На пару (воронка, юзер) разрешён лишь один активный entry (unique index).
    # Поэтому прошлый активный ТЕСТ-прогон этого юзера снимаем (можно тестить
    # повторно после refresh). Реальную (не тестовую) подписку не трогаем.
    existing_active = (
        await session.execute(
            select(FunnelEntry).where(
                FunnelEntry.funnel_id == funnel_id,
                FunnelEntry.user_id == test_user.id,
                FunnelEntry.status == "active",
            )
        )
    ).scalars().all()
    for e in existing_active:
        if not e.is_test:
            raise HTTPException(
                status_code=409,
                detail="У этого пользователя уже есть активная подписка на воронку — "
                       "выберите для теста другого пользователя.",
            )
        await session.execute(
            update(ScheduledMessage)
            .where(
                ScheduledMessage.funnel_entry_id == e.id,
                ScheduledMessage.sent_at.is_(None),
                ScheduledMessage.cancelled_at.is_(None),
            )
            .values(cancelled_at=now, cancel_reason="test_restarted")
        )
        e.status = "cancelled"
        e.cancelled_at = now
        e.cancel_reason = "test_restarted"
    await session.flush()

    # Создаём entry с source='manual', чтобы отличать от реальных
    entry = FunnelEntry(
        funnel_id=funnel_id,
        user_id=test_user.id,
        source="manual",
        source_ref=admin.id,
        started_at=now,
        status="active",
        is_test=True,
    )
    session.add(entry)
    await session.flush()

    # Планируем сообщения с delay/60 секунд вместо минут
    schedules = []
    for step in steps:
        delay_seconds = max(1, int(step.delay_minutes))  # min 1 сек
        sched = ScheduledMessage(
            user_id=test_user.id,
            funnel_entry_id=entry.id,
            funnel_step_id=step.id,
            scheduled_at=now + timedelta(seconds=delay_seconds),
        )
        session.add(sched)
        schedules.append({
            "step_id": step.id,
            "order_idx": step.order_idx,
            "scheduled_at": (now + timedelta(seconds=delay_seconds)).isoformat(),
            "delay_seconds": delay_seconds,
            "original_delay_minutes": step.delay_minutes,
        })

    await session.commit()

    return {
        "test_entry_id": entry.id,
        "test_user_id": test_user.id,
        "steps_scheduled": len(schedules),
        "schedules": schedules,
        "started_at": now.isoformat(),
        "speedup_factor": 60,
        "note": "Сообщения придут в Telegram если у админа настроен telegram_user_id; "
                "иначе можно опрашивать /test-run/{test_entry_id}/status для прогресса.",
    }


@router.get("/{funnel_id}/test-run/latest", response_model=dict)
async def test_run_latest(
    funnel_id: int,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Последний тест-прогон воронки — чтобы восстановить панель после refresh."""
    entry = (
        await session.execute(
            select(FunnelEntry)
            .where(FunnelEntry.funnel_id == funnel_id, FunnelEntry.is_test.is_(True))
            .order_by(FunnelEntry.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if entry is None:
        return {"test_entry_id": None}
    return {"test_entry_id": entry.id, "status": entry.status}


@router.get("/{funnel_id}/test-run/{test_entry_id}/status", response_model=dict)
async def test_run_status(
    funnel_id: int,
    test_entry_id: int,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Прогресс тестового прогона: какой шаг отправлен, какой ожидает."""
    entry = await session.get(FunnelEntry, test_entry_id)
    if entry is None or entry.funnel_id != funnel_id:
        raise HTTPException(status_code=404, detail="Test entry not found")

    msgs = (
        await session.execute(
            select(ScheduledMessage, FunnelStep)
            .join(FunnelStep, FunnelStep.id == ScheduledMessage.funnel_step_id)
            .where(ScheduledMessage.funnel_entry_id == test_entry_id)
            .order_by(FunnelStep.order_idx)
        )
    ).all()

    return {
        "entry_id": test_entry_id,
        "entry_status": entry.status,
        "messages": [
            {
                "step_order_idx": s.order_idx,
                "step_message_text": s.message_text[:100],
                "scheduled_at": m.scheduled_at.isoformat(),
                "sent_at": m.sent_at.isoformat() if m.sent_at else None,
                "cancelled_at": m.cancelled_at.isoformat() if m.cancelled_at else None,
                "error": m.error,
            }
            for m, s in msgs
        ],
    }


@router.post("/{funnel_id}/test-run/{test_entry_id}/advance", response_model=dict)
async def test_run_advance(
    funnel_id: int,
    test_entry_id: int,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Отправить СЛЕДУЮЩИЙ запланированный шаг тест-прогона прямо сейчас.

    Не нужно ждать расписания ×60 — двигаем ближайший неотправленный шаг на
    «сейчас» и сразу прогоняем воркер для этого entry."""
    from datetime import datetime, timezone

    from app.workers.scheduled_messages import process_due_messages

    entry = await session.get(FunnelEntry, test_entry_id)
    if entry is None or entry.funnel_id != funnel_id:
        raise HTTPException(status_code=404, detail="Test entry not found")

    nxt = (
        await session.execute(
            select(ScheduledMessage)
            .where(
                ScheduledMessage.funnel_entry_id == test_entry_id,
                ScheduledMessage.sent_at.is_(None),
                ScheduledMessage.cancelled_at.is_(None),
            )
            .order_by(ScheduledMessage.scheduled_at.asc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if nxt is None:
        return {"advanced": False, "done": True, "stats": {"sent": 0}}

    nxt.scheduled_at = datetime.now(tz=timezone.utc)
    await session.commit()

    stats = await process_due_messages(session, entry_id=test_entry_id)
    return {"advanced": True, "done": False, "stats": stats}


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
