"""Расширенные тесты /api/stats: group_by=link, фильтры, conv-метрики, totals."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest


@pytest.mark.asyncio
async def test_overview_with_realistic_data(admin_client, make_committed, clean_db):
    """overview агрегирует users/leads/subs/revenue/catalog."""
    now = datetime.now(tz=timezone.utc)
    user1 = await make_committed.user()
    user2 = await make_committed.user()
    channel = await make_committed.channel()
    product = await make_committed.product(channel=channel)
    await make_committed.lead(user=user1, product=product, status="new")
    await make_committed.lead(user=user2, product=product, status="paid")
    await make_committed.payment(user=user2, product=product, amount=1500)
    await make_committed.subscription(
        user=user2, channel=channel, status="active",
        ends_at=now + timedelta(days=5),
    )

    r = await admin_client.get("/api/stats/overview")
    assert r.status_code == 200
    body = r.json()

    assert body["users"]["total"] == 2
    assert body["leads"]["total"] == 2
    assert body["leads"]["new"] == 1
    assert body["subscriptions"]["active"] == 1
    assert body["subscriptions"]["expiring_7d"] == 1
    assert float(body["revenue"]["total"]) == 1500.0
    assert body["catalog"]["products"] == 1
    assert body["catalog"]["channels"] == 1
    # recent_leads/payments — 2 и 1 соответственно
    assert len(body["recent_leads"]) == 2
    assert len(body["recent_payments"]) == 1


@pytest.mark.asyncio
async def test_sources_group_by_link_returns_slug_and_meta(admin_client, make_committed, clean_db):
    product = await make_committed.product()
    link = await make_committed.tracking_link(
        product=product, slug="abc12345", utm_source="ig", utm_medium="reels",
        utm_campaign="spring", click_count=50, unique_users=40,
    )

    r = await admin_client.get("/api/stats/sources?group_by=link")
    assert r.status_code == 200
    body = r.json()
    assert body["group_by"] == "link"
    row = next((r for r in body["rows"] if r.get("slug") == "abc12345"), None)
    assert row is not None
    assert row["tracking_link_id"] == link.id
    assert row["source"] == "ig"
    assert row["medium"] == "reels"
    assert row["campaign"] == "spring"
    assert row["clicks"] == 50
    assert row["unique_users"] == 40


@pytest.mark.asyncio
async def test_sources_includes_conv_metrics(admin_client, make_committed, engine, clean_db):
    """conv_click_to_lead, conv_lead_to_payment, avg_check."""
    product = await make_committed.product()
    link = await make_committed.tracking_link(
        product=product, slug="conv1234", utm_source="yt",
        click_count=100, unique_users=80,
    )
    user = await make_committed.user(
        first_tracking_link_id=link.id, first_product_id=product.id,
    )
    await make_committed.lead(user=user, product=product, status="paid")
    await make_committed.payment(user=user, product=product, amount=2000)

    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE leads SET tracking_link_id=:l, utm_source=:s WHERE user_id=:uid"),
            {"l": link.id, "s": "yt", "uid": user.id},
        )
        await conn.execute(
            text("UPDATE payments SET tracking_link_id=:l WHERE user_id=:uid"),
            {"l": link.id, "uid": user.id},
        )

    r = await admin_client.get("/api/stats/sources?group_by=source")
    body = r.json()
    yt = next((r for r in body["rows"] if r.get("source") == "yt"), None)
    assert yt is not None
    # 1 lead / 100 clicks = 0.01
    assert abs(yt["conv_click_to_lead"] - 0.01) < 0.001
    assert yt["conv_lead_to_payment"] == 1.0
    assert float(yt["avg_check"]) == 2000.0


async def _direct_sql(engine, sql, params):
    """Прямой SQL через переданный engine fixture."""
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.execute(text(sql), params)


@pytest.mark.asyncio
async def test_sources_filter_by_product_id(admin_client, make_committed, clean_db):
    p1 = await make_committed.product()
    p2 = await make_committed.product()
    await make_committed.tracking_link(product=p1, utm_source="ig", click_count=10)
    await make_committed.tracking_link(product=p2, utm_source="yt", click_count=20)

    r = await admin_client.get(f"/api/stats/sources?product_id={p1.id}&group_by=source")
    body = r.json()
    sources = {row.get("source") for row in body["rows"]}
    assert "ig" in sources
    assert "yt" not in sources  # filtered out


@pytest.mark.asyncio
async def test_sources_filter_by_bot_id(admin_client, make_committed, clean_db):
    bot1 = await make_committed.bot()
    bot2 = await make_committed.bot()
    ch1 = await make_committed.channel(bot=bot1)
    ch2 = await make_committed.channel(bot=bot2)
    p1 = await make_committed.product(channel=ch1)
    p2 = await make_committed.product(channel=ch2)
    await make_committed.tracking_link(
        product=p1, bot_id=bot1.id, utm_source="ig", click_count=5,
    )
    await make_committed.tracking_link(
        product=p2, bot_id=bot2.id, utm_source="yt", click_count=15,
    )

    r = await admin_client.get(f"/api/stats/sources?bot_id={bot1.id}&group_by=source")
    body = r.json()
    sources = {row.get("source") for row in body["rows"]}
    assert "ig" in sources
    assert "yt" not in sources


@pytest.mark.asyncio
async def test_sources_with_date_range(admin_client, make_committed, clean_db):
    """from/to фильтры режут leads/payments по периоду."""
    product = await make_committed.product()
    await make_committed.tracking_link(product=product, utm_source="ig", click_count=5)

    from urllib.parse import quote
    now = datetime.now(tz=timezone.utc)
    from_ = quote((now - timedelta(days=7)).isoformat())
    to = quote((now + timedelta(days=1)).isoformat())

    r = await admin_client.get(
        f"/api/stats/sources?from={from_}&to={to}&group_by=source",
    )
    assert r.status_code == 200
    body = r.json()
    # Окно охватывает now → клики (созданные сейчас) попадут
    assert any(row.get("source") == "ig" for row in body["rows"])


@pytest.mark.asyncio
async def test_sources_totals_match_rows_sum(admin_client, make_committed, clean_db):
    product = await make_committed.product()
    await make_committed.tracking_link(
        product=product, utm_source="ig", click_count=10, unique_users=8,
    )
    await make_committed.tracking_link(
        product=product, utm_source="yt", click_count=20, unique_users=15,
    )

    r = await admin_client.get("/api/stats/sources?group_by=source")
    body = r.json()
    sum_clicks = sum(row["clicks"] for row in body["rows"])
    sum_unique = sum(row["unique_users"] for row in body["rows"])
    assert body["totals"]["clicks"] == sum_clicks
    assert body["totals"]["unique_users"] == sum_unique
    # Конкретно
    assert body["totals"]["clicks"] == 30
    assert body["totals"]["unique_users"] == 23


@pytest.mark.asyncio
async def test_sources_organic_traffic_no_tracking_link(admin_client, make_committed, clean_db):
    """Лиды без tracking_link_id попадают в группу 'органика' (utm_source=None)."""
    product = await make_committed.product()
    user = await make_committed.user()
    await make_committed.lead(user=user, product=product, status="new")
    # tracking_link_id=NULL по умолчанию

    r = await admin_client.get("/api/stats/sources?group_by=source")
    body = r.json()
    organic = next((r for r in body["rows"] if r.get("source") is None), None)
    assert organic is not None
    assert organic["leads"] == 1


@pytest.mark.asyncio
async def test_sources_rows_sorted_by_revenue_desc(admin_client, make_committed, engine, clean_db):
    """Строки сортируются по revenue убыванию."""
    product = await make_committed.product()
    user1 = await make_committed.user()
    user2 = await make_committed.user()

    link_a = await make_committed.tracking_link(
        product=product, slug="srcabig1", utm_source="big",
    )
    link_b = await make_committed.tracking_link(
        product=product, slug="srcsma11", utm_source="small",
    )

    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO payments (user_id, product_id, period_months, amount, "
                "currency, tracking_link_id, created_at) "
                "VALUES (:u, :p, 3, 5000, 'RUB', :l, NOW())"
            ),
            {"u": user1.id, "p": product.id, "l": link_a.id},
        )
        await conn.execute(
            text(
                "INSERT INTO payments (user_id, product_id, period_months, amount, "
                "currency, tracking_link_id, created_at) "
                "VALUES (:u, :p, 3, 100, 'RUB', :l, NOW())"
            ),
            {"u": user2.id, "p": product.id, "l": link_b.id},
        )

    r = await admin_client.get("/api/stats/sources?group_by=source")
    body = r.json()
    sources_with_rev = [row for row in body["rows"] if float(row.get("revenue") or 0) > 0]
    revenues = [float(row["revenue"]) for row in sources_with_rev]
    assert revenues == sorted(revenues, reverse=True)
