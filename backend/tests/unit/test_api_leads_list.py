"""GET /api/leads — список + фильтр по status + пагинация + GET /{id}."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_list_leads_empty(admin_client, clean_db):
    r = await admin_client.get("/api/leads")
    body = r.json()
    assert body == {"total": 0, "items": []}


@pytest.mark.asyncio
async def test_list_leads_returns_items(admin_client, make_committed, clean_db):
    product = await make_committed.product()
    user = await make_committed.user()
    await make_committed.lead(user=user, product=product, status="new")
    await make_committed.lead(user=user, product=product, status="paid")

    r = await admin_client.get("/api/leads")
    body = r.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2


@pytest.mark.asyncio
async def test_list_leads_status_filter(admin_client, make_committed, clean_db):
    product = await make_committed.product()
    user = await make_committed.user()
    await make_committed.lead(user=user, product=product, status="new")
    await make_committed.lead(user=user, product=product, status="paid")
    await make_committed.lead(user=user, product=product, status="contacted")

    for st in ["new", "paid", "contacted"]:
        r = await admin_client.get(f"/api/leads?status={st}")
        assert r.json()["total"] == 1

    r = await admin_client.get("/api/leads?status=all")
    assert r.json()["total"] == 3


@pytest.mark.asyncio
async def test_list_leads_pagination(admin_client, make_committed, clean_db):
    product = await make_committed.product()
    user = await make_committed.user()
    for _ in range(5):
        await make_committed.lead(user=user, product=product)
    r = await admin_client.get("/api/leads?limit=2&offset=1")
    body = r.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2


@pytest.mark.asyncio
async def test_get_lead_by_id(admin_client, make_committed, clean_db):
    product = await make_committed.product()
    user = await make_committed.user(first_name="Alice")
    lead = await make_committed.lead(user=user, product=product, status="new")

    r = await admin_client.get(f"/api/leads/{lead.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == lead.id
    assert body["user_first_name"] == "Alice"
    assert body["status"] == "new"


@pytest.mark.asyncio
async def test_get_unknown_lead_404(admin_client, clean_db):
    r = await admin_client.get("/api/leads/99999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_lead(admin_client, make_committed, clean_db):
    product = await make_committed.product()
    user = await make_committed.user()
    lead = await make_committed.lead(user=user, product=product)

    r = await admin_client.delete(f"/api/leads/{lead.id}")
    assert r.status_code == 204

    r = await admin_client.get(f"/api/leads/{lead.id}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_unknown_lead_404(admin_client, clean_db):
    r = await admin_client.delete("/api/leads/99999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_requires_auth(api_client):
    r = await api_client.get("/api/leads")
    assert r.status_code == 401
