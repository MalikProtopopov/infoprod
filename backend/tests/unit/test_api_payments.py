"""API: GET/POST/PATCH/DELETE /api/payments."""
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
async def test_list_payments_empty(admin_client, clean_db):
    r = await admin_client.get("/api/payments")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_create_payment_with_default_amount(admin_client, make_committed, mock_tg, clean_db):
    product = await make_committed.product(price_3m=1500)
    user = await make_committed.user()

    r = await admin_client.post(
        "/api/payments",
        **payment_form(user_id=user.id, product_id=product.id, period_months=3),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["period_months"] == 3
    assert body["amount"] == "1500.00"
    assert len(body["receipts"]) == 1  # чек приложен и сохранён


@pytest.mark.asyncio
async def test_create_payment_requires_receipt(admin_client, make_committed, mock_tg, clean_db):
    """Без чека платёж не создаётся → 422 (защита от накрутки)."""
    product = await make_committed.product()
    user = await make_committed.user()
    r = await admin_client.post(
        "/api/payments",
        **payment_form(with_receipt=False, user_id=user.id, product_id=product.id, period_months=3),
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_payment_with_custom_amount(admin_client, make_committed, mock_tg, clean_db):
    product = await make_committed.product()
    user = await make_committed.user()
    r = await admin_client.post(
        "/api/payments",
        **payment_form(user_id=user.id, product_id=product.id, period_months=6, amount="999"),
    )
    assert r.status_code == 201
    assert r.json()["amount"] == "999.00"


@pytest.mark.asyncio
async def test_create_payment_negative_amount_returns_422(admin_client, make_committed, mock_tg, clean_db):
    product = await make_committed.product()
    user = await make_committed.user()
    r = await admin_client.post(
        "/api/payments",
        **payment_form(user_id=user.id, product_id=product.id, period_months=3, amount="-100"),
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_payment_unknown_user(admin_client, make_committed, clean_db):
    product = await make_committed.product()
    r = await admin_client.post(
        "/api/payments",
        **payment_form(user_id=99999, product_id=product.id, period_months=3),
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_create_payment_unknown_product(admin_client, make_committed, clean_db):
    user = await make_committed.user()
    r = await admin_client.post(
        "/api/payments",
        **payment_form(user_id=user.id, product_id=99999, period_months=3),
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_create_payment_invalid_period(admin_client, make_committed, clean_db):
    user = await make_committed.user()
    product = await make_committed.product()
    r = await admin_client.post(
        "/api/payments",
        **payment_form(user_id=user.id, product_id=product.id, period_months=1),
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_payment_no_active_bot_returns_409(admin_client, make_committed, clean_db, monkeypatch):
    monkeypatch.setattr("app.bot.manager.get_aiogram_bot", lambda _: None)
    user = await make_committed.user()
    product = await make_committed.product()
    r = await admin_client.post(
        "/api/payments",
        **payment_form(user_id=user.id, product_id=product.id, period_months=3),
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_update_payment_comment(admin_client, make_committed, clean_db):
    payment = await make_committed.payment()
    r = await admin_client.patch(
        f"/api/payments/{payment.id}",
        json={"comment": "added comment"},
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_delete_payment_revokes_related_subscription(
    admin_client, make_committed, mock_tg, engine, clean_db,
):
    """Удаление платежа должно отозвать подписку, если она связана payment_id."""
    payment = await make_committed.payment()
    user = payment.user_id
    sub = await make_committed.subscription(
        user_id=payment.user_id, status="active",
        product_id=payment.product_id, payment_id=payment.id,
    )

    r = await admin_client.delete(f"/api/payments/{payment.id}")
    assert r.status_code == 204

    from sqlalchemy import text
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text("SELECT status FROM subscriptions WHERE id=:id"), {"id": sub.id},
            )
        ).first()
    assert row[0] == "revoked"


@pytest.mark.asyncio
async def test_delete_unknown_payment_404(admin_client, clean_db):
    r = await admin_client.delete("/api/payments/99999")
    assert r.status_code == 404
