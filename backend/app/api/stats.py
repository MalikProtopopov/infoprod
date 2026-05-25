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
    funnel_id: int | None = Query(default=None),
    group_by: str = Query(default="source", pattern="^(source|campaign|link|funnel)$"),
) -> dict:
    """Отчёт по источникам трафика.

    group_by:
      - source    → группировка по utm_source
      - campaign  → по (utm_source, utm_campaign)
      - link      → по конкретной tracking_link (показываем slug)
      - funnel    → по воронке (показываем funnel.name + кол-во подписок)

    funnel_id фильтр — оставить только ссылки, привязанные к этой воронке
    (и считать лиды/платежи только тех юзеров, кто прошёл через эту воронку).
    """
    if to is None:
        to = datetime.now(tz=timezone.utc)
    if from_ is None:
        from_ = to - timedelta(days=30)

    # --- 1. Клики и unique_users — агрегируем по ссылкам, попадающим в фильтры
    link_select = select(
        TrackingLink.id,
        TrackingLink.slug,
        TrackingLink.utm_source,
        TrackingLink.utm_medium,
        TrackingLink.utm_campaign,
        TrackingLink.click_count,
        TrackingLink.unique_users,
        TrackingLink.funnel_id,
    )
    if product_id is not None:
        link_select = link_select.where(TrackingLink.product_id == product_id)
    if bot_id is not None:
        link_select = link_select.where(TrackingLink.bot_id == bot_id)
    if funnel_id is not None:
        link_select = link_select.where(TrackingLink.funnel_id == funnel_id)

    link_rows = (await session.execute(link_select)).all()

    # Имена воронок — нужны для group_by='funnel'. Грузим только те,
    # которые встречаются в наборе ссылок.
    funnel_ids = {r[7] for r in link_rows if r[7] is not None}
    if funnel_id is not None:
        funnel_ids.add(funnel_id)
    funnel_names: dict[int, str] = {}
    if funnel_ids:
        funnel_names = dict(
            (
                await session.execute(
                    select(Funnel.id, Funnel.name).where(Funnel.id.in_(funnel_ids))
                )
            ).all()
        )

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
    if funnel_id is not None:
        # Лиды только тех юзеров, которые пришли через ссылки этой воронки.
        allowed_link_ids = [r[0] for r in link_rows]
        if allowed_link_ids:
            lead_q = lead_q.where(Lead.tracking_link_id.in_(allowed_link_ids))
        else:
            lead_q = lead_q.where(Lead.id.is_(None))  # пусто
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
    if funnel_id is not None:
        allowed_link_ids = [r[0] for r in link_rows]
        if allowed_link_ids:
            pay_q = pay_q.where(Payment.tracking_link_id.in_(allowed_link_ids))
        else:
            pay_q = pay_q.where(Payment.id.is_(None))
    pay_q = pay_q.group_by(Payment.tracking_link_id)
    pay_rows = (await session.execute(pay_q)).all()

    # Маппинг tracking_link_id -> (payments, revenue)
    pay_by_link: dict[int | None, tuple[int, Decimal]] = {}
    for row in pay_rows:
        pay_by_link[row[0]] = (int(row[1]), Decimal(row[2] or 0))

    # --- 3. Группируем
    def _key(link_id, utm_source, utm_medium, utm_campaign, slug, fn_id):
        if group_by == "link":
            return ("link", link_id, slug, utm_source, utm_medium, utm_campaign)
        if group_by == "campaign":
            return ("campaign", utm_source or "—", utm_campaign or "—")
        if group_by == "funnel":
            return ("funnel", fn_id)
        return ("source", utm_source or "—")

    def _meta(link_id, utm_source, utm_medium, utm_campaign, slug, fn_id):
        if group_by == "link":
            return {
                "tracking_link_id": link_id, "slug": slug,
                "source": utm_source, "medium": utm_medium, "campaign": utm_campaign,
            }
        if group_by == "campaign":
            return {"source": utm_source or None, "campaign": utm_campaign or None}
        if group_by == "funnel":
            return {
                "funnel_id": fn_id,
                "funnel_name": funnel_names.get(fn_id) if fn_id is not None else None,
            }
        return {"source": utm_source or None}

    groups: dict[tuple, dict] = {}

    # Прокатимся по ссылкам — добавим clicks/unique
    for l_id, slug, src, med, camp, clicks, uniq, fn_id in link_rows:
        key = _key(l_id, src, med, camp, slug, fn_id)
        g = groups.setdefault(key, _empty_group())
        g["clicks"] += int(clicks or 0)
        g["unique_users"] += int(uniq or 0)
        g["meta"] = _meta(l_id, src, med, camp, slug, fn_id)

    # Индексация по link_id: O(1) lookup вместо O(N) поиска в цикле.
    link_by_id: dict[int, tuple] = {r[0]: r for r in link_rows}

    # leads
    for tl_id, src, med, camp, cnt in lead_rows:
        slug = None
        fn_id = None
        if tl_id is not None and tl_id in link_by_id:
            row = link_by_id[tl_id]
            slug = row[1]
            fn_id = row[7]
        if tl_id is None and group_by == "link":
            key = ("link", None, None, None, None, None)
        elif tl_id is None and group_by == "funnel":
            # Лиды без tracking_link не относятся ни к одной воронке — пропускаем
            continue
        else:
            key = _key(tl_id, src, med, camp, slug, fn_id)
        g = groups.setdefault(key, _empty_group())
        g["leads"] += int(cnt or 0)
        if "meta" not in g:
            g["meta"] = _meta(tl_id, src, med, camp, slug, fn_id)

    # payments
    for tl_id, (pcnt, prevenue) in pay_by_link.items():
        slug = None
        src = med = camp = None
        fn_id = None
        if tl_id is not None and tl_id in link_by_id:
            row = link_by_id[tl_id]
            _, slug, src, med, camp, _, _, fn_id = row
        if tl_id is None and group_by == "funnel":
            continue
        key = _key(tl_id, src, med, camp, slug, fn_id)
        g = groups.setdefault(key, _empty_group())
        g["payments"] += pcnt
        g["revenue"] = Decimal(g["revenue"]) + prevenue
        if "meta" not in g:
            g["meta"] = _meta(tl_id, src, med, camp, slug, fn_id)

    # --- 3b. Подписки на воронку (funnel_entries) — отдельная колонка.
    # Считаем только entries, пришедшие через ссылки этого набора.
    allowed_link_ids = [r[0] for r in link_rows]
    if allowed_link_ids:
        from app.models.funnel_entry import FunnelEntry as _FE

        entry_q = (
            select(
                _FE.funnel_id,
                _FE.source_ref,
                func.count(_FE.id).label("cnt"),
            )
            .where(
                _FE.source == "tracking_link",
                _FE.source_ref.in_(allowed_link_ids),
                _FE.started_at >= from_,
                _FE.started_at <= to,
            )
            .group_by(_FE.funnel_id, _FE.source_ref)
        )
        for fn_id_e, link_ref, cnt in (await session.execute(entry_q)).all():
            tl_id = int(link_ref)
            link = link_by_id.get(tl_id)
            if link is None:
                continue
            _, slug, src, med, camp, _, _, _ = link
            key = _key(tl_id, src, med, camp, slug, fn_id_e)
            g = groups.setdefault(key, _empty_group())
            g["entries"] = g.get("entries", 0) + int(cnt or 0)
            if "meta" not in g:
                g["meta"] = _meta(tl_id, src, med, camp, slug, fn_id_e)

    # --- 4. Собираем ответ
    rows = []
    totals = {
        "clicks": 0, "unique_users": 0, "leads": 0, "payments": 0,
        "entries": 0, "revenue": Decimal("0"),
    }
    for key, g in groups.items():
        entries = int(g.get("entries") or 0)
        row = {
            **g.get("meta", {}),
            "clicks": int(g["clicks"]),
            "unique_users": int(g["unique_users"]),
            "entries": entries,
            "leads": int(g["leads"]),
            "payments": int(g["payments"]),
            "revenue": str(g["revenue"]),
            "conv_click_to_entry": _safe_div(entries, g["clicks"]),
            "conv_click_to_lead": _safe_div(g["leads"], g["clicks"]),
            "conv_lead_to_payment": _safe_div(g["payments"], g["leads"]),
            "avg_check": _safe_div(g["revenue"], g["payments"]),
        }
        rows.append(row)
        totals["clicks"] += int(g["clicks"])
        totals["unique_users"] += int(g["unique_users"])
        totals["entries"] += entries
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
            "entries": totals["entries"],
            "leads": totals["leads"],
            "payments": totals["payments"],
            "revenue": str(totals["revenue"]),
        },
    }


