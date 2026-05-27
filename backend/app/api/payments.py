from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_admin, get_session
from app.bot import manager as bot_manager
from app.models.admin import Admin
from app.models.channel import Channel
from app.models.payment import Payment
from app.models.product import Product
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.payment import PaymentCreate, PaymentOut, PaymentUpdate
from app.services import subscriptions as sub_service

router = APIRouter(prefix="/payments", tags=["payments"])


def _to_out(p: Payment, user: User | None = None, product_name: str | None = None) -> PaymentOut:
    return PaymentOut(
        id=p.id,
        user_id=p.user_id,
        user_username=getattr(user, "username", None) if user else None,
        user_first_name=getattr(user, "first_name", None) if user else None,
        product_id=p.product_id,
        product_name=product_name,
        period_months=p.period_months,
        amount=p.amount,
        currency=p.currency,
        comment=p.comment,
        created_at=p.created_at,
    )


def _price_for_period(product: Product, period_months: int) -> Decimal:
    return {3: product.price_3m, 6: product.price_6m, 12: product.price_12m}[period_months]


@router.get("", response_model=list[PaymentOut])
async def list_payments(
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
    user_id: int | None = Query(default=None),
    product_id: int | None = Query(default=None),
) -> list[PaymentOut]:
    stmt = (
        select(Payment, User, Product.name)
        .join(User, User.id == Payment.user_id)
        .join(Product, Product.id == Payment.product_id)
        .order_by(Payment.id.desc())
    )
    if user_id is not None:
        stmt = stmt.where(Payment.user_id == user_id)
    if product_id is not None:
        stmt = stmt.where(Payment.product_id == product_id)
    rows = (await session.execute(stmt)).all()
    return [_to_out(p, u, pn) for p, u, pn in rows]


@router.post("", response_model=PaymentOut, status_code=201)
async def create_payment(
    payload: PaymentCreate,
    admin: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> PaymentOut:
    user = (
        await session.execute(select(User).where(User.id == payload.user_id))
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="Пользователь не найден")
    product = (
        await session.execute(select(Product).where(Product.id == payload.product_id))
    ).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=400, detail="Продукт не найден")

    channel = (
        await session.execute(select(Channel).where(Channel.id == product.channel_id))
    ).scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=400, detail="Канал продукта не найден")
    if bot_manager.get_aiogram_bot(channel.bot_id) is None:
        raise HTTPException(
            status_code=409,
            detail="Бот канала неактивен или не запущен — невозможно выдать доступ. Активируйте бота в разделе «Боты».",
        )

    if payload.amount is not None and payload.amount < 0:
        raise HTTPException(status_code=422, detail="Сумма не может быть отрицательной")
    amount = payload.amount if payload.amount is not None else _price_for_period(product, payload.period_months)

    # Last-touch атрибуция платежа: наследуется от самой свежей заявки этой пары user+product
    # (если таковая есть и в ней проставлен tracking_link_id)
    from app.models.lead import Lead
    last_lead_tl = (
        await session.execute(
            select(Lead.tracking_link_id)
            .where(
                Lead.user_id == user.id,
                Lead.product_id == product.id,
                Lead.tracking_link_id.is_not(None),
            )
            .order_by(Lead.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    payment = Payment(
        user_id=user.id,
        product_id=product.id,
        period_months=payload.period_months,
        amount=amount,
        currency=product.currency,
        comment=payload.comment,
        admin_id=admin.id,
        tracking_link_id=last_lead_tl,
    )
    session.add(payment)
    await session.flush()  # получить id

    await sub_service.grant_for_payment(session, payment)

    # Автоматически отмечаем последнюю заявку этого user+product как paid
    from datetime import datetime, timezone
    last_lead = (
        await session.execute(
            select(Lead)
            .where(
                Lead.user_id == user.id,
                Lead.product_id == product.id,
                Lead.status.in_(["new", "contacted"]),
            )
            .order_by(Lead.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if last_lead is not None:
        last_lead.status = "paid"
        if last_lead.paid_at is None:
            last_lead.paid_at = datetime.now(tz=timezone.utc)
        # Привязываем платёж к заявке (обратная связь для целостности).
        last_lead.payment_id = payment.id

    # NEW: автоотмена активных воронок на этот продукт
    from app.services.funnels import FunnelsService
    funnels_svc = FunnelsService(session)
    await funnels_svc.cancel_entries_for_user_on_payment(
        user_id=user.id, product_id=product.id,
    )

    # Audit
    from app.services.audit import log_action
    await log_action(
        session, admin_id=admin.id, action="create",
        resource_type="payment", resource_id=payment.id,
        summary=f"Payment {payment.amount} {payment.currency} за {payment.period_months} мес. для user_id={payment.user_id}",
        payload={"product_id": payment.product_id, "amount": str(payment.amount), "period_months": payment.period_months},
    )

    await session.commit()
    await session.refresh(payment)

    return _to_out(payment, user, product.name)


@router.patch("/{payment_id}", response_model=PaymentOut)
async def update_payment(
    payment_id: int,
    payload: PaymentUpdate,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> PaymentOut:
    p = (await session.execute(select(Payment).where(Payment.id == payment_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Payment not found")
    if payload.comment is not None:
        p.comment = payload.comment
    await session.commit()
    await session.refresh(p)
    return _to_out(p)


@router.delete("/{payment_id}", status_code=204, response_class=Response)
async def delete_payment(
    payment_id: int,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> Response:
    p = (await session.execute(select(Payment).where(Payment.id == payment_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Payment not found")

    # Отозвать связанные подписки
    subs = (
        await session.execute(select(Subscription).where(Subscription.payment_id == p.id))
    ).scalars().all()
    for s in subs:
        if s.status == "active":
            await sub_service.revoke(session, s, status="revoked", notify=True)

    await session.delete(p)
    await session.commit()
    return Response(status_code=204)
