"""Edge cases для /api/stats — link grouping без атрибуции, payment-only, totals."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_group_by_link_with_organic_lead(admin_client, make_committed, clean_db):
    """group_by=link: лиды без tracking_link_id попадают в ключ '—'."""
    product = await make_committed.product()
    user = await make_committed.user()
    await make_committed.lead(user=user, product=product, status="new")

    r = await admin_client.get("/api/stats/sources?group_by=link")
    body = r.json()
    organic = next((row for row in body["rows"] if row.get("slug") is None), None)
    assert organic is not None
    assert organic["leads"] == 1


@pytest.mark.asyncio
async def test_group_by_link_with_payment_only(
    admin_client, make_committed, engine, clean_db,
):
    """payment с tracking_link_id, без linked lead — попадает в группу link."""
    product = await make_committed.product()
    link = await make_committed.tracking_link(
        product=product, slug="payonly1", utm_source="ig", click_count=5,
    )
    user = await make_committed.user()
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO payments (user_id, product_id, period_months, amount, "
                "currency, tracking_link_id, created_at) "
                "VALUES (:u, :p, 3, 999, 'RUB', :l, NOW())"
            ),
            {"u": user.id, "p": product.id, "l": link.id},
        )

    r = await admin_client.get("/api/stats/sources?group_by=link")
    body = r.json()
    row = next((r for r in body["rows"] if r.get("slug") == "payonly1"), None)
    assert row is not None
    assert row["payments"] == 1
    assert float(row["revenue"]) == 999.0


@pytest.mark.asyncio
async def test_overview_with_no_data(admin_client, clean_db):
    """Пустая БД — overview возвращает нули, не падает."""
    r = await admin_client.get("/api/stats/overview")
    assert r.status_code == 200
    body = r.json()
    assert body["users"]["total"] == 0
    assert body["leads"]["total"] == 0
    assert body["subscriptions"]["active"] == 0
    assert body["catalog"]["products"] == 0
    assert body["recent_leads"] == []
    assert body["recent_payments"] == []


@pytest.mark.asyncio
async def test_sources_group_by_campaign_with_null_campaign(
    admin_client, make_committed, clean_db,
):
    """utm_campaign=NULL должно показываться как '—'."""
    product = await make_committed.product()
    await make_committed.tracking_link(
        product=product, utm_source="ig", utm_campaign=None, click_count=10,
    )

    r = await admin_client.get("/api/stats/sources?group_by=campaign")
    body = r.json()
    null_camp = next(
        (row for row in body["rows"] if row.get("campaign") in (None, "")),
        None,
    )
    assert null_camp is not None


@pytest.mark.asyncio
async def test_sources_only_to_param(admin_client, make_committed, clean_db):
    """Только `to` без `from` — должно работать (from = to - 30d)."""
    from datetime import datetime, timezone
    from urllib.parse import quote
    to_iso = quote(datetime.now(tz=timezone.utc).isoformat())
    r = await admin_client.get(f"/api/stats/sources?to={to_iso}&group_by=source")
    assert r.status_code == 200
    body = r.json()
    assert "from" in body and "to" in body


@pytest.mark.asyncio
async def test_sources_filter_combination_product_bot(admin_client, make_committed, clean_db):
    """Двойной фильтр product_id + bot_id."""
    bot = await make_committed.bot()
    channel = await make_committed.channel(bot=bot)
    product = await make_committed.product(channel=channel)
    await make_committed.tracking_link(
        product=product, bot_id=bot.id, utm_source="ig", click_count=7,
    )

    r = await admin_client.get(
        f"/api/stats/sources?product_id={product.id}&bot_id={bot.id}&group_by=source",
    )
    body = r.json()
    assert any(row.get("source") == "ig" for row in body["rows"])
    assert body["totals"]["clicks"] == 7


@pytest.mark.asyncio
async def test_sources_response_includes_dates(admin_client, clean_db):
    """from/to всегда есть в ответе (даже если не передавали)."""
    r = await admin_client.get("/api/stats/sources?group_by=source")
    body = r.json()
    assert "from" in body
    assert "to" in body
    # ISO формат
    from datetime import datetime
    datetime.fromisoformat(body["from"])
    datetime.fromisoformat(body["to"])


@pytest.mark.asyncio
async def test_sources_overview_recent_payments_truncated_to_5(
    admin_client, make_committed, clean_db,
):
    """recent_payments — максимум 5 элементов."""
    product = await make_committed.product()
    for _ in range(7):
        await make_committed.payment(product=product)
    r = await admin_client.get("/api/stats/overview")
    body = r.json()
    assert len(body["recent_payments"]) == 5