def _empty_group() -> dict:
    return {
        "clicks": 0, "unique_users": 0, "entries": 0,
        "leads": 0, "payments": 0, "revenue": Decimal("0"),
    }


# ============================================================
# /timeline — лиды/оплаты/выручка во времени с группировкой
# ============================================================

@router.get("/timeline")
async def stats_timeline(
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
    granularity: str = Query(default="day", pattern="^(day|week|month)$"),
    dimension: str = Query(default="source", pattern="^(source|campaign|product|funnel|none)$"),
    product_id: int | None = Query(default=None),
    attribution: str = Query(default="last", pattern="^(last|first)$"),
) -> dict:
    """Timeline по дням/неделям/месяцам, с разрезом по выбранному dimension.

    Attribution:
      - last  → Lead.utm_source / Payment.tracking_link_id (как было ДО оплаты)
      - first → User.first_utm_source (первое касание)

    Возвращает 3 series: leads, payments, revenue.
    """
    if to is None:
        to = datetime.now(tz=timezone.utc)
    if from_ is None:
        from_ = to - timedelta(days=30)

    bucket = func.date_trunc(granularity, Lead.created_at).label("bucket")
    pay_bucket = func.date_trunc(granularity, Payment.created_at).label("bucket")

    # --- Лиды
    if attribution == "first":
        # Берём first_utm_source юзера
        lead_dim_col = User.first_utm_source
        lead_q = (
            select(bucket, lead_dim_col, func.count(Lead.id))
            .join(User, User.id == Lead.user_id)
            .where(Lead.created_at >= from_, Lead.created_at <= to)
        )
    else:
        if dimension == "source":
            lead_dim_col = Lead.utm_source
        elif dimension == "campaign":
            lead_dim_col = Lead.utm_campaign
        elif dimension == "product":
            lead_dim_col = Lead.product_id
        elif dimension == "funnel":
            # Воронка определяется через FunnelEntry, опционально — лидов
            # вне воронок мы помечаем как None.
            lead_dim_col = None
        else:  # none
            lead_dim_col = None
        if lead_dim_col is not None:
            lead_q = (
                select(bucket, lead_dim_col, func.count(Lead.id))
                .where(Lead.created_at >= from_, Lead.created_at <= to)
            )
        else:
            lead_q = (
                select(bucket, func.cast(None, type_=Lead.utm_source.type).label("dim"), func.count(Lead.id))
                .where(Lead.created_at >= from_, Lead.created_at <= to)
            )

    if product_id is not None:
        lead_q = lead_q.where(Lead.product_id == product_id)
    if lead_dim_col is not None:
        lead_q = lead_q.group_by(bucket, lead_dim_col)
    else:
        lead_q = lead_q.group_by(bucket)
    lead_q = lead_q.order_by(bucket)
    lead_rows = (await session.execute(lead_q)).all()

    # --- Оплаты + выручка
    if attribution == "first":
        pay_dim_col = User.first_utm_source
        pay_q = (
            select(pay_bucket, pay_dim_col, func.count(Payment.id), func.coalesce(func.sum(Payment.amount), 0))
            .join(User, User.id == Payment.user_id)
            .where(Payment.created_at >= from_, Payment.created_at <= to)
        )
    else:
        # last-touch: через JOIN на TrackingLink
        if dimension == "source":
            pay_dim_col = TrackingLink.utm_source
        elif dimension == "campaign":
            pay_dim_col = TrackingLink.utm_campaign
        elif dimension == "product":
            pay_dim_col = Payment.product_id
        else:
            pay_dim_col = None
        if pay_dim_col is not None and dimension in ("source", "campaign"):
            pay_q = (
                select(pay_bucket, pay_dim_col, func.count(Payment.id), func.coalesce(func.sum(Payment.amount), 0))
                .select_from(Payment)
                .outerjoin(TrackingLink, TrackingLink.id == Payment.tracking_link_id)
                .where(Payment.created_at >= from_, Payment.created_at <= to)
            )
        elif pay_dim_col is not None:
            pay_q = (
                select(pay_bucket, pay_dim_col, func.count(Payment.id), func.coalesce(func.sum(Payment.amount), 0))
                .where(Payment.created_at >= from_, Payment.created_at <= to)
            )
        else:
            pay_q = (
                select(pay_bucket, func.cast(None, type_=TrackingLink.utm_source.type).label("dim"),
                       func.count(Payment.id), func.coalesce(func.sum(Payment.amount), 0))
                .where(Payment.created_at >= from_, Payment.created_at <= to)
            )

    if product_id is not None:
        pay_q = pay_q.where(Payment.product_id == product_id)
    if pay_dim_col is not None:
        pay_q = pay_q.group_by(pay_bucket, pay_dim_col)
    else:
        pay_q = pay_q.group_by(pay_bucket)
    pay_q = pay_q.order_by(pay_bucket)
    pay_rows = (await session.execute(pay_q)).all()

    # --- Сборка points: { date, dim, leads, payments, revenue }
    bucket_set: set[str] = set()
    dims_set: set[str] = set()
    by_bd: dict[tuple[str, str], dict] = {}

    def _key(d, dim):
        ds = d.isoformat() if hasattr(d, "isoformat") else str(d)
        dm = str(dim) if dim is not None else "organic"
        bucket_set.add(ds)
        dims_set.add(dm)
        return (ds, dm)

    for row in lead_rows:
        d, dim, cnt = row[0], row[1], row[2]
        k = _key(d, dim)
        by_bd.setdefault(k, {"leads": 0, "payments": 0, "revenue": Decimal("0")})
        by_bd[k]["leads"] += int(cnt or 0)

    for row in pay_rows:
        d, dim, cnt, rev = row[0], row[1], row[2], row[3]
        k = _key(d, dim)
        by_bd.setdefault(k, {"leads": 0, "payments": 0, "revenue": Decimal("0")})
        by_bd[k]["payments"] += int(cnt or 0)
        by_bd[k]["revenue"] += Decimal(rev or 0)

    points = [
        {
            "date": ds,
            "dim": dm,
            "leads": v["leads"],
            "payments": v["payments"],
            "revenue": str(v["revenue"]),
        }
        for (ds, dm), v in sorted(by_bd.items(), key=lambda x: (x[0][0], x[0][1]))
    ]
    totals = {
        "leads": sum(v["leads"] for v in by_bd.values()),
        "payments": sum(v["payments"] for v in by_bd.values()),
        "revenue": str(sum((v["revenue"] for v in by_bd.values()), Decimal("0"))),
    }

    return {
        "from": from_.isoformat(),
        "to": to.isoformat(),
        "granularity": granularity,
        "dimension": dimension,
        "attribution": attribution,
        "dims": sorted(dims_set),
        "buckets": sorted(bucket_set),
        "points": points,
        "totals": totals,
    }


