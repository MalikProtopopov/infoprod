"""Edge cases для api/payments — все ветки create_payment."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_tg(monkeypatch):
    monkeypatch.setattr("app.bot.manager.get_aiogram_bot", lambda _: MagicMock())
    monkeypatch.setattr("app.services.subscriptions.tg.create_one_time_invite", AsyncMock(return_value="https://t.me/+x"))
    monkeypatch.setattr("app.services.subscriptions.tg.kick_user", AsyncMock(return_value=True))
    monkeypatch.setattr("app.services.subscriptions.tg.send_message_safe", AsyncMock(return_value=True))


@pytest.mark.asyncio
async def test_create_payment_inherits_tracking_link_from_open_lead(
    admin_client, make_committed, mock_tg, engine, clean_db,
):
    """tracking_link inherits только from open lead (new/contacted), не first_user_*."""
    product = await make_committed.product()
    link = await make_committed.tracking_link(product=product, utm_source="ig")
    user = await make_committed.user(first_tracking_link_id=link.id)
    lead = await make_committed.lead(user=user, product=product, status="contacted")
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE leads SET tracking_link_id=:l WHERE id=:id"),
            {"l": link.id, "id": lead.id},
        )

    r = await admin_client.post(
        "/api/payments",
        json={"user_id": user.id, "product_id": product.id, "period_months": 3},
    )
    assert r.status_code == 201
    pid = r.json()["id"]

    async with engine.connect() as conn:
        row = (await conn.execute(
            text("SELECT tracking_link_id FROM payments WHERE id=:id"), {"id": pid}
        )).first()
    assert row[0] == link.id


@pytest.mark.asyncio
async def test_create_payment_no_user_lead_no_inherit(
    admin_client, make_committed, mock_tg, engine, clean_db,
):
    """Если у юзера нет ни lead, ни first_tracking_link — payment без tracking_link."""
    user = await make_committed.user()
    product = await make_committed.product()

    r = await admin_client.post(
        "/api/payments",
        json={"user_id": user.id, "product_id": product.id, "period_months": 3},
    )
    assert r.status_code == 201
    pid = r.json()["id"]

    from sqlalchemy import text
    async with engine.connect() as conn:
        row = (await conn.execute(
            text("SELECT tracking_link_id FROM payments WHERE id=:id"), {"id": pid}
        )).first()
    assert row[0] is None


@pytest.mark.asyncio
async def test_patch_payment_unknown_404(admin_client, clean_db):
    r = await admin_client.patch("/api/payments/99999", json={"comment": "x"})
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_patch_payment_with_empty_payload(admin_client, make_committed, clean_db):
    """PATCH без полей — 200, ничего не меняет."""
    payment = await make_committed.payment(comment="original")
    r = await admin_client.patch(f"/api/payments/{payment.id}", json={})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_create_payment_when_already_paid_lead_exists(
    admin_client, make_committed, mock_tg, engine, clean_db,
):
    """paid/closed leads не должны меняться повторно."""
    user = await make_committed.user()
    product = await make_committed.product()
    old_lead = await make_committed.lead(user=user, product=product, status="paid")

    r = await admin_client.post(
        "/api/payments",
        json={"user_id": user.id, "product_id": product.id, "period_months": 3},
    )
    assert r.status_code == 201

    from sqlalchemy import text
    async with engine.connect() as conn:
        row = (await conn.execute(
            text("SELECT status FROM leads WHERE id=:id"), {"id": old_lead.id}
        )).first()
    # Не перезаписывается
    assert row[0] == "paid"


@pytest.mark.asyncio
async def test_create_payment_returns_admin_id_set(
    admin_client, make_committed, mock_tg, engine, clean_db,
):
    """Создающий админ — записывается в admin_id."""
    user = await make_committed.user()
    product = await make_committed.product()
    r = await admin_client.post(
        "/api/payments",
        json={"user_id": user.id, "product_id": product.id, "period_months": 3},
    )
    pid = r.json()["id"]

    from sqlalchemy import text
    async with engine.connect() as conn:
        row = (await conn.execute(
            text("SELECT admin_id FROM payments WHERE id=:id"), {"id": pid}
        )).first()
    assert row[0] is not None


@pytest.mark.asyncio
async def test_create_payment_explicit_period_6m_uses_price_6m(
    admin_client, make_committed, mock_tg, clean_db,
):
    user = await make_committed.user()
    product = await make_committed.product(price_3m=100, price_6m=200, price_12m=300)
    r = await admin_client.post(
        "/api/payments",
        json={"user_id": user.id, "product_id": product.id, "period_months": 6},
    )
    assert r.json()["amount"] == "200.00"


@pytest.mark.asyncio
async def test_create_payment_requires_auth(api_client):
    r = await api_client.post("/api/payments", json={
        "user_id": 1, "product_id": 1, "period_months": 3,
    })
    assert r.status_code == 401
