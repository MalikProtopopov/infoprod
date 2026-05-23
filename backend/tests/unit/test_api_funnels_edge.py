"""Edge cases для /api/funnels — add_step с unknown funnel, reorder с пустым списком."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_add_step_to_unknown_funnel_404(admin_client, clean_db):
    r = await admin_client.post(
        "/api/funnels/99999/steps",
        json={"order_idx": 0, "delay_minutes": 0, "message_text": "x"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_reorder_unknown_funnel_404(admin_client, clean_db):
    r = await admin_client.post(
        "/api/funnels/99999/reorder",
        json={"ordered_step_ids": []},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_update_unknown_step_404(admin_client, clean_db):
    r = await admin_client.patch(
        "/api/funnel-steps/99999",
        json={"order_idx": 0, "delay_minutes": 0, "message_text": "x"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_unknown_step_404(admin_client, clean_db):
    r = await admin_client.delete("/api/funnel-steps/99999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_funnels_filter_is_active(admin_client, make_committed, clean_db):
    await make_committed.funnel(is_active=True)
    await make_committed.funnel(is_active=False)
    r = await admin_client.get("/api/funnels?is_active=true")
    assert len(r.json()) == 1


@pytest.mark.asyncio
async def test_create_funnel_with_invalid_ttl_422(admin_client, make_committed, clean_db):
    product = await make_committed.product()
    r = await admin_client.post(
        "/api/funnels",
        json={"name": "X", "product_id": product.id, "ttl_days": 0, "steps": []},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_get_funnel_includes_steps_array(admin_client, make_committed, clean_db):
    funnel = await make_committed.funnel()
    await make_committed.funnel_step(funnel=funnel)
    r = await admin_client.get(f"/api/funnels/{funnel.id}")
    body = r.json()
    assert "steps" in body
    assert len(body["steps"]) == 1


@pytest.mark.asyncio
async def test_list_entries_returns_user_data(admin_client, make_committed, clean_db):
    user = await make_committed.user(first_name="Test", username="tu")
    funnel = await make_committed.funnel()
    await make_committed.funnel_entry(user=user, funnel=funnel, status="active")
    r = await admin_client.get(f"/api/funnels/{funnel.id}/entries")
    body = r.json()
    assert body[0]["user_first_name"] == "Test"
    assert body[0]["user_username"] == "tu"


@pytest.mark.asyncio
async def test_cancel_already_cancelled_entry_404(admin_client, make_committed, clean_db):
    entry = await make_committed.funnel_entry(status="cancelled")
    r = await admin_client.post(f"/api/funnel-entries/{entry.id}/cancel")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_entries_with_status_filter_completed(admin_client, make_committed, clean_db):
    funnel = await make_committed.funnel()
    await make_committed.funnel_entry(funnel=funnel, status="active")
    await make_committed.funnel_entry(funnel=funnel, status="completed")
    r = await admin_client.get(f"/api/funnels/{funnel.id}/entries?status=completed")
    assert len(r.json()) == 1