# ============================================================
# /funnels/{id}/conversion — step-by-step метрики
# ============================================================

@router.get("/funnels/{funnel_id}/conversion")
async def funnel_conversion(
    funnel_id: int,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
) -> dict:
    """Step-by-step метрики воронки на основе ScheduledMessage.

    Включает honest-breakdown: delivered / pending / cancelled / failed.
    Также — сколько после каждого шага юзер сделал Lead и Payment.
    """
    from app.models.funnel import Funnel
    from app.models.funnel_step import FunnelStep
    from app.models.funnel_entry import FunnelEntry
    from app.models.scheduled_message import ScheduledMessage

    f = await session.get(Funnel, funnel_id)
    if f is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Funnel not found")

    if to is None:
        to = datetime.now(tz=timezone.utc)
    if from_ is None:
        from_ = to - timedelta(days=30)

    # Все шаги воронки
    steps = (
        await session.execute(
            select(FunnelStep)
            .where(FunnelStep.funnel_id == funnel_id)
            .order_by(FunnelStep.order_idx)
        )
    ).scalars().all()

    # Все entries в периоде (исключая тестовые)
    entry_rows = (
        await session.execute(
            select(FunnelEntry.id, FunnelEntry.status, FunnelEntry.cancel_reason)
            .where(
                FunnelEntry.funnel_id == funnel_id,
                FunnelEntry.started_at >= from_,
                FunnelEntry.started_at <= to,
                FunnelEntry.source != "manual",
            )
        )
    ).all()
    entry_ids = [e[0] for e in entry_rows]
    total_entered = len(entry_ids)
    completed = sum(1 for e in entry_rows if e[1] == "completed")
    cancelled_by_payment = sum(
        1 for e in entry_rows if e[1] == "cancelled" and (e[2] or "") == "paid"
    )
    cancelled_other = sum(
        1 for e in entry_rows if e[1] == "cancelled" and (e[2] or "") != "paid"
    )
    successful_outcomes = completed + cancelled_by_payment

    # Per-step метрики
    step_metrics: list[dict] = []
    if entry_ids:
        sm_rows = (
            await session.execute(
                select(
                    ScheduledMessage.funnel_step_id,
                    func.count(ScheduledMessage.id).filter(ScheduledMessage.sent_at.isnot(None)).label("delivered"),
                    func.count(ScheduledMessage.id).filter(
                        ScheduledMessage.sent_at.is_(None),
                        ScheduledMessage.scheduled_at > datetime.now(tz=timezone.utc),
                        ScheduledMessage.cancelled_at.is_(None),
                        ScheduledMessage.error.is_(None),
                    ).label("pending"),
                    func.count(ScheduledMessage.id).filter(ScheduledMessage.cancelled_at.isnot(None)).label("cancelled"),
                    func.count(ScheduledMessage.id).filter(ScheduledMessage.error.isnot(None)).label("failed"),
                )
                .where(ScheduledMessage.funnel_entry_id.in_(entry_ids))
                .group_by(ScheduledMessage.funnel_step_id)
            )
        ).all()
        by_step = {r[0]: r for r in sm_rows}
        for s in steps:
            r = by_step.get(s.id)
            step_metrics.append({
                "step_id": s.id,
                "order_idx": s.order_idx,
                "message_preview": s.message_text[:120],
                "delay_minutes": s.delay_minutes,
                "delivered": int(r[1]) if r else 0,
                "pending": int(r[2]) if r else 0,
                "cancelled": int(r[3]) if r else 0,
                "failed": int(r[4]) if r else 0,
            })
    else:
        for s in steps:
            step_metrics.append({
                "step_id": s.id,
                "order_idx": s.order_idx,
                "message_preview": s.message_text[:120],
                "delay_minutes": s.delay_minutes,
                "delivered": 0, "pending": 0, "cancelled": 0, "failed": 0,
            })

    # Атрибутированная выручка: оплаты юзеров, попавших в эти entries
    revenue_attributed = Decimal("0")
    payments_attributed = 0
    if entry_ids:
        user_ids_row = (
            await session.execute(
                select(FunnelEntry.user_id).where(FunnelEntry.id.in_(entry_ids))
            )
        ).all()
        user_ids = [u[0] for u in user_ids_row]
        if user_ids:
            pay_q = (
                select(func.count(Payment.id), func.coalesce(func.sum(Payment.amount), 0))
                .where(
                    Payment.user_id.in_(user_ids),
                    Payment.product_id == f.product_id,
                    Payment.created_at >= from_,
                    Payment.created_at <= to,
                )
            )
            row = (await session.execute(pay_q)).one()
            payments_attributed = int(row[0] or 0)
            revenue_attributed = Decimal(row[1] or 0)

    cvr_step_to_pay = _safe_div(payments_attributed, total_entered)

    return {
        "funnel_id": funnel_id,
        "funnel_name": f.name,
        "from": from_.isoformat(),
        "to": to.isoformat(),
        "total_entered": total_entered,
        "completed": completed,
        "cancelled_by_payment": cancelled_by_payment,
        "cancelled_other": cancelled_other,
        "successful_outcomes": successful_outcomes,
        "payments_attributed": payments_attributed,
        "revenue_attributed": str(revenue_attributed),
        "cvr_entry_to_payment": cvr_step_to_pay,
        "steps": step_metrics,
    }


