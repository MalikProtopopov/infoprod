"""Тесты для UX-endpoints: entry-points aggregate, test-run, feature-requests."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_entry_points_empty(admin_client, make_committed, clean_db):
    funnel = await make_committed.funnel()
    r = await admin_client.get(f"/api/funnels/{funnel.id}/entry-points")
    assert r.status_code == 200
    body = r.json()
    assert body["funnel_id"] == funnel.id
    assert body["tracking_links"] == []
    assert body["triggers"] == []
    assert body["is_product_default"] is False
    assert body["has_any"] is False


@pytest.mark.asyncio
async def test_entry_points_with_link_and_trigger(admin_client, make_committed, clean_db):
    funnel = await make_committed.funnel()
    await make_committed.tracking_link(
        product_id=funnel.product_id, funnel_id=funnel.id,
        utm_source="ig", slug="testlink",
    )
    await make_committed.funnel_trigger(funnel=funnel, word="клуб")
    r = await admin_client.get(f"/api/funnels/{funnel.id}/entry-points")
    body = r.json()
    assert len(body["tracking_links"]) == 1
    assert len(body["triggers"]) == 1
    assert body["has_any"] is True


@pytest.mark.asyncio
async def test_entry_points_with_default_funnel(admin_client, make_committed, engine, clean_db):
    funnel = await make_committed.funnel()
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE products SET default_funnel_id=:f WHERE id=:p"),
            {"f": funnel.id, "p": funnel.product_id},
        )
    r = await admin_client.get(f"/api/funnels/{funnel.id}/entry-points")
    body = r.json()
    assert body["is_product_default"] is True
    assert body["has_any"] is True


@pytest.mark.asyncio
async def test_entry_points_unknown_funnel_404(admin_client, clean_db):
    r = await admin_client.get("/api/funnels/99999/entry-points")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_test_run_no_steps_422(admin_client, make_committed, clean_db):
    funnel = await make_committed.funnel()
    r = await admin_client.post(f"/api/funnels/{funnel.id}/test-run")
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_test_run_schedules_messages_x60(admin_client, make_committed, clean_db):
    funnel = await make_committed.funnel()
    await make_committed.funnel_step(funnel=funnel, order_idx=0, delay_minutes=0)
    await make_committed.funnel_step(funnel=funnel, order_idx=1, delay_minutes=60)  # = 60s в тесте
    await make_committed.funnel_step(funnel=funnel, order_idx=2, delay_minutes=1440)  # = 1440s

    r = await admin_client.post(f"/api/funnels/{funnel.id}/test-run")
    assert r.status_code == 201
    body = r.json()
    assert body["test_entry_id"] > 0
    assert body["test_user_id"] > 0
    assert body["steps_scheduled"] == 3
    assert body["speedup_factor"] == 60
    # delay_seconds = delay_minutes (но интерпретация secunds)
    assert body["schedules"][0]["delay_seconds"] == 1  # min 1 sec
    assert body["schedules"][1]["delay_seconds"] == 60
    assert body["schedules"][2]["delay_seconds"] == 1440


@pytest.mark.asyncio
async def test_test_run_status(admin_client, make_committed, clean_db):
    funnel = await make_committed.funnel()
    await make_committed.funnel_step(funnel=funnel, order_idx=0, delay_minutes=0, message_text="Hello")
    r = await admin_client.post(f"/api/funnels/{funnel.id}/test-run")
    entry_id = r.json()["test_entry_id"]

    status = await admin_client.get(f"/api/funnels/{funnel.id}/test-run/{entry_id}/status")
    assert status.status_code == 200
    body = status.json()
    assert body["entry_status"] == "active"
    assert len(body["messages"]) == 1
    assert body["messages"][0]["sent_at"] is None


@pytest.mark.asyncio
async def test_test_run_status_unknown_404(admin_client, make_committed, clean_db):
    funnel = await make_committed.funnel()
    r = await admin_client.get(f"/api/funnels/{funnel.id}/test-run/99999/status")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_feature_request_creation(admin_client, clean_db):
    r = await admin_client.post(
        "/api/feature-requests",
        json={"feature_key": "ab_testing", "context": "Хочу A/B на текст шага"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["feature_key"] == "ab_testing"


@pytest.mark.asyncio
async def test_feature_request_logged_to_audit(admin_client, clean_db):
    await admin_client.post(
        "/api/feature-requests",
        json={"feature_key": "ab_testing"},
    )
    audit = await admin_client.get("/api/audit-log?action=feature_request")
    body = audit.json()
    assert body["items"]
    assert body["items"][0]["action"] == "feature_request"


@pytest.mark.asyncio
async def test_feature_request_validation_422(admin_client, clean_db):
    r = await admin_client.post("/api/feature-requests", json={})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_feature_request_requires_auth(api_client):
    r = await api_client.post("/api/feature-requests", json={"feature_key": "x"})
    assert r.status_code == 401
