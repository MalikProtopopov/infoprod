"""API: PATCH /api/leads/{id} — фиксация status timestamps."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_patch_lead_status_to_contacted_sets_contacted_at(admin_client, make_committed, engine, clean_db):
    lead = await make_committed.lead(status="new")

    r = await admin_client.patch(f"/api/leads/{lead.id}", json={"status": "contacted"})
    assert r.status_code == 200
    assert r.json()["status"] == "contacted"

    from sqlalchemy import text
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text("SELECT contacted_at, paid_at, closed_at FROM leads WHERE id=:id"),
                {"id": lead.id},
            )
        ).first()
    assert row[0] is not None
    assert row[1] is None
    assert row[2] is None


@pytest.mark.asyncio
async def test_patch_lead_to_paid_sets_paid_at(admin_client, make_committed, engine, clean_db):
    lead = await make_committed.lead(status="contacted")
    await admin_client.patch(f"/api/leads/{lead.id}", json={"status": "paid"})

    from sqlalchemy import text
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text("SELECT paid_at, closed_at FROM leads WHERE id=:id"),
                {"id": lead.id},
            )
        ).first()
    assert row[0] is not None
    assert row[1] is None


@pytest.mark.asyncio
async def test_patch_lead_does_not_overwrite_existing_timestamps(admin_client, make_committed, engine, clean_db):
    """Регрессия: повторный PATCH в тот же статус не должен сбивать timestamp."""
    from datetime import datetime, timezone
    from sqlalchemy import text

    old_ts = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    lead = await make_committed.lead(status="contacted")
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE leads SET contacted_at = :t WHERE id = :id"),
            {"t": old_ts, "id": lead.id},
        )

    r = await admin_client.patch(f"/api/leads/{lead.id}", json={"status": "contacted"})
    assert r.status_code == 200

    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text("SELECT contacted_at FROM leads WHERE id=:id"),
                {"id": lead.id},
            )
        ).first()
    contacted_at = row[0]
    if contacted_at.tzinfo is None:
        contacted_at = contacted_at.replace(tzinfo=timezone.utc)
    assert contacted_at == old_ts


@pytest.mark.asyncio
async def test_patch_invalid_status_returns_422(admin_client, make_committed, clean_db):
    lead = await make_committed.lead()
    r = await admin_client.patch(f"/api/leads/{lead.id}", json={"status": "garbage"})
    assert r.status_code == 422