# ============================================================
# /funnels/summary — топ воронок за период
# ============================================================

@router.get("/funnels/summary")
async def funnels_summary(
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
) -> dict:
    """Список всех воронок с базовыми метриками за период (для Pareto-блока)."""
    from app.models.funnel import Funnel
    from app.models.funnel_entry import FunnelEntry

    if to is None:
        to = datetime.now(tz=timezone.utc)
    if from_ is None:
        from_ = to - timedelta(days=30)

    funnels = (
        await session.execute(select(Funnel).order_by(Funnel.id.desc()))
    ).scalars().all()
    if not funnels:
        return {"from": from_.isoformat(), "to": to.isoformat(), "rows": []}

    funnel_ids = [f.id for f in funnels]

    # entries — исключаем manual (тестовые)
    entry_rows = (
        await session.execute(
            select(FunnelEntry.funnel_id, FunnelEntry.status, FunnelEntry.cancel_reason)
            .where(
                FunnelEntry.funnel_id.in_(funnel_ids),
                FunnelEntry.started_at >= from_,
                FunnelEntry.started_at <= to,
                FunnelEntry.source != "manual",
            )
        )
    ).all()
    by_funnel: dict[int, dict] = {}
    for fid, st, reason in entry_rows:
        m = by_funnel.setdefault(fid, {"entered": 0, "completed": 0, "cancelled_paid": 0, "cancelled_other": 0})
        m["entered"] += 1
        if st == "completed":
            m["completed"] += 1
        elif st == "cancelled":
            if (reason or "") == "paid":
                m["cancelled_paid"] += 1
            else:
                m["cancelled_other"] += 1

    # Платежи — один запрос вместо N+1.
    # JOIN FunnelEntry → Funnel → Payment (user_id и product_id),
    # DISTINCT по (funnel_id, payment_id) убирает дубликаты от повторных entries того же юзера.
    attributed = (
        select(
            FunnelEntry.funnel_id.label("funnel_id"),
            Payment.id.label("payment_id"),
            Payment.amount.label("amount"),
        )
        .select_from(FunnelEntry)
        .join(Funnel, Funnel.id == FunnelEntry.funnel_id)
        .join(
            Payment,
            and_(
                Payment.user_id == FunnelEntry.user_id,
                Payment.product_id == Funnel.product_id,
            ),
        )
        .where(
            FunnelEntry.funnel_id.in_(funnel_ids),
            FunnelEntry.started_at >= from_,
            FunnelEntry.started_at <= to,
            FunnelEntry.source != "manual",
            Payment.created_at >= from_,
            Payment.created_at <= to,
        )
        .distinct()
    ).subquery()
    pay_rows = (
        await session.execute(
            select(
                attributed.c.funnel_id,
                func.count(attributed.c.payment_id),
                func.coalesce(func.sum(attributed.c.amount), 0),
            ).group_by(attributed.c.funnel_id)
        )
    ).all()
    pay_by_funnel: dict[int, tuple[int, Decimal]] = {
        fid: (int(pcnt or 0), Decimal(rev or 0)) for fid, pcnt, rev in pay_rows
    }
    for f in funnels:
        pay_by_funnel.setdefault(f.id, (0, Decimal("0")))

    rows = []
    for f in funnels:
        m = by_funnel.get(f.id, {"entered": 0, "completed": 0, "cancelled_paid": 0, "cancelled_other": 0})
        pcnt, prev = pay_by_funnel[f.id]
        success = m["completed"] + m["cancelled_paid"]
        rows.append({
            "funnel_id": f.id,
            "name": f.name,
            "product_id": f.product_id,
            "is_active": f.is_active,
            "entered": m["entered"],
            "successful_outcomes": success,
            "completed": m["completed"],
            "cancelled_by_payment": m["cancelled_paid"],
            "cancelled_other": m["cancelled_other"],
            "payments": pcnt,
            "revenue": str(prev),
            "cvr": _safe_div(pcnt, m["entered"]),
        })
    rows.sort(key=lambda r: float(r["revenue"]), reverse=True)
    return {
        "from": from_.isoformat(),
        "to": to.isoformat(),
        "rows": rows,
    }


