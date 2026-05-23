from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_admin, get_session
from app.models.admin import Admin
from app.models.bot import Bot
from app.models.channel import Channel
from app.models.lead import Lead
from app.models.payment import Payment
from app.models.product import Product
from app.models.subscription import Subscription
from app.models.tracking_link import TrackingLink
from app.models.user import User

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/overview")
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

def _safe_div(a, b) -> float:
    try:
        b_f = float(b)
        return float(a) / b_f if b_f > 0 else 0.0
    except (TypeError, ValueError):
        return 0.0


@router.get("/sources")
async def stats_sources(
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
    product_id: int | None = Query(default=None),
    bot_id: int | None = Query(default=None),
    group_by: str = Query(default="source", pattern="^(source|campaign|link)$"),
) -> dict:
    """Отчёт по источникам трафика.

    group_by:
      - source    → группировка по utm_source
      - campaign  → по (utm_source, utm_campaign)
      - link      → по конкретной tracking_link (показываем slug)
    """
    if to is None:
        to = datetime.now(tz=timezone.utc)
    if from_ is None:
        from_ = to - timedelta(days=30)

    # --- 1. Клики и unique_users — агрегируем по ссылкам, попадающим в фильтры
    link_filters = []
    if product_id is not None:
        link_filters.append(TrackingLink.product_id == product_id)
    if bot_id is not None:
        link_filters.append(TrackingLink.bot_id == bot_id)

    link_rows = (
        await session.execute(
            select(
                TrackingLink.id,
                TrackingLink.slug,
                TrackingLink.utm_source,
                TrackingLink.utm_medium,
                TrackingLink.utm_campaign,
                TrackingLink.click_count,
                TrackingLink.unique_users,
            ).where(*link_filters) if link_filters else select(
                TrackingLink.id,
                TrackingLink.slug,
                TrackingLink.utm_source,
                TrackingLink.utm_medium,
                TrackingLink.utm_campaign,
                TrackingLink.click_count,
                TrackingLink.unique_users,
            )
        )
    ).all()

    # --- 2. Leads + payments по периоду
    lead_q = (
        select(
            Lead.tracking_link_id,
            Lead.utm_source,
            Lead.utm_medium,
            Lead.utm_campaign,
            func.count(Lead.id).label("cnt"),
        )
        .where(Lead.created_at >= from_, Lead.created_at <= to)
    )
    if product_id is not None:
        lead_q = lead_q.where(Lead.product_id == product_id)
    lead_q = lead_q.group_by(Lead.tracking_link_id, Lead.utm_source, Lead.utm_medium, Lead.utm_campaign)
    lead_rows = (await session.execute(lead_q)).all()

    pay_q = (
        select(
            Payment.tracking_link_id,
            func.count(Payment.id).label("cnt"),
            func.coalesce(func.sum(Payment.amount), 0).label("revenue"),
        )
        .where(Payment.created_at >= from_, Payment.created_at <= to)
    )
    if product_id is not None:
        pay_q = pay_q.where(Payment.product_id == product_id)
    pay_q = pay_q.group_by(Payment.tracking_link_id)
    pay_rows = (await session.execute(pay_q)).all()

    # Маппинг tracking_link_id -> (payments, revenue)
    pay_by_link: dict[int | None, tuple[int, Decimal]] = {}
    for row in pay_rows:
        pay_by_link[row[0]] = (int(row[1]), Decimal(row[2] or 0))

    # --- 3. Группируем
    def _key(link_id, utm_source, utm_medium, utm_campaign, slug):
        if group_by == "link":
            return ("link", link_id, slug, utm_source, utm_medium, utm_campaign)
        if group_by == "campaign":
            return ("campaign", utm_source or "—", utm_campaign or "—")
        return ("source", utm_source or "—")

    groups: dict[tuple, dict] = {}

    # Прокатимся по ссылкам — добавим clicks/unique
    for l_id, slug, src, med, camp, clicks, uniq in link_rows:
        key = _key(l_id, src, med, camp, slug)
        g = groups.setdefault(key, _empty_group())
        g["clicks"] += int(clicks or 0)
        g["unique_users"] += int(uniq or 0)
        if group_by == "link":
            g["meta"] = {
                "tracking_link_id": l_id,
                "slug": slug,
                "source": src,
                "medium": med,
                "campaign": camp,
            }
        elif group_by == "campaign":
            g["meta"] = {"source": src or None, "campaign": camp or None}
        else:
            g["meta"] = {"source": src or None}

    # Индексация по link_id: O(1) lookup вместо O(N) поиска в цикле.
    # Защищает /sources от O(N×M) при росте числа ссылок.
    link_by_id: dict[int, tuple] = {r[0]: r for r in link_rows}

    # leads
    for tl_id, src, med, camp, cnt in lead_rows:
        slug = None
        if tl_id is not None and tl_id in link_by_id:
            slug = link_by_id[tl_id][1]
        if tl_id is None and group_by == "link":
            # Лиды без атрибуции — отдельная группа "органика"
            key = ("link", None, None, None, None, None)
        else:
            key = _key(tl_id, src, med, camp, slug)
        g = groups.setdefault(key, _empty_group())
        g["leads"] += int(cnt or 0)
        if "meta" not in g:
            if group_by == "link":
                g["meta"] = {
                    "tracking_link_id": tl_id,
                    "slug": slug,
                    "source": src,
                    "medium": med,
                    "campaign": camp,
                }
            elif group_by == "campaign":
                g["meta"] = {"source": src or None, "campaign": camp or None}
            else:
                g["meta"] = {"source": src or None}

    # payments
    for tl_id, (pcnt, prevenue) in pay_by_link.items():
        slug = None
        src = med = camp = None
        if tl_id is not None and tl_id in link_by_id:
            _, slug, src, med, camp, _, _ = link_by_id[tl_id]
        key = _key(tl_id, src, med, camp, slug)
        g = groups.setdefault(key, _empty_group())
        g["payments"] += pcnt
        g["revenue"] = Decimal(g["revenue"]) + prevenue
        if "meta" not in g:
            if group_by == "link":
                g["meta"] = {
                    "tracking_link_id": tl_id,
                    "slug": slug,
                    "source": src,
                    "medium": med,
                    "campaign": camp,
                }
            elif group_by == "campaign":
                g["meta"] = {"source": src or None, "campaign": camp or None}
            else:
                g["meta"] = {"source": src or None}

    # --- 4. Собираем ответ
    rows = []
    totals = {"clicks": 0, "unique_users": 0, "leads": 0, "payments": 0, "revenue": Decimal("0")}
    for key, g in groups.items():
        row = {
            **g.get("meta", {}),
            "clicks": int(g["clicks"]),
            "unique_users": int(g["unique_users"]),
            "leads": int(g["leads"]),
            "payments": int(g["payments"]),
            "revenue": str(g["revenue"]),
            "conv_click_to_lead": _safe_div(g["leads"], g["clicks"]),
            "conv_lead_to_payment": _safe_div(g["payments"], g["leads"]),
            "avg_check": _safe_div(g["revenue"], g["payments"]),
        }
        rows.append(row)
        totals["clicks"] += int(g["clicks"])
        totals["unique_users"] += int(g["unique_users"])
        totals["leads"] += int(g["leads"])
        totals["payments"] += int(g["payments"])
        totals["revenue"] += Decimal(g["revenue"])

    # Сортируем по выручке убыванию
    rows.sort(key=lambda r: float(r.get("revenue") or 0), reverse=True)

    return {
        "from": from_.isoformat(),
        "to": to.isoformat(),
        "group_by": group_by,
        "rows": rows,
        "totals": {
            "clicks": totals["clicks"],
            "unique_users": totals["unique_users"],
            "leads": totals["leads"],
            "payments": totals["payments"],
            "revenue": str(totals["revenue"]),
        },
    }


def _empty_group() -> dict:
    return {"clicks": 0, "unique_users": 0, "leads": 0, "payments": 0, "revenue": Decimal("0")}
