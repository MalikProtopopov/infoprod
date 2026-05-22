"""API: CRUD /api/products + коллизия с tracking_link.slug."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_list_products_empty(admin_client, clean_db):
    r = await admin_client.get("/api/products")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_create_product_minimal(admin_client, make_committed, clean_db):
    channel = await make_committed.channel()
    r = await admin_client.post(
        "/api/products",
        json={
            "code": "newprod",
            "name": "New Product",
            "channel_id": channel.id,
            "price_3m": "1000",
            "price_6m": "1800",
            "price_12m": "3000",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["code"] == "newprod"
    assert body["name"] == "New Product"
    assert body["is_active"] is True
    assert body["currency"] == "RUB"


@pytest.mark.asyncio
async def test_create_product_with_invalid_code_returns_422(admin_client, make_committed, clean_db):
    channel = await make_committed.channel()
    r = await admin_client.post(
        "/api/products",
        json={
            "code": "with space",
            "name": "x",
            "channel_id": channel.id,
            "price_3m": "0",
            "price_6m": "0",
            "price_12m": "0",
        },
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_product_negative_price_returns_422(admin_client, make_committed, clean_db):
    channel = await make_committed.channel()
    r = await admin_client.post(
        "/api/products",
        json={
            "code": "neg1",
            "name": "x",
            "channel_id": channel.id,
            "price_3m": "-1",
            "price_6m": "0",
            "price_12m": "0",
        },
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_product_unknown_channel_returns_400(admin_client, clean_db):
    r = await admin_client.post(
        "/api/products",
        json={
            "code": "x", "name": "x", "channel_id": 99999,
            "price_3m": "0", "price_6m": "0", "price_12m": "0",
        },
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_create_product_duplicate_code_returns_409(admin_client, make_committed, clean_db):
    channel = await make_committed.channel()
    await make_committed.product(code="dup1", channel=channel)
    r = await admin_client.post(
        "/api/products",
        json={
            "code": "dup1", "name": "Other", "channel_id": channel.id,
            "price_3m": "0", "price_6m": "0", "price_12m": "0",
        },
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_create_product_code_collides_with_tracking_slug(admin_client, make_committed, clean_db):
    """Регрессия: product.code не должен совпадать с существующим tracking_link.slug."""
    product = await make_committed.product()
    await make_committed.tracking_link(slug="myslug12", product=product)

    other_channel = await make_committed.channel()
    r = await admin_client.post(
        "/api/products",
        json={
            "code": "myslug12", "name": "Y", "channel_id": other_channel.id,
            "price_3m": "0", "price_6m": "0", "price_12m": "0",
        },
    )
    assert r.status_code == 409
    assert "slug" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_product_returns_full_card(admin_client, make_committed, clean_db):
    product = await make_committed.product(code="ggg", name="GetProduct")
    r = await admin_client.get(f"/api/products/{product.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == "ggg"
    assert body["name"] == "GetProduct"
    assert body["channel_title"] is not None


@pytest.mark.asyncio
async def test_get_unknown_product_returns_404(admin_client, clean_db):
    r = await admin_client.get("/api/products/99999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_patch_product(admin_client, make_committed, clean_db):
    product = await make_committed.product(name="Old", price_3m=1000)
    r = await admin_client.patch(
        f"/api/products/{product.id}",
        json={"name": "Renamed", "price_3m": "2000"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Renamed"
    assert body["price_3m"] == "2000.00"


@pytest.mark.asyncio
async def test_patch_product_with_unknown_channel_400(admin_client, make_committed, clean_db):
    product = await make_committed.product()
    r = await admin_client.patch(
        f"/api/products/{product.id}",
        json={"channel_id": 99999},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_delete_product(admin_client, make_committed, clean_db):
    product = await make_committed.product()
    r = await admin_client.delete(f"/api/products/{product.id}")
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_delete_unknown_product_404(admin_client, clean_db):
    r = await admin_client.delete("/api/products/99999")
    assert r.status_code == 404
