"""API-тесты /api/funnels, /api/funnel-entries, /api/funnel-steps."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_list_funnels_empty(admin_client, clean_db):
    r = await admin_client.get("/api/funnels")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_list_funnels_requires_auth(api_client):
    r = await api_client.get("/api/funnels")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_create_funnel_with_steps(admin_client, make_committed, clean_db):
    product = await make_committed.product()
    r = await admin_client.post(
        "/api/funnels",
        json={
            "name": "My Funnel",
            "product_id": product.id,
            "ttl_days": 30,
            "cancel_on_payment": True,
            "steps": [
                {"order_idx": 0, "delay_minutes": 0, "message_text": "Hello"},
                {"order_idx": 1, "delay_minutes": 60, "message_text": "Day later"},
            ],
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "My Funnel"
    assert body["ttl_days"] == 30
    assert body["steps_count"] == 2
    assert len(body["steps"]) == 2


@pytest.mark.asyncio
async def test_create_funnel_unknown_product_400(admin_client, clean_db):
    r = await admin_client.post(
        "/api/funnels",
        json={"name": "X", "product_id": 99999, "steps": []},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_get_funnel(admin_client, make_committed, clean_db):
    funnel = await make_committed.funnel(name="Detail test")
    r = await admin_client.get(f"/api/funnels/{funnel.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Detail test"


@pytest.mark.asyncio
async def test_get_funnel_unknown_404(admin_client, clean_db):
    r = await admin_client.get("/api/funnels/99999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_patch_funnel(admin_client, make_committed, clean_db):
    funnel = await make_committed.funnel(name="Old")
    r = await admin_client.patch(
        f"/api/funnels/{funnel.id}",
        json={"name": "New", "is_active": False, "ttl_days": 14},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "New"
    assert body["is_active"] is False
    assert body["ttl_days"] == 14


@pytest.mark.asyncio
async def test_delete_funnel(admin_client, make_committed, clean_db):
    funnel = await make_committed.funnel()
    r = await admin_client.delete(f"/api/funnels/{funnel.id}")
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_delete_funnel_with_active_entries_409(admin_client, make_committed, clean_db):
    funnel = await make_committed.funnel()
    await make_committed.funnel_entry(funnel=funnel, status="active")

    r = await admin_client.delete(f"/api/funnels/{funnel.id}")
    assert r.status_code == 409
    assert "активн" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_add_step(admin_client, make_committed, clean_db):
    funnel = await make_committed.funnel()
    r = await admin_client.post(
        f"/api/funnels/{funnel.id}/steps",
        json={
            "order_idx": 0, "delay_minutes": 30,
            "message_text": "New step",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["funnel_id"] == funnel.id
    assert body["delay_minutes"] == 30


@pytest.mark.asyncio
async def test_reorder_steps(admin_client, make_committed, clean_db):
    funnel = await make_committed.funnel()
    s1 = await make_committed.funnel_step(funnel=funnel, order_idx=0, message_text="A")
    s2 = await make_committed.funnel_step(funnel=funnel, order_idx=1, message_text="B")
    s3 = await make_committed.funnel_step(funnel=funnel, order_idx=2, message_text="C")

    r = await admin_client.post(
        f"/api/funnels/{funnel.id}/reorder",
        json={"ordered_step_ids": [s3.id, s1.id, s2.id]},
    )
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_update_step(admin_client, make_committed, clean_db):
    funnel = await make_committed.funnel()
    step = await make_committed.funnel_step(funnel=funnel, message_text="Old text")

    r = await admin_client.patch(
        f"/api/funnel-steps/{step.id}",
        json={
            "order_idx": 0, "delay_minutes": 120,
            "message_text": "Updated", "is_active": False,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["message_text"] == "Updated"
    assert body["delay_minutes"] == 120


@pytest.mark.asyncio
async def test_delete_step(admin_client, make_committed, clean_db):
    funnel = await make_committed.funnel()
    step = await make_committed.funnel_step(funnel=funnel)
    r = await admin_client.delete(f"/api/funnel-steps/{step.id}")
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_list_entries(admin_client, make_committed, clean_db):
    funnel = await make_committed.funnel()
    user = await make_committed.user(first_name="Test", username="tu")
    entry = await make_committed.funnel_entry(funnel=funnel, user=user, status="active")
    r = await admin_client.get(f"/api/funnels/{funnel.id}/entries")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["user_first_name"] == "Test"


@pytest.mark.asyncio
async def test_list_entries_status_filter(admin_client, make_committed, clean_db):
    funnel = await make_committed.funnel()
    await make_committed.funnel_entry(funnel=funnel, status="active")
    await make_committed.funnel_entry(funnel=funnel, status="completed")
    r = await admin_client.get(f"/api/funnels/{funnel.id}/entries?status=active")
    assert len(r.json()) == 1


@pytest.mark.asyncio
async def test_cancel_entry(admin_client, make_committed, engine, clean_db):
    entry = await make_committed.funnel_entry(status="active")
    r = await admin_client.post(f"/api/funnel-entries/{entry.id}/cancel")
    assert r.status_code == 204

    from sqlalchemy import text
    async with engine.connect() as conn:
        status = (
            await conn.execute(
                text("SELECT status FROM funnel_entries WHERE id=:id"), {"id": entry.id}
            )
        ).scalar_one()
    assert status == "cancelled"


@pytest.mark.asyncio
async def test_cancel_unknown_entry_404(admin_client, clean_db):
    r = await admin_client.post("/api/funnel-entries/99999/cancel")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_funnels_includes_steps_count(admin_client, make_committed, clean_db):
    funnel = await make_committed.funnel(name="Has steps")
    await make_committed.funnel_step(funnel=funnel)
    await make_committed.funnel_step(funnel=funnel, order_idx=1)
    r = await admin_client.get("/api/funnels")
    assert r.json()[0]["steps_count"] == 2


@pytest.mark.asyncio
async def test_list_funnels_filter_by_product(admin_client, make_committed, clean_db):
    p1 = await make_committed.product()
    p2 = await make_committed.product()
    await make_committed.funnel(product=p1, name="F1")
    await make_committed.funnel(product=p2, name="F2")
    r = await admin_client.get(f"/api/funnels?product_id={p1.id}")
    body = r.json()
    assert len(body) == 1
    assert body[0]["name"] == "F1"
