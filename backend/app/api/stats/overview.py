"""GET /api/stats/overview — ядровая сводка для главной админки.

Всегда доступна (без флага analytics): дашборд-главная её дёргает.
Глубокая аналитика вынесена в analytics.py под флаг analytics.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_admin, get_session
from app.models.admin import Admin
from app.models.bot import Bot
from app.models.channel import Channel
from app.models.funnel import Funnel
from app.models.lead import Lead
from app.models.payment import Payment
from app.models.product import Product
from app.models.subscription import Subscription
from app.models.tracking_link import TrackingLink
from app.models.user import User

overview_router = APIRouter(prefix="/stats", tags=["stats"])


@overview_router.get("/overview")
async def overview(
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    now = datetime.now(tz=timezone.utc)
    month_ago = now - timedelta(days=30)
    week_ago = now - timedelta(days=7)
    day_ago = now - timedelta(days=1)

    async def scalar(stmt):
        return (await session.execute(stmt)).scalar_one()

    total_users = await scalar(select(func.count()).select_from(User))
    new_users_7d = await scalar(select(func.count()).select_from(User).where(User.first_seen_at >= week_ago))

    total_leads = await scalar(select(func.count()).select_from(Lead))
    new_leads = await scalar(select(func.count()).select_from(Lead).where(Lead.status == "new"))
    # last_24h — все поступившие за сутки (поток), безотносительно к их сегодняшнему статусу.
    # Это метрика активности, а не "висящих" заявок (для висящих — new_leads).
    leads_24h = await scalar(
        select(func.count()).select_from(Lead).where(Lead.created_at >= day_ago)
    )

    active_subs = await scalar(
        select(func.count()).select_from(Subscription).where(Subscription.status == "active")
    )
    subs_expiring_7d = await scalar(
        select(func.count())
        .select_from(Subscription)
        .where(Subscription.status == "active", Subscription.ends_at <= now + timedelta(days=7))
    )

    revenue_30d = (
        await session.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.created_at >= month_ago)
        )
    ).scalar_one()
    revenue_total = (await session.execute(select(func.coalesce(func.sum(Payment.amount), 0)))).scalar_one()
    payments_30d = await scalar(select(func.count()).select_from(Payment).where(Payment.created_at >= month_ago))

    total_products = await scalar(select(func.count()).select_from(Product))
    total_channels = await scalar(select(func.count()).select_from(Channel))
    total_bots = await scalar(select(func.count()).select_from(Bot).where(Bot.is_active.is_(True)))

    # Последние 5 заявок и платежей для активити
    recent_leads_rows = (
        await session.execute(
            select(Lead, User, Product)
            .join(User, User.id == Lead.user_id)
            .join(Product, Product.id == Lead.product_id)
            .order_by(Lead.id.desc())
            .limit(5)
        )
    ).all()
    recent_payments_rows = (
        await session.execute(
            select(Payment, User, Product)
            .join(User, User.id == Payment.user_id)
            .join(Product, Product.id == Payment.product_id)
            .order_by(Payment.id.desc())
            .limit(5)
        )
    ).all()

    return {
        "users": {"total": total_users, "new_7d": new_users_7d},
        "leads": {"total": total_leads, "new": new_leads, "last_24h": leads_24h},
        "subscriptions": {"active": active_subs, "expiring_7d": subs_expiring_7d},
        "revenue": {
            "total": str(revenue_total),
            "last_30d": str(revenue_30d),
            "payments_30d": payments_30d,
        },
        "catalog": {"products": total_products, "channels": total_channels, "active_bots": total_bots},
        "recent_leads": [
            {
                "id": l.id,
                "status": l.status,
                "created_at": l.created_at.isoformat(),
                "user_id": u.id,
                "user_first_name": u.first_name,
                "user_username": u.username,
                "product_name": p.name,
            }
            for l, u, p in recent_leads_rows
        ],
        "recent_payments": [
            {
                "id": pay.id,
                "amount": str(pay.amount),
                "currency": pay.currency,
                "period_months": pay.period_months,
                "created_at": pay.created_at.isoformat(),
                "user_first_name": u.first_name,
                "user_username": u.username,
                "product_name": p.name,
            }
            for pay, u, p in recent_payments_rows
        ],
    }


# ============================================================
# /sources — агрегированный отчёт по источникам
# ============================================================

