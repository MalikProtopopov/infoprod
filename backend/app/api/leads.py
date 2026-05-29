from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_admin, get_session
from app.models.admin import Admin
from app.models.channel import Channel
from app.models.lead import Lead
from app.models.payment import Payment
from app.models.product import Product
from app.models.user import User
from app.schemas.lead import PAYMENT_REQUIRED_STATUSES, LeadOut, LeadUpdate

router = APIRouter(prefix="/leads", tags=["leads"])

# Частые причины отмены — для дропдауна в UI. Своя причина вводится текстом.
CANCEL_REASON_PRESETS = [
    "Дорого",
    "Передумал / не актуально",
    "Нет денег сейчас",
    "Купил у конкурента",
    "Не выходит на связь",
    "Ошибочная / тестовая заявка",
    "Не подошли условия",
]


def _to_out(
    lead: Lead, user: User, product: Product, channel: Channel | None, payment: Payment | None = None
) -> LeadOut:
    return LeadOut(
        id=lead.id,
        status=lead.status,
        created_at=lead.created_at,
        user_id=user.id,
        user_telegram_id=user.telegram_user_id,
        user_username=user.username,
        user_first_name=user.first_name,
        user_last_name=user.last_name,
        user_language=user.language_code,
        user_phone=user.phone,
        user_email=user.email,
        user_notes=user.notes,
        product_id=product.id,
        product_code=product.code,
        product_name=product.name,
        product_description=product.description,
        product_currency=product.currency,
        product_price_3m=product.price_3m,
        product_price_6m=product.price_6m,
        product_price_12m=product.price_12m,
        channel_id=channel.id if channel else None,
        channel_title=channel.title if channel else None,
        payment_id=lead.payment_id,
        payment_amount=payment.amount if payment else None,
        payment_currency=payment.currency if payment else None,
        cancel_reason=lead.cancel_reason,
        cancelled_at=lead.cancelled_at,
    )


@router.get("", response_model=dict)
async def list_leads(
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
    status: str | None = Query(default=None, description="new|contacted|paid|closed|all"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict:
    stmt = (
        select(Lead, User, Product, Channel, Payment)
        .join(User, User.id == Lead.user_id)
        .join(Product, Product.id == Lead.product_id)
        .outerjoin(Channel, Channel.id == Product.channel_id)
        .outerjoin(Payment, Payment.id == Lead.payment_id)
        .order_by(Lead.id.desc())
    )
    count_stmt = select(func.count()).select_from(Lead)
    if status and status != "all":
        stmt = stmt.where(Lead.status == status)
        count_stmt = count_stmt.where(Lead.status == status)
    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(stmt.limit(limit).offset(offset))).all()
    return {
        "total": total,
        "items": [_to_out(l, u, p, c, pay).model_dump(mode="json") for l, u, p, c, pay in rows],
    }


@router.get("/cancel-reasons")
async def cancel_reasons_summary(
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Частота причин отмены (для дашборда) + список пресетов для UI."""
    rows = (
        await session.execute(
            select(Lead.cancel_reason, func.count())
            .where(Lead.status == "cancelled", Lead.cancel_reason.is_not(None))
            .group_by(Lead.cancel_reason)
            .order_by(func.count().desc())
        )
    ).all()
    return {
        "presets": CANCEL_REASON_PRESETS,
        "breakdown": [{"reason": r, "count": c} for r, c in rows],
        "total": sum(c for _, c in rows),
    }


@router.get("/{lead_id}", response_model=LeadOut)
async def get_lead(
    lead_id: int,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> LeadOut:
    row = (
        await session.execute(
            select(Lead, User, Product, Channel, Payment)
            .join(User, User.id == Lead.user_id)
            .join(Product, Product.id == Lead.product_id)
            .outerjoin(Channel, Channel.id == Product.channel_id)
            .outerjoin(Payment, Payment.id == Lead.payment_id)
            .where(Lead.id == lead_id)
        )
    ).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    l, u, p, c, pay = row
    return _to_out(l, u, p, c, pay)


@router.patch("/{lead_id}", response_model=LeadOut)
async def update_lead(
    lead_id: int,
    payload: LeadUpdate,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> LeadOut:
    lead = (await session.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    from datetime import datetime, timezone
    now = datetime.now(tz=timezone.utc)

    # paid/closed подразумевают сделку → обязателен привязанный платёж.
    if payload.status in PAYMENT_REQUIRED_STATUSES:
        target_payment_id = payload.payment_id or lead.payment_id
        if target_payment_id is None:
            raise HTTPException(
                status_code=422,
                detail="Статус требует платёж. Привяжите существующий платёж или создайте новый.",
            )
        payment = (
            await session.execute(select(Payment).where(Payment.id == target_payment_id))
        ).scalar_one_or_none()
        if payment is None:
            raise HTTPException(status_code=422, detail="Платёж не найден")
        if payment.user_id != lead.user_id:
            raise HTTPException(
                status_code=422, detail="Платёж принадлежит другому пользователю"
            )
        if lead.product_id is not None and payment.product_id != lead.product_id:
            raise HTTPException(
                status_code=422, detail="Платёж за другой продукт"
            )
        lead.payment_id = payment.id

    # cancelled → обязательна причина отмены.
    if payload.status == "cancelled":
        reason = (payload.cancel_reason or "").strip()
        if not reason:
            raise HTTPException(status_code=422, detail="Укажите причину отмены")
        lead.cancel_reason = reason
    else:
        # Выходим из «отменена» → старая причина больше не актуальна.
        lead.cancel_reason = None
        lead.cancelled_at = None

    # Таймстампы смены статуса — только при первом переходе.
    field_map = {
        "contacted": "contacted_at",
        "paid": "paid_at",
        "closed": "closed_at",
        "cancelled": "cancelled_at",
    }
    ts_field = field_map.get(payload.status)
    if ts_field and getattr(lead, ts_field) is None:
        setattr(lead, ts_field, now)

    lead.status = payload.status
    await session.commit()
    await session.refresh(lead)

    user = (await session.execute(select(User).where(User.id == lead.user_id))).scalar_one()
    product = (await session.execute(select(Product).where(Product.id == lead.product_id))).scalar_one()
    channel = None
    if product.channel_id is not None:
        channel = (
            await session.execute(select(Channel).where(Channel.id == product.channel_id))
        ).scalar_one_or_none()
    payment = None
    if lead.payment_id is not None:
        payment = (
            await session.execute(select(Payment).where(Payment.id == lead.payment_id))
        ).scalar_one_or_none()
    return _to_out(lead, user, product, channel, payment)


@router.delete("/{lead_id}", status_code=204, response_class=Response)
async def delete_lead(
    lead_id: int,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> Response:
    lead = (await session.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    await session.delete(lead)
    await session.commit()
    return Response(status_code=204)
