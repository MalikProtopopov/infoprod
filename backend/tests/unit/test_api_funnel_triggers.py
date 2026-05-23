"""API-тесты /api/funnel-triggers — CRUD, duplicate=409."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_list_empty(admin_client, clean_db):
    r = await admin_client.get("/api/funnel-triggers")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_create(admin_client, make_committed, clean_db):
    funnel = await make_committed.funnel()
    r = await admin_client.post(
        "/api/funnel-triggers",
        json={"word": "СТАРТ", "funnel_id": funnel.id},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["word"] == "старт"
    assert body["funnel_id"] == funnel.id


@pytest.mark.asyncio
async def test_create_duplicate_409(admin_client, make_committed, clean_db):
    funnel = await make_committed.funnel()
    r1 = await admin_client.post(
        "/api/funnel-triggers", json={"word": "dupe", "funnel_id": funnel.id},
    )
    assert r1.status_code == 201
    r2 = await admin_client.post(
        "/api/funnel-triggers", json={"word": "DUPE", "funnel_id": funnel.id},
    )
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_create_unknown_funnel_400(admin_client, clean_db):
    r = await admin_client.post(
        "/api/funnel-triggers", json={"word": "x_y_z", "funnel_id": 99999},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_create_validation_short_422(admin_client, make_committed, clean_db):
    funnel = await make_committed.funnel()
    r = await admin_client.post(
        "/api/funnel-triggers", json={"word": "a", "funnel_id": funnel.id},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_patch_trigger(admin_client, make_committed, clean_db):
    trigger = await make_committed.funnel_trigger(word="origword", is_active=True)
    r = await admin_client.patch(
        f"/api/funnel-triggers/{trigger.id}",
        json={"is_active": False},
    )
    assert r.status_code == 200
    assert r.json()["is_active"] is False


@pytest.mark.asyncio
async def test_delete_trigger(admin_client, make_committed, clean_db):
    trigger = await make_committed.funnel_trigger()
    r = await admin_client.delete(f"/api/funnel-triggers/{trigger.id}")
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_delete_unknown_404(admin_client, clean_db):
    r = await admin_client.delete("/api/funnel-triggers/99999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_includes_funnel_name(admin_client, make_committed, clean_db):
    funnel = await make_committed.funnel(name="Named funnel")
    await make_committed.funnel_trigger(funnel=funnel, word="lookmeup")
    r = await admin_client.get("/api/funnel-triggers")
    body = r.json()
    assert len(body) == 1
    assert body[0]["funnel_name"] == "Named funnel"


@pytest.mark.asyncio
async def test_requires_auth(api_client):
    r = await api_client.get("/api/funnel-triggers")
    assert r.status_code == 401
