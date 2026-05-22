"""API-тесты CRUD /api/tracking-links.

Используем `make_committed` для подготовки данных — он коммитит в отдельной
транзакции, чтобы данные были видны через admin_client.
"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_list_empty_when_no_links(admin_client, clean_db):
    r = await admin_client.get("/api/tracking-links")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_list_requires_auth(api_client):
    r = await api_client.get("/api/tracking-links")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_create_link_with_minimal_payload(admin_client, make_committed, clean_db):
    product = await make_committed.product()
    r = await admin_client.post(
        "/api/tracking-links",
        json={"product_id": product.id, "utm_source": "instagram"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["utm_source"] == "instagram"
    assert len(body["slug"]) == 8
    assert body["click_count"] == 0
    assert body["product"]["id"] == product.id


@pytest.mark.asyncio
async def test_create_link_full_payload(admin_client, make_committed, clean_db):
    product = await make_committed.product()
    r = await admin_client.post(
        "/api/tracking-links",
        json={
            "product_id": product.id,
            "utm_source": "youtube",
            "utm_medium": "video",
            "utm_campaign": "spring_2026",
            "notes": "test campaign",
            "custom_slug": "myslug12",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["slug"] == "myslug12"
    assert body["utm_medium"] == "video"
    assert body["utm_campaign"] == "spring_2026"
    assert body["notes"] == "test campaign"


@pytest.mark.asyncio
async def test_create_link_invalid_slug_returns_422(admin_client, make_committed, clean_db):
    product = await make_committed.product()
    r = await admin_client.post(
        "/api/tracking-links",
        json={"product_id": product.id, "utm_source": "ig", "custom_slug": "ab"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_link_collision_returns_409(admin_client, make_committed, clean_db):
    product = await make_committed.product()
    await make_committed.tracking_link(slug="taken123", product=product)
    r = await admin_client.post(
        "/api/tracking-links",
        json={"product_id": product.id, "utm_source": "ig", "custom_slug": "taken123"},
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_create_link_unknown_product_returns_400(admin_client, clean_db):
    r = await admin_client.post(
        "/api/tracking-links",
        json={"product_id": 99999, "utm_source": "ig"},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_patch_link_updates_notes_and_is_active(admin_client, make_committed, clean_db):
    link = await make_committed.tracking_link()
    r = await admin_client.patch(
        f"/api/tracking-links/{link.id}",
        json={"notes": "updated note", "is_active": False},
    )
    assert r.status_code == 200
    assert r.json()["notes"] == "updated note"
    assert r.json()["is_active"] is False


@pytest.mark.asyncio
async def test_delete_link_soft_when_has_no_relations(admin_client, make_committed, clean_db):
    link = await make_committed.tracking_link()
    r = await admin_client.delete(f"/api/tracking-links/{link.id}")
    assert r.status_code == 204
    r = await admin_client.get(f"/api/tracking-links/{link.id}")
    assert r.status_code == 200
    assert r.json()["is_active"] is False


@pytest.mark.asyncio
async def test_qr_png_returns_image(admin_client, make_committed, clean_db):
    link = await make_committed.tracking_link()
    r = await admin_client.get(f"/api/tracking-links/{link.id}/qr.png")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert len(r.content) > 200
