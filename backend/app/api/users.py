from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_admin, get_session, require_role
from app.models.admin import Admin
from app.models.channel import Channel
from app.models.lead import Lead
from app.models.payment import Payment
from app.models.product import Product
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.user import UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=dict)
async def list_users(
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
    q: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    stmt = select(User)
    if q:
        # Уберём ведущий @, лишние пробелы — пользователи часто копируют "@username"
        q_clean = q.strip().lstrip("@").strip()
        if q_clean:
            like = f"%{q_clean.lower()}%"
            conditions = [
                func.lower(func.coalesce(User.username, "")).like(like),
                func.lower(func.coalesce(User.first_name, "")).like(like),
                func.lower(func.coalesce(User.last_name, "")).like(like),
            ]
            # Если запрос состоит только из цифр — также ищем по telegram_user_id
            if q_clean.lstrip("-").isdigit():
                try:
                    conditions.append(User.telegram_user_id == int(q_clean))
                except ValueError:
                    pass
            stmt = stmt.where(or_(*conditions))
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        await session.execute(stmt.order_by(User.id.desc()).limit(limit).offset(offset))
    ).scalars().all()
    return {
        "total": total,
        "items": [UserOut.model_validate(u, from_attributes=True) for u in rows],
    }


@router.get("/{user_id}")
async def get_user(
    user_id: int,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    leads_rows = (
        await session.execute(
            select(Lead, Product.name, Channel.title)
            .join(Product, Product.id == Lead.product_id)
            .join(Channel, Channel.id == Product.channel_id)
            .where(Lead.user_id == user.id)
            .order_by(Lead.id.desc())
        )
    ).all()

    payments_rows = (
        await session.execute(
            select(Payment, Product.name, Channel.title)
            .join(Product, Product.id == Payment.product_id)
            .join(Channel, Channel.id == Product.channel_id)
            .where(Payment.user_id == user.id)
            .order_by(Payment.id.desc())
        )
    ).all()

    subs_rows = (
        await session.execute(
            select(Subscription, Channel.title, Product.name)
            .join(Channel, Channel.id == Subscription.channel_id)
            .outerjoin(Product, Product.id == Subscription.product_id)
            .where(Subscription.user_id == user.id)
            .order_by(Subscription.id.desc())
        )
    ).all()

    return {
        "user": UserOut.model_validate(user, from_attributes=True).model_dump(mode="json"),
        "leads": [
            {
                "id": l.id,
                "product_id": l.product_id,
                "product_name": pn,
                "channel_title": ct,
                "status": l.status,
                "created_at": l.created_at,
            }
            for l, pn, ct in leads_rows
        ],
        "payments": [
            {
                "id": p.id,
                "product_id": p.product_id,
                "product_name": pn,
                "channel_title": ct,
                "period_months": p.period_months,
                "amount": str(p.amount),
                "currency": p.currency,
                "comment": p.comment,
                "created_at": p.created_at,
            }
            for p, pn, ct in payments_rows
        ],
        "subscriptions": [
            {
                "id": s.id,
                "channel_id": s.channel_id,
                "channel_title": ct,
                "product_id": s.product_id,
                "product_name": pn,
                "starts_at": s.starts_at,
                "ends_at": s.ends_at,
                "status": s.status,
                "invite_link": s.invite_link,
            }
            for s, ct, pn in subs_rows
        ],
    }


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(user, k, v)
    await session.commit()
    await session.refresh(user)
    return UserOut.model_validate(user, from_attributes=True)


# ───────── История ответов юзера (quiz/form submissions) ─────────


@router.get("/{user_id}/submissions")
async def user_submissions(
    user_id: int,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
    status: str | None = Query(default=None, description="in_progress|completed|cancelled|all"),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    """Хронология квизов/форм юзера.

    Каждый элемент содержит снапшот ответов на момент прохождения
    (даже если квиз/форма потом отредактировали), название
    квиза/формы из текущей версии, и контекст воронки.
    """
    from sqlalchemy import select, and_
    from app.models.user_step_state import UserStepState
    from app.models.funnel_step import FunnelStep
    from app.models.funnel import Funnel
    from app.models.funnel_entry import FunnelEntry
    from app.models.quiz import Quiz
    from app.models.form import Form
    from app.models.lead import Lead

    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    conditions = [UserStepState.user_id == user_id]
    if status and status != "all":
        conditions.append(UserStepState.status == status)

    rows = (
        await session.execute(
            select(
                UserStepState,
                FunnelStep,
                Quiz,
                Form,
                Funnel,
                FunnelEntry,
            )
            .join(FunnelStep, FunnelStep.id == UserStepState.funnel_step_id)
            .outerjoin(Quiz, Quiz.id == FunnelStep.quiz_id)
            .outerjoin(Form, Form.id == FunnelStep.form_id)
            .outerjoin(Funnel, Funnel.id == FunnelStep.funnel_id)
            .outerjoin(FunnelEntry, FunnelEntry.id == UserStepState.funnel_entry_id)
            .where(and_(*conditions))
            .order_by(UserStepState.started_at.desc())
            .limit(limit)
        )
    ).all()

    # Lead'ы, созданные form-submission'ами — по form_step_id + user_id
    lead_rows = (
        await session.execute(
            select(Lead.id, Lead.form_step_id, Lead.created_at)
            .where(Lead.user_id == user_id, Lead.form_step_id.isnot(None))
        )
    ).all()
    leads_by_step: dict[int, list[dict]] = {}
    for lid, fsid, lcreated in lead_rows:
        leads_by_step.setdefault(fsid, []).append({"id": lid, "created_at": lcreated})

    items: list[dict] = []
    for state, step, quiz, form, funnel, entry in rows:
        item = {
            "id": state.id,
            "mode": state.mode,
            "status": state.status,
            "started_at": state.started_at,
            "completed_at": state.completed_at,
            "score": state.score,
            "current_idx": state.current_idx,
            "answers": state.answers,
            "funnel": (
                {"id": funnel.id, "name": funnel.name} if funnel is not None else None
            ),
            "funnel_entry_id": entry.id if entry is not None else None,
            "step_id": step.id if step is not None else None,
        }
        if state.mode == "quiz" and quiz is not None:
            item["quiz"] = {"id": quiz.id, "name": quiz.name}
        if state.mode == "form" and form is not None:
            item["form"] = {"id": form.id, "name": form.name}
            # привязываем созданный Lead если есть
            lead_list = leads_by_step.get(step.id if step else None, [])
            # ближайший по времени Lead (после started_at)
            relevant = [
                l for l in lead_list if l["created_at"] >= state.started_at
            ]
            if relevant:
                relevant.sort(key=lambda x: x["created_at"])
                item["lead_id"] = relevant[0]["id"]
        items.append(item)

    return {"total": len(items), "items": items}


# ───────── GDPR endpoints ─────────


@router.get("/{user_id}/export")
async def gdpr_export(
    user_id: int,
    admin: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """GDPR-export: возвращает все данные пользователя в JSON."""
    from app.services.audit import log_action

    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    leads = (
        await session.execute(select(Lead).where(Lead.user_id == user_id))
    ).scalars().all()
    payments = (
        await session.execute(select(Payment).where(Payment.user_id == user_id))
    ).scalars().all()
    subs = (
        await session.execute(select(Subscription).where(Subscription.user_id == user_id))
    ).scalars().all()

    await log_action(
        session, admin_id=admin.id, action="gdpr_export",
        resource_type="user", resource_id=user_id,
        summary=f"GDPR export для user_id={user_id}",
    )
    await session.commit()

    def _serialize_row(obj):
        out = {}
        for c in obj.__table__.columns:
            v = getattr(obj, c.name)
            if hasattr(v, "isoformat"):
                v = v.isoformat()
            out[c.name] = v
        return out

    return {
        "user": _serialize_row(user),
        "leads": [_serialize_row(l) for l in leads],
        "payments": [_serialize_row(p) for p in payments],
        "subscriptions": [_serialize_row(s) for s in subs],
    }


@router.delete("/{user_id}/forget", status_code=204, response_class=Response)
async def gdpr_forget(
    user_id: int,
    admin: Admin = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """GDPR right-to-be-forgotten: анонимизация (без удаления PII-зависимых записей).

    Заменяет personal-поля на null и хеш telegram_user_id. Лиды/платежи остаются для финансовой
    аналитики, но без связи с реальной личностью.
    """
    from app.services.audit import log_action

    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Удаляем PII
    user.username = None
    user.first_name = "[redacted]"
    user.last_name = None
    user.phone = None
    user.email = None
    user.notes = None
    user.notifications_enabled = False
    # telegram_user_id не трогаем — это unique-key. Заменяем на отрицательное (виртуальное).
    if user.telegram_user_id > 0:
        user.telegram_user_id = -user.telegram_user_id

    await log_action(
        session, admin_id=admin.id, action="gdpr_forget",
        resource_type="user", resource_id=user_id,
        summary=f"GDPR forget для user_id={user_id}",
    )
    await session.commit()
    return Response(status_code=204)
