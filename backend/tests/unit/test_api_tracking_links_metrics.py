"""Тесты на батч-метрики /api/tracking-links list, патч edge cases."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_list_returns_batch_metrics_per_link(admin_client, make_committed, engine, clean_db):
    """list endpoint в один запрос аггрегирует metrics по всем ссылкам."""
    product = await make_committed.product()
    link1 = await make_committed.tracking_link(
        product=product, slug="metric01", click_count=10, unique_users=8,
    )
    link2 = await make_committed.tracking_link(
        product=product, slug="metric02", click_count=20, unique_users=15,
    )
    user = await make_committed.user()

    from sqlalchemy import text
    async with engine.begin() as conn:
        # link1: 2 leads, 1 payment 500
        await conn.execute(
            text(
                "INSERT INTO leads (user_id, product_id, status, tracking_link_id, created_at) "
                "VALUES (:u, :p, 'new', :l, NOW()), (:u, :p, 'paid', :l, NOW())"
            ),
            {"u": user.id, "p": product.id, "l": link1.id},
        )
        await conn.execute(
            text(
                "INSERT INTO payments (user_id, product_id, period_months, amount, "
                "currency, tracking_link_id, created_at) "
                "VALUES (:u, :p, 3, 500, 'RUB', :l, NOW())"
            ),
            {"u": user.id, "p": product.id, "l": link1.id},
        )
        # link2: 1 lead
        await conn.execute(
            text(
                "INSERT INTO leads (user_id, product_id, status, tracking_link_id, created_at) "
                "VALUES (:u, :p, 'new', :l, NOW())"
            ),
            {"u": user.id, "p": product.id, "l": link2.id},
        )

    r = await admin_client.get(f"/api/tracking-links?product_id={product.id}")
    body = r.json()
    by_slug = {row["slug"]: row for row in body}
    assert by_slug["metric01"]["leads_count"] == 2
    assert by_slug["metric01"]["payments_count"] == 1
    assert by_slug["metric01"]["revenue"] == "500.00"
    assert by_slug["metric02"]["leads_count"] == 1
    assert by_slug["metric02"]["payments_count"] == 0
    assert by_slug["metric02"]["revenue"] == "0"


@pytest.mark.asyncio
async def test_patch_link_reactivate(admin_client, make_committed, clean_db):
    """PATCH is_active: false → true."""
    link = await make_committed.tracking_link(is_active=False)
    r = await admin_client.patch(
        f"/api/tracking-links/{link.id}", json={"is_active": True},
    )
    assert r.status_code == 200
    assert r.json()["is_active"] is True


@pytest.mark.asyncio
async def test_patch_unknown_link_404(admin_client, clean_db):
    r = await admin_client.patch("/api/tracking-links/99999", json={"notes": "x"})
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_unknown_link_404(admin_client, clean_db):
    r = await admin_client.delete("/api/tracking-links/99999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_empty_returns_empty_array(admin_client, clean_db):
    r = await admin_client.get("/api/tracking-links?product_id=99999")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_create_with_utm_content(admin_client, make_committed, clean_db):
    product = await make_committed.product()
    r = await admin_client.post(
        "/api/tracking-links",
        json={
            "product_id": product.id, "utm_source": "ig",
            "utm_content": "story_v1",
        },
    )
    assert r.status_code == 201
    assert r.json()["utm_content"] == "story_v1"


@pytest.mark.asyncio
async def test_link_url_uses_bot_username_when_set(admin_client, make_committed, clean_db):
    bot = await make_committed.bot(username="mainbot")
    product = await make_committed.product()
    link = await make_committed.tracking_link(product=product, bot_id=bot.id, slug="urlt0001")

    r = await admin_client.get(f"/api/tracking-links/{link.id}")
    body = r.json()
    assert body["url"] == "https://t.me/mainbot?start=urlt0001"


@pytest.mark.asyncio
async def test_link_url_underscore_when_no_bot(admin_client, make_committed, clean_db):
    """Без bot_id — url с placeholder '_'."""
    product = await make_committed.product()
    link = await make_committed.tracking_link(product=product, bot_id=None, slug="urlt0002")

    r = await admin_client.get(f"/api/tracking-links/{link.id}")
    body = r.json()
    assert body["url"] == "https://t.me/_?start=urlt0002"
