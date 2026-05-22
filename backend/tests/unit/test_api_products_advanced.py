"""Дополнительные тесты /api/products: code collision на patch, cover_url, description."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_patch_product_change_code_to_unused(admin_client, make_committed, clean_db):
    """Свободный код можно поставить."""
    product = await make_committed.product(code="old_code")
    r = await admin_client.patch(f"/api/products/{product.id}", json={"code": "new_code"})
    assert r.status_code == 200
    assert r.json()["code"] == "new_code"


@pytest.mark.asyncio
async def test_patch_product_change_code_to_existing_409(admin_client, make_committed, clean_db):
    await make_committed.product(code="taken1")
    p2 = await make_committed.product()
    r = await admin_client.patch(f"/api/products/{p2.id}", json={"code": "taken1"})
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_patch_product_change_code_collides_with_slug(
    admin_client, make_committed, clean_db,
):
    product = await make_committed.product()
    await make_committed.tracking_link(slug="trackslg", product=product)
    p2 = await make_committed.product()
    r = await admin_client.patch(f"/api/products/{p2.id}", json={"code": "trackslg"})
    assert r.status_code == 409
    assert "slug" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_patch_product_change_channel(admin_client, make_committed, clean_db):
    ch1 = await make_committed.channel()
    ch2 = await make_committed.channel()
    product = await make_committed.product(channel=ch1)
    r = await admin_client.patch(
        f"/api/products/{product.id}", json={"channel_id": ch2.id},
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_patch_product_description_and_cover(admin_client, make_committed, clean_db):
    product = await make_committed.product()
    r = await admin_client.patch(
        f"/api/products/{product.id}",
        json={
            "description": "Updated description",
            "cover_url": "https://example.com/cover.jpg",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["description"] == "Updated description"
    assert body["cover_url"] == "https://example.com/cover.jpg"


@pytest.mark.asyncio
async def test_patch_product_is_active_toggle(admin_client, make_committed, clean_db):
    product = await make_committed.product(is_active=True)
    r = await admin_client.patch(f"/api/products/{product.id}", json={"is_active": False})
    assert r.status_code == 200
    assert r.json()["is_active"] is False


@pytest.mark.asyncio
async def test_patch_unknown_product_404(admin_client, clean_db):
    r = await admin_client.patch("/api/products/99999", json={"name": "X"})
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_products_requires_auth(api_client):
    r = await api_client.get("/api/products")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_get_product_requires_auth(api_client):
    r = await api_client.get("/api/products/1")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_list_products_returns_channel_title(admin_client, make_committed, clean_db):
    channel = await make_committed.channel(title="My Channel")
    await make_committed.product(channel=channel, name="P1")
    r = await admin_client.get("/api/products")
    body = r.json()
    assert body[0]["channel_title"] == "My Channel"


@pytest.mark.asyncio
async def test_patch_product_with_empty_payload(admin_client, make_committed, clean_db):
    """Пустой PATCH — 200, ничего не меняет."""
    product = await make_committed.product(name="Stay same")
    r = await admin_client.patch(f"/api/products/{product.id}", json={})
    assert r.status_code == 200
    assert r.json()["name"] == "Stay same"


@pytest.mark.asyncio
async def test_create_product_decimal_string_prices(admin_client, make_committed, clean_db):
    """Цены могут быть строкой с десятичным разделителем."""
    channel = await make_committed.channel()
    r = await admin_client.post(
        "/api/products",
        json={
            "code": "decimal1", "name": "X", "channel_id": channel.id,
            "price_3m": "999.50", "price_6m": "1799.00", "price_12m": "2999.99",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["price_3m"] == "999.50"
    assert body["price_12m"] == "2999.99"
