"""Расширенные тесты /api/tracking-links: list filters, GET by id, hard delete, leads/payments metrics."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_list_with_product_id_filter(admin_client, make_committed, clean_db):
    p1 = await make_committed.product()
    p2 = await make_committed.product()
    await make_committed.tracking_link(product=p1, utm_source="ig")
    await make_committed.tracking_link(product=p2, utm_source="yt")

    r = await admin_client.get(f"/api/tracking-links?product_id={p1.id}")
    body = r.json()
    assert len(body) == 1
    assert body[0]["utm_source"] == "ig"


@pytest.mark.asyncio
async def test_list_with_is_active_filter(admin_client, make_committed, clean_db):
    product = await make_committed.product()
    await make_committed.tracking_link(product=product, is_active=True)
    await make_committed.tracking_link(product=product, is_active=False)

    r = await admin_client.get("/api/tracking-links?is_active=true")
    assert len(r.json()) == 1
    r = await admin_client.get("/api/tracking-links?is_active=false")
    assert len(r.json()) == 1


@pytest.mark.asyncio
async def test_list_with_pagination(admin_client, make_committed, clean_db):
    product = await make_committed.product()
    for _ in range(5):
        await make_committed.tracking_link(product=product)
    r = await admin_client.get("/api/tracking-links?limit=2&offset=1")
    assert len(r.json()) == 2


@pytest.mark.asyncio
async def test_get_by_id_includes_metrics(admin_client, make_committed, engine, clean_db):
    product = await make_committed.product()
    link = await make_committed.tracking_link(
        product=product, click_count=10, unique_users=7,
    )
    user = await make_committed.user()
    # Создаём лид и платёж с tracking_link_id для проверки счётчиков
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO leads (user_id, product_id, status, tracking_link_id, created_at) "
                "VALUES (:u, :p, 'paid', :l, NOW())"
            ),
            {"u": user.id, "p": product.id, "l": link.id},
        )
        await conn.execute(
            text(
                "INSERT INTO payments (user_id, product_id, period_months, amount, "
                "currency, tracking_link_id, created_at) "
                "VALUES (:u, :p, 3, 999, 'RUB', :l, NOW())"
            ),
            {"u": user.id, "p": product.id, "l": link.id},
        )

    r = await admin_client.get(f"/api/tracking-links/{link.id}")
    body = r.json()
    assert body["click_count"] == 10
    assert body["unique_users"] == 7
    assert body["leads_count"] == 1
    assert body["payments_count"] == 1
    assert body["revenue"] == "999.00"


@pytest.mark.asyncio
async def test_get_unknown_id_404(admin_client, clean_db):
    r = await admin_client.get("/api/tracking-links/99999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_create_with_bot_id(admin_client, make_committed, clean_db):
    bot = await make_committed.bot()
    product = await make_committed.product()
    r = await admin_client.post(
        "/api/tracking-links",
        json={"product_id": product.id, "utm_source": "ig", "bot_id": bot.id},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["bot"]["id"] == bot.id


@pytest.mark.asyncio
async def test_create_with_unknown_bot_400(admin_client, make_committed, clean_db):
    product = await make_committed.product()
    r = await admin_client.post(
        "/api/tracking-links",
        json={"product_id": product.id, "utm_source": "ig", "bot_id": 99999},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_hard_delete_unused_link(admin_client, make_committed, engine, clean_db):
    link = await make_committed.tracking_link()
    r = await admin_client.delete(f"/api/tracking-links/{link.id}?hard=true")
    assert r.status_code == 204

    # Запись физически удалена — GET вернёт 404
    r = await admin_client.get(f"/api/tracking-links/{link.id}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_hard_delete_blocked_when_has_leads_409(admin_client, make_committed, engine, clean_db):
    product = await make_committed.product()
    link = await make_committed.tracking_link(product=product)
    user = await make_committed.user()
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO leads (user_id, product_id, status, tracking_link_id, created_at) "
                "VALUES (:u, :p, 'new', :l, NOW())"
            ),
            {"u": user.id, "p": product.id, "l": link.id},
        )

    r = await admin_client.delete(f"/api/tracking-links/{link.id}?hard=true")
    assert r.status_code == 409
    assert "заявок" in r.json()["detail"]


@pytest.mark.asyncio
async def test_qr_png_with_bot_uses_username(admin_client, make_committed, clean_db):
    bot = await make_committed.bot(username="bottest")
    product = await make_committed.product()
    link = await make_committed.tracking_link(product=product, bot_id=bot.id)

    r = await admin_client.get(f"/api/tracking-links/{link.id}/qr.png")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"


@pytest.mark.asyncio
async def test_qr_unknown_link_returns_404(admin_client, clean_db):
    r = await admin_client.get("/api/tracking-links/99999/qr.png")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_create_link_without_auth(api_client):
    r = await api_client.post("/api/tracking-links", json={"product_id": 1, "utm_source": "ig"})
    assert r.status_code == 401
