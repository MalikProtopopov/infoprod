"""API: GET/PATCH /api/users."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_list_users_empty(admin_client, clean_db):
    r = await admin_client.get("/api/users")
    assert r.status_code == 200
    body = r.json()
    assert body == {"total": 0, "items": []}


@pytest.mark.asyncio
async def test_list_users_pagination(admin_client, make_committed, clean_db):
    for i in range(5):
        await make_committed.user(telegram_user_id=10000 + i, username=f"u{i}")

    r = await admin_client.get("/api/users?limit=3")
    body = r.json()
    assert body["total"] == 5
    assert len(body["items"]) == 3


@pytest.mark.asyncio
async def test_list_users_search_by_username(admin_client, make_committed, clean_db):
    await make_committed.user(username="alice", first_name="Alice", telegram_user_id=20001)
    await make_committed.user(username="bob", first_name="Bob", telegram_user_id=20002)
    await make_committed.user(username="charlie", first_name="Charlie", telegram_user_id=20003)

    r = await admin_client.get("/api/users?q=ali")
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["username"] == "alice"


@pytest.mark.asyncio
async def test_list_users_search_with_at_prefix(admin_client, make_committed, clean_db):
    """@-префикс должен быть отброшен в запросе."""
    await make_committed.user(username="someone", first_name="X", telegram_user_id=20010)
    r = await admin_client.get("/api/users?q=@someone")
    assert r.json()["total"] == 1


@pytest.mark.asyncio
async def test_list_users_search_by_telegram_id(admin_client, make_committed, clean_db):
    """Числовой запрос должен искать также по telegram_user_id."""
    await make_committed.user(telegram_user_id=370638927, first_name="Malik")
    r = await admin_client.get("/api/users?q=370638927")
    assert r.json()["total"] == 1


@pytest.mark.asyncio
async def test_list_users_search_by_first_name(admin_client, make_committed, clean_db):
    await make_committed.user(first_name="Ivan", username="ivan_x", telegram_user_id=20020)
    r = await admin_client.get("/api/users?q=ivan")
    # match по first_name и username — оба «ivan», но один уник user
    assert r.json()["total"] == 1


@pytest.mark.asyncio
async def test_get_user_returns_full_card(admin_client, make_committed, clean_db):
    user = await make_committed.user(first_name="Fred", username="fred", telegram_user_id=30000)
    r = await admin_client.get(f"/api/users/{user.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["first_name"] == "Fred"
    assert "leads" in body
    assert "payments" in body
    assert "subscriptions" in body
    assert body["leads"] == []
    assert body["payments"] == []
    assert body["subscriptions"] == []


@pytest.mark.asyncio
async def test_get_user_with_history(admin_client, make_committed, clean_db):
    user = await make_committed.user(telegram_user_id=30100)
    product = await make_committed.product()
    await make_committed.lead(user=user, product=product, status="paid")
    await make_committed.payment(user=user, product=product, period_months=3, amount=1500)

    r = await admin_client.get(f"/api/users/{user.id}")
    body = r.json()
    assert len(body["leads"]) == 1
    assert body["leads"][0]["status"] == "paid"
    assert body["leads"][0]["channel_title"] is not None
    assert len(body["payments"]) == 1
    assert body["payments"][0]["amount"] == "1500.00"


@pytest.mark.asyncio
async def test_get_unknown_user_returns_404(admin_client, clean_db):
    r = await admin_client.get("/api/users/99999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_patch_user_phone_email_notes(admin_client, make_committed, clean_db):
    user = await make_committed.user()
    r = await admin_client.patch(
        f"/api/users/{user.id}",
        json={"phone": "+7-911-1234567", "email": "u@example.com", "notes": "Important customer"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["phone"] == "+7-911-1234567"
    assert body["email"] == "u@example.com"
    assert body["notes"] == "Important customer"


@pytest.mark.asyncio
async def test_patch_user_invalid_email_returns_422(admin_client, make_committed, clean_db):
    user = await make_committed.user()
    r = await admin_client.patch(f"/api/users/{user.id}", json={"email": "not-an-email"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_patch_unknown_user_returns_404(admin_client, clean_db):
    r = await admin_client.patch("/api/users/99999", json={"notes": "x"})
    assert r.status_code == 404
