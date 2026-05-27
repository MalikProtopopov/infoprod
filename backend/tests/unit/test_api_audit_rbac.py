"""API: /api/audit-log + GDPR + RBAC проверки."""
from __future__ import annotations

import pytest

from tests.helpers import payment_form


@pytest.mark.asyncio
async def test_audit_log_list_empty(admin_client, clean_db):
    r = await admin_client.get("/api/audit-log")
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []


@pytest.mark.asyncio
async def test_audit_log_requires_auth(api_client):
    r = await api_client.get("/api/audit-log")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_audit_log_records_payment_creation(
    admin_client, make_committed, engine, clean_db, monkeypatch,
):
    """После POST /payments в audit_log должна появиться запись."""
    from unittest.mock import AsyncMock, MagicMock
    monkeypatch.setattr("app.bot.manager.get_aiogram_bot", lambda _: MagicMock())
    monkeypatch.setattr("app.services.subscriptions.tg.create_one_time_invite",
                        AsyncMock(return_value="https://t.me/+x"))
    monkeypatch.setattr("app.services.subscriptions.tg.kick_user", AsyncMock(return_value=True))
    monkeypatch.setattr("app.services.subscriptions.tg.send_message_safe", AsyncMock(return_value=True))

    user = await make_committed.user()
    product = await make_committed.product()
    r = await admin_client.post(
        "/api/payments",
        **payment_form(user_id= user.id, product_id= product.id, period_months= 3),
    )
    assert r.status_code == 201

    # Проверяем audit_log запись
    audit = await admin_client.get("/api/audit-log?resource_type=payment&action=create")
    body = audit.json()
    assert body["items"], "audit_log должен содержать запись о создании платежа"
    last = body["items"][0]
    assert last["resource_type"] == "payment"
    assert last["action"] == "create"
    assert last["admin_id"] is not None


@pytest.mark.asyncio
async def test_audit_logs_lead_status_change(admin_client, make_committed, clean_db):
    """Смена статуса заявки (раньше не логировалась) теперь пишется middleware'ом."""
    lead = await make_committed.lead(status="new")
    r = await admin_client.patch(f"/api/leads/{lead.id}", json={"status": "contacted"})
    assert r.status_code == 200
    audit = await admin_client.get("/api/audit-log?resource_type=lead&action=update")
    items = audit.json()["items"]
    assert any(it["resource_id"] == lead.id for it in items), "PATCH /leads должен попасть в аудит"


@pytest.mark.asyncio
async def test_audit_logs_product_delete(admin_client, make_committed, clean_db):
    """Удаление продукта (раньше не логировалось) теперь в аудите."""
    product = await make_committed.product()
    r = await admin_client.delete(f"/api/products/{product.id}")
    assert r.status_code in (200, 204)
    audit = await admin_client.get("/api/audit-log?resource_type=product&action=delete")
    assert any(it["resource_id"] == product.id for it in audit.json()["items"])


@pytest.mark.asyncio
async def test_audit_log_filter_by_admin(admin_client, make_committed, clean_db):
    """Фильтрация по admin_id."""
    # Просто проверим что фильтр не падает
    r = await admin_client.get("/api/audit-log?admin_id=1")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_gdpr_export_unknown_user_404(admin_client, clean_db):
    r = await admin_client.get("/api/users/99999/export")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_gdpr_export_returns_user_data(admin_client, make_committed, clean_db):
    user = await make_committed.user(first_name="Alice", username="alice")
    product = await make_committed.product()
    await make_committed.lead(user=user, product=product, status="new")
    await make_committed.payment(user=user, product=product)

    r = await admin_client.get(f"/api/users/{user.id}/export")
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["first_name"] == "Alice"
    assert body["user"]["username"] == "alice"
    assert len(body["leads"]) == 1
    assert len(body["payments"]) == 1
    assert body["subscriptions"] == []


@pytest.mark.asyncio
async def test_gdpr_forget_anonymizes_user(admin_client, make_committed, engine, clean_db):
    user = await make_committed.user(
        first_name="Alice", last_name="A",
        username="alice", phone="+7-911", email="a@b.com", notes="VIP",
    )
    r = await admin_client.delete(f"/api/users/{user.id}/forget")
    assert r.status_code == 204

    from sqlalchemy import text
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text("SELECT first_name, last_name, username, phone, email, notes, "
                     "telegram_user_id, notifications_enabled FROM users WHERE id=:id"),
                {"id": user.id},
            )
        ).first()
    assert row[0] == "[redacted]"  # first_name
    assert row[1] is None  # last_name
    assert row[2] is None  # username
    assert row[3] is None  # phone
    assert row[4] is None  # email
    assert row[5] is None  # notes
    assert row[6] < 0      # telegram_user_id отрицательный (анонимизирован)
    assert row[7] is False  # notifications_enabled выключен


@pytest.mark.asyncio
async def test_gdpr_forget_unknown_user_404(admin_client, clean_db):
    r = await admin_client.delete("/api/users/99999/forget")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_gdpr_forget_records_audit(admin_client, make_committed, clean_db):
    user = await make_committed.user()
    r = await admin_client.delete(f"/api/users/{user.id}/forget")
    assert r.status_code == 204

    audit = await admin_client.get("/api/audit-log?action=gdpr_forget")
    body = audit.json()
    assert body["items"], "GDPR forget должен быть в audit_log"


@pytest.mark.asyncio
async def test_gdpr_export_records_audit(admin_client, make_committed, clean_db):
    user = await make_committed.user()
    r = await admin_client.get(f"/api/users/{user.id}/export")
    assert r.status_code == 200

    audit = await admin_client.get("/api/audit-log?action=gdpr_export")
    body = audit.json()
    assert body["items"]
