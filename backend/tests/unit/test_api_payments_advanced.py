"""Дополнительные тесты /api/payments: auto-paid lead, tracking_link inherit, период 6/12."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.helpers import payment_form


@pytest.fixture
def mock_tg(monkeypatch):
    monkeypatch.setattr("app.bot.manager.get_aiogram_bot", lambda _: MagicMock())
    monkeypatch.setattr("app.services.subscriptions.tg.create_one_time_invite", AsyncMock(return_value="https://t.me/+x"))
    monkeypatch.setattr("app.services.subscriptions.tg.kick_user", AsyncMock(return_value=True))
    monkeypatch.setattr("app.services.subscriptions.tg.send_message_safe", AsyncMock(return_value=True))


@pytest.mark.asyncio
async def test_create_payment_auto_marks_open_lead_as_paid(
    admin_client, make_committed, mock_tg, engine, clean_db,
):
    """Если у пользователя есть незакрытый lead — он автоматом становится paid."""
    user = await make_committed.user()
    product = await make_committed.product()
    lead = await make_committed.lead(user=user, product=product, status="new")

    r = await admin_client.post(
        "/api/payments",
        **payment_form(user_id= user.id, product_id= product.id, period_months= 3),
    )
    assert r.status_code == 201

    from sqlalchemy import text
    async with engine.connect() as conn:
        row = (await conn.execute(
            text("SELECT status, paid_at FROM leads WHERE id=:id"), {"id": lead.id}
        )).first()
    assert row[0] == "paid"
    assert row[1] is not None


@pytest.mark.asyncio
async def test_create_payment_for_period_6(admin_client, make_committed, mock_tg, clean_db):
    user = await make_committed.user()
    product = await make_committed.product(price_3m=1000, price_6m=1800)
    r = await admin_client.post(
        "/api/payments",
        **payment_form(user_id= user.id, product_id= product.id, period_months= 6),
    )
    assert r.status_code == 201
    assert r.json()["amount"] == "1800.00"


@pytest.mark.asyncio
async def test_create_payment_for_period_12(admin_client, make_committed, mock_tg, clean_db):
    user = await make_committed.user()
    product = await make_committed.product(price_12m=2999)
    r = await admin_client.post(
        "/api/payments",
        **payment_form(user_id= user.id, product_id= product.id, period_months= 12),
    )
    assert r.status_code == 201
    assert r.json()["amount"] == "2999.00"


@pytest.mark.asyncio
async def test_create_payment_inherits_tracking_link_from_open_lead(
    admin_client, make_committed, mock_tg, engine, clean_db,
):
    """Если у пользователя был лид с tracking_link_id — оно подхватится в payment."""
    user = await make_committed.user()
    product = await make_committed.product()
    link = await make_committed.tracking_link(product=product, utm_source="ig")
    lead = await make_committed.lead(user=user, product=product, status="new")
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE leads SET tracking_link_id=:l WHERE id=:id"),
            {"l": link.id, "id": lead.id},
        )

    r = await admin_client.post(
        "/api/payments",
        **payment_form(user_id= user.id, product_id= product.id, period_months= 3),
    )
    assert r.status_code == 201
    pid = r.json()["id"]
    async with engine.connect() as conn:
        row = (await conn.execute(
            text("SELECT tracking_link_id FROM payments WHERE id=:id"), {"id": pid}
        )).first()
    assert row[0] == link.id


@pytest.mark.asyncio
async def test_create_payment_with_comment(admin_client, make_committed, mock_tg, clean_db):
    user = await make_committed.user()
    product = await make_committed.product()
    r = await admin_client.post(
        "/api/payments",
        **payment_form(user_id= user.id, product_id= product.id, period_months= 3, comment= "from email follow-up"),
    )
    assert r.status_code == 201


@pytest.mark.asyncio
async def test_delete_payment_revokes_only_active_subscription(
    admin_client, make_committed, mock_tg, engine, clean_db,
):
    """Если подписка уже expired — не нужно revoke."""
    user = await make_committed.user()
    product = await make_committed.product()
    payment = await make_committed.payment(user=user, product=product)
    sub = await make_committed.subscription(
        user=user, channel=await make_committed.channel(),
        product=product, status="expired", payment_id=payment.id,
    )

    r = await admin_client.delete(f"/api/payments/{payment.id}")
    assert r.status_code == 204

    from sqlalchemy import text
    async with engine.connect() as conn:
        row = (await conn.execute(
            text("SELECT status FROM subscriptions WHERE id=:id"), {"id": sub.id}
        )).first()
    # Подписка осталась expired (а не revoked) — её не трогали
    assert row[0] == "expired"


@pytest.mark.asyncio
async def test_list_payments_returns_user_username_and_product_name(
    admin_client, make_committed, clean_db,
):
    user = await make_committed.user(username="testuser123")
    product = await make_committed.product(name="My Product")
    await make_committed.payment(user=user, product=product)

    r = await admin_client.get("/api/payments")
    body = r.json()
    assert len(body) == 1
    assert body[0]["user_username"] == "testuser123"
    assert body[0]["product_name"] == "My Product"


@pytest.mark.asyncio
async def test_list_requires_auth(api_client):
    r = await api_client.get("/api/payments")
    assert r.status_code == 401
