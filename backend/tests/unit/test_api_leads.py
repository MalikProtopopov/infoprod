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
async def test_patch_lead_to_paid_requires_payment(admin_client, make_committed, clean_db):
    """paid без привязанного платежа → 422 (жёсткое требование)."""
    lead = await make_committed.lead(status="contacted")
    r = await admin_client.patch(f"/api/leads/{lead.id}", json={"status": "paid"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_patch_lead_to_paid_links_payment_and_sets_paid_at(admin_client, make_committed, engine, clean_db):
    lead = await make_committed.lead(status="contacted")
    payment = await make_committed.payment(user_id=lead.user_id, product_id=lead.product_id)

    r = await admin_client.patch(
        f"/api/leads/{lead.id}", json={"status": "paid", "payment_id": payment.id}
    )
    assert r.status_code == 200
    assert r.json()["payment_id"] == payment.id

    from sqlalchemy import text
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text("SELECT payment_id, paid_at, closed_at FROM leads WHERE id=:id"),
                {"id": lead.id},
            )
        ).first()
    assert row[0] == payment.id
    assert row[1] is not None
    assert row[2] is None


@pytest.mark.asyncio
async def test_patch_lead_paid_rejects_foreign_payment(admin_client, make_committed, clean_db):
    """Платёж другого пользователя нельзя привязать → 422."""
    lead = await make_committed.lead(status="contacted")
    other_payment = await make_committed.payment()  # свой user/product
    r = await admin_client.patch(
        f"/api/leads/{lead.id}", json={"status": "paid", "payment_id": other_payment.id}
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_patch_lead_closed_requires_payment(admin_client, make_committed, clean_db):
    lead = await make_committed.lead(status="contacted")
    assert (await admin_client.patch(f"/api/leads/{lead.id}", json={"status": "closed"})).status_code == 422
    payment = await make_committed.payment(user_id=lead.user_id, product_id=lead.product_id)
    r = await admin_client.patch(
        f"/api/leads/{lead.id}", json={"status": "closed", "payment_id": payment.id}
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_patch_lead_cancelled_requires_reason(admin_client, make_committed, engine, clean_db):
    lead = await make_committed.lead(status="new")
    # без причины → 422
    assert (await admin_client.patch(f"/api/leads/{lead.id}", json={"status": "cancelled"})).status_code == 422
    # с причиной → 200, причина + cancelled_at сохранены
    r = await admin_client.patch(
        f"/api/leads/{lead.id}", json={"status": "cancelled", "cancel_reason": "Дорого"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "cancelled"
    assert body["cancel_reason"] == "Дорого"
    assert body["cancelled_at"] is not None


@pytest.mark.asyncio
async def test_cancel_reasons_summary(admin_client, make_committed, clean_db):
    for reason in ["Дорого", "Дорого", "Нет денег сейчас"]:
        lead = await make_committed.lead(status="new")
        await admin_client.patch(
            f"/api/leads/{lead.id}", json={"status": "cancelled", "cancel_reason": reason}
        )
    r = await admin_client.get("/api/leads/cancel-reasons")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 3
    assert data["breakdown"][0] == {"reason": "Дорого", "count": 2}
    assert "Дорого" in data["presets"]


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
