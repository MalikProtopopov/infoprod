"""API: GET /api/subscriptions + POST revoke/extend."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_tg(monkeypatch):
    """Подмена bot_manager + tg.* функций — без реальных TG-вызовов."""
    monkeypatch.setattr("app.bot.manager.get_aiogram_bot", lambda _: MagicMock())
    monkeypatch.setattr("app.services.subscriptions.tg.create_one_time_invite", AsyncMock(return_value="https://t.me/+x"))
    monkeypatch.setattr("app.services.subscriptions.tg.kick_user", AsyncMock(return_value=True))
    monkeypatch.setattr("app.services.subscriptions.tg.send_message_safe", AsyncMock(return_value=True))


@pytest.mark.asyncio
async def test_list_subscriptions_empty(admin_client, clean_db):
    r = await admin_client.get("/api/subscriptions")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_list_subscriptions_filtered_by_status(admin_client, make_committed, clean_db):
    await make_committed.subscription(status="active")
    await make_committed.subscription(status="expired")
    await make_committed.subscription(status="revoked")

    r = await admin_client.get("/api/subscriptions?status=active")
    assert len(r.json()) == 1
    r = await admin_client.get("/api/subscriptions?status=expired")
    assert len(r.json()) == 1
    r = await admin_client.get("/api/subscriptions?status=all")
    assert len(r.json()) == 3


@pytest.mark.asyncio
async def test_revoke_subscription(admin_client, make_committed, mock_tg, clean_db):
    sub = await make_committed.subscription(status="active")
    r = await admin_client.post(f"/api/subscriptions/{sub.id}/revoke")
    assert r.status_code == 200
    assert r.json()["status"] == "revoked"


@pytest.mark.asyncio
async def test_revoke_unknown_returns_404(admin_client, clean_db):
    r = await admin_client.post("/api/subscriptions/99999/revoke")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_extend_by_days(admin_client, make_committed, mock_tg, engine, clean_db):
    now = datetime.now(tz=timezone.utc)
    sub = await make_committed.subscription(status="active", ends_at=now + timedelta(days=10))
    original_ends = sub.ends_at

    r = await admin_client.post(
        f"/api/subscriptions/{sub.id}/extend",
        json={"days": 5},
    )
    assert r.status_code == 200, r.text

    # Прямой SELECT
    from sqlalchemy import text
    async with engine.connect() as conn:
        new_ends = (
            await conn.execute(
                text("SELECT ends_at FROM subscriptions WHERE id=:id"), {"id": sub.id},
            )
        ).scalar_one()
    if new_ends.tzinfo is None:
        new_ends = new_ends.replace(tzinfo=timezone.utc)
    # ends_at += 5 дней
    delta = new_ends - original_ends
    assert abs(delta.total_seconds() - 5 * 86400) < 5


@pytest.mark.asyncio
async def test_extend_without_period_returns_400(admin_client, make_committed, mock_tg, clean_db):
    sub = await make_committed.subscription(status="active")
    r = await admin_client.post(f"/api/subscriptions/{sub.id}/extend", json={})
    assert r.status_code == 400