# ============================================================
# /health — diagnostic-info для onboarding-блока в /analytics
# ============================================================

@router.get("/health")
async def stats_health(
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Diagnostic-сводка для UI: что есть, чего не хватает, какие warnings."""
    from app.models.funnel import Funnel

    async def scalar(stmt):
        return (await session.execute(stmt)).scalar_one()

    now = datetime.now(tz=timezone.utc)
    month_ago = now - timedelta(days=30)

    leads_30d = await scalar(
        select(func.count()).select_from(Lead).where(Lead.created_at >= month_ago)
    )
    leads_attributed_30d = await scalar(
        select(func.count()).select_from(Lead).where(
            Lead.created_at >= month_ago, Lead.tracking_link_id.is_not(None)
        )
    )
    total_tracking_links = await scalar(select(func.count()).select_from(TrackingLink))
    active_tracking_links = await scalar(
        select(func.count()).select_from(TrackingLink).where(TrackingLink.is_active.is_(True))
    )
    total_payments_30d = await scalar(
        select(func.count()).select_from(Payment).where(Payment.created_at >= month_ago)
    )
    revenue_30d = (
        await session.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.created_at >= month_ago)
        )
    ).scalar_one()

    funnels_total = await scalar(select(func.count()).select_from(Funnel))
    funnels_active = await scalar(
        select(func.count()).select_from(Funnel).where(Funnel.is_active.is_(True))
    )

    # ScheduledMessage health
    from app.models.scheduled_message import ScheduledMessage
    sm_total = await scalar(select(func.count()).select_from(ScheduledMessage))
    sm_failed = await scalar(
        select(func.count()).select_from(ScheduledMessage).where(ScheduledMessage.error.is_not(None))
    )
    sm_sent = await scalar(
        select(func.count()).select_from(ScheduledMessage).where(ScheduledMessage.sent_at.is_not(None))
    )

    # Test data pollution
    from app.models.funnel_entry import FunnelEntry
    test_entries = await scalar(
        select(func.count()).select_from(FunnelEntry).where(FunnelEntry.source == "manual")
    )
    test_users = await scalar(
        select(func.count()).select_from(User).where(User.telegram_user_id < 0)
    )

    # users with notifications off
    notif_off = await scalar(
        select(func.count()).select_from(User).where(User.notifications_enabled.is_(False))
    )
    total_users = await scalar(select(func.count()).select_from(User))
    notif_off_pct = _safe_div(notif_off, total_users) * 100

    attribution_pct = _safe_div(leads_attributed_30d, leads_30d) * 100

    warnings: list[dict] = []
    if total_tracking_links == 0:
        warnings.append({
            "key": "no_tracking_links",
            "severity": "warning",
            "title": "Нет ни одной tracking-ссылки",
            "message": "Без них невозможно отследить откуда пришли юзеры. Откройте продукт и создайте первую ссылку — после этого появятся метрики по источникам.",
            "action": {"label": "К продуктам", "href": "/products"},
        })
    elif leads_30d > 5 and attribution_pct < 20:
        warnings.append({
            "key": "low_attribution",
            "severity": "warning",
            "title": f"Только {attribution_pct:.0f}% лидов имеют атрибуцию",
            "message": "Большинство юзеров приходят без tracking-ссылок. Размещайте ссылки во всех каналах продвижения.",
            "action": {"label": "К продуктам", "href": "/products"},
        })

    if sm_total > 0 and _safe_div(sm_failed, sm_total) > 0.2:
        warnings.append({
            "key": "high_sm_error_rate",
            "severity": "error",
            "title": f"Бот не доставил {sm_failed} из {sm_total} сообщений воронки",
            "message": "Возможные причины: юзеры заблокировали бота, либо это тестовые запуски от админа без TG-аккаунта.",
            "action": None,
        })

    if test_entries > 0:
        warnings.append({
            "key": "test_data_present",
            "severity": "info",
            "title": f"В данных есть {test_entries} тестовых прогонов",
            "message": "Они исключены из аналитики автоматически (source='manual').",
            "action": None,
        })

    if notif_off_pct > 20:
        warnings.append({
            "key": "high_notif_off",
            "severity": "warning",
            "title": f"{notif_off_pct:.0f}% юзеров отключили уведомления",
            "message": "Воронки и лидмагниты до них не доходят. Step-conversion для них занижена объективно.",
            "action": None,
        })

    if funnels_total == 0:
        warnings.append({
            "key": "no_funnels",
            "severity": "info",
            "title": "Воронок ещё нет",
            "message": "Воронка — серия сообщений, которые бот сам шлёт юзеру после подписки. Помогает прогревать к покупке.",
            "action": {"label": "Создать воронку", "href": "/funnels"},
        })

    return {
        "summary": {
            "leads_30d": leads_30d,
            "leads_attributed_30d": leads_attributed_30d,
            "attribution_pct": round(attribution_pct, 1),
            "tracking_links_total": total_tracking_links,
            "tracking_links_active": active_tracking_links,
            "payments_30d": total_payments_30d,
            "revenue_30d": str(revenue_30d),
            "funnels_total": funnels_total,
            "funnels_active": funnels_active,
            "scheduled_messages_total": sm_total,
            "scheduled_messages_sent": sm_sent,
            "scheduled_messages_failed": sm_failed,
            "test_entries": test_entries,
            "test_users": test_users,
            "users_total": total_users,
            "users_notifications_off": notif_off,
            "users_notifications_off_pct": round(notif_off_pct, 1),
        },
        "warnings": warnings,
    }
