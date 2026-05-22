"""Unit-тесты services/subscriptions с use of `make` хелпера (см. conftest)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from freezegun import freeze_time

from app.services.subscriptions import _add_months, expire_due, extend, grant_for_payment


def _patch_bot_and_tg(monkeypatch):
    calls = MagicMock()
    calls.invite = AsyncMock(return_value="https://t.me/+invitelink")
    calls.kick = AsyncMock(return_value=True)
    calls.send = AsyncMock(return_value=True)

    monkeypatch.setattr("app.bot.manager.get_aiogram_bot", lambda _: MagicMock())
    monkeypatch.setattr("app.services.subscriptions.tg.create_one_time_invite", calls.invite)
    monkeypatch.setattr("app.services.subscriptions.tg.kick_user", calls.kick)
    monkeypatch.setattr("app.services.subscriptions.tg.send_message_safe", calls.send)
    return calls


# ───────── _add_months ─────────

class TestAddMonths:
    def test_three_months(self):
        d = datetime(2026, 1, 15, tzinfo=timezone.utc)
        assert _add_months(d, 3) == datetime(2026, 4, 15, tzinfo=timezone.utc)

    def test_twelve_months_is_one_year(self):
        d = datetime(2026, 5, 22, tzinfo=timezone.utc)
        assert _add_months(d, 12) == datetime(2027, 5, 22, tzinfo=timezone.utc)

    def test_handles_month_overflow_end_of_month(self):
        d = datetime(2026, 1, 31, tzinfo=timezone.utc)
        result = _add_months(d, 1)
        assert result.month == 2
        assert result.day in (28, 29)


# ───────── grant_for_payment ─────────

@pytest.mark.asyncio
@freeze_time("2026-05-22 12:00:00", tz_offset=0)
async def test_grant_creates_new_subscription(session, make, monkeypatch):
    calls = _patch_bot_and_tg(monkeypatch)
    payment = await make.payment(period_months=3)

    sub = await grant_for_payment(session, payment)

    assert sub.status == "active"
    assert sub.user_id == payment.user_id
    assert sub.product_id == payment.product_id
    assert sub.payment_id == payment.id
    assert sub.starts_at == datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    assert sub.ends_at == datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)
    assert sub.invite_link == "https://t.me/+invitelink"
    calls.invite.assert_awaited_once()
    calls.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_grant_extends_existing_active_subscription(session, make, monkeypatch):
    _patch_bot_and_tg(monkeypatch)
    user = await make.user()
    product = await make.product()
    channel = product.channel

    now = datetime.now(tz=timezone.utc)
    existing_ends = now + timedelta(days=30)
    await make.subscription(
        user=user, channel=channel, product=product,
        starts_at=now - timedelta(days=60), ends_at=existing_ends, status="active",
    )

    payment = await make.payment(user=user, product=product, period_months=6)
    sub = await grant_for_payment(session, payment)

    from sqlalchemy import select
    from app.models.subscription import Subscription
    all_subs = (
        await session.execute(
            select(Subscription).where(Subscription.user_id == user.id, Subscription.channel_id == channel.id)
        )
    ).scalars().all()
    assert len(all_subs) == 1
    assert sub.id == all_subs[0].id
    assert sub.ends_at == _add_months(existing_ends, 6)


@pytest.mark.asyncio
async def test_grant_creates_new_when_existing_is_expired(session, make, monkeypatch):
    _patch_bot_and_tg(monkeypatch)
    user = await make.user()
    product = await make.product()
    channel = product.channel
    now = datetime.now(tz=timezone.utc)
    await make.subscription(
        user=user, channel=channel, product=product,
        starts_at=now - timedelta(days=200), ends_at=now - timedelta(days=10), status="expired",
    )

    payment = await make.payment(user=user, product=product, period_months=3)
    sub = await grant_for_payment(session, payment)
    assert sub.status == "active"
    assert sub.ends_at > now + timedelta(days=85)


@pytest.mark.asyncio
async def test_grant_without_bot_creates_subscription_but_no_invite(session, make, monkeypatch):
    monkeypatch.setattr("app.bot.manager.get_aiogram_bot", lambda _: None)
    payment = await make.payment(period_months=3)
    sub = await grant_for_payment(session, payment)
    assert sub.status == "active"
    assert sub.invite_link is None


# ───────── revoke ─────────

@pytest.mark.asyncio
async def test_revoke_kicks_user_and_sends_notification(session, make, monkeypatch):
    calls = _patch_bot_and_tg(monkeypatch)
    sub = await make.subscription(status="active")
    from app.services.subscriptions import revoke
    await revoke(session, sub, status="revoked", notify=True)
    assert sub.status == "revoked"
    calls.kick.assert_awaited_once()
    calls.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_revoke_without_notify_skips_message(session, make, monkeypatch):
    calls = _patch_bot_and_tg(monkeypatch)
    sub = await make.subscription(status="active")
    from app.services.subscriptions import revoke
    await revoke(session, sub, status="expired", notify=False)
    assert sub.status == "expired"
    calls.kick.assert_awaited_once()
    calls.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_revoke_without_bot_only_changes_status(session, make, monkeypatch):
    monkeypatch.setattr("app.bot.manager.get_aiogram_bot", lambda _: None)
    sub = await make.subscription(status="active")
    from app.services.subscriptions import revoke
    await revoke(session, sub, status="revoked", notify=True)
    assert sub.status == "revoked"


# ───────── extend ─────────

@pytest.mark.asyncio
async def test_extend_active_subscription_by_days(session, make, monkeypatch):
    _patch_bot_and_tg(monkeypatch)
    now = datetime.now(tz=timezone.utc)
    sub = await make.subscription(status="active", ends_at=now + timedelta(days=10))
    original_ends = sub.ends_at
    await extend(session, sub, days=5)
    assert sub.ends_at == original_ends + timedelta(days=5)
    assert sub.status == "active"


@pytest.mark.asyncio
async def test_extend_active_by_months(session, make, monkeypatch):
    _patch_bot_and_tg(monkeypatch)
    now = datetime.now(tz=timezone.utc)
    sub = await make.subscription(status="active", ends_at=now + timedelta(days=10))
    original_ends = sub.ends_at
    await extend(session, sub, months=2)
    assert sub.ends_at == _add_months(original_ends, 2)


@pytest.mark.asyncio
async def test_extend_expired_subscription_sends_new_invite(session, make, monkeypatch):
    calls = _patch_bot_and_tg(monkeypatch)
    now = datetime.now(tz=timezone.utc)
    sub = await make.subscription(status="expired", ends_at=now - timedelta(days=5), invite_link=None)

    await extend(session, sub, months=3)

    assert sub.status == "active"
    assert sub.ends_at > now + timedelta(days=85)
    calls.invite.assert_awaited_once()
    calls.send.assert_awaited_once()
    assert sub.invite_link == "https://t.me/+invitelink"


@pytest.mark.asyncio
async def test_extend_active_subscription_does_not_resend_invite(session, make, monkeypatch):
    calls = _patch_bot_and_tg(monkeypatch)
    now = datetime.now(tz=timezone.utc)
    sub = await make.subscription(status="active", ends_at=now + timedelta(days=10))
    await extend(session, sub, days=7)
    calls.invite.assert_not_awaited()
    calls.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_extend_from_past_ends_at_starts_from_now(session, make, monkeypatch):
    _patch_bot_and_tg(monkeypatch)
    now = datetime.now(tz=timezone.utc)
    sub = await make.subscription(status="revoked", ends_at=now - timedelta(days=30))
    await extend(session, sub, days=10)
    assert sub.ends_at > now + timedelta(days=9)
    assert sub.ends_at < now + timedelta(days=11)


# ───────── expire_due ─────────

@pytest.mark.asyncio
async def test_expire_due_picks_only_active_with_past_ends_at(session, make, monkeypatch):
    _patch_bot_and_tg(monkeypatch)
    now = datetime.now(tz=timezone.utc)
    expired_sub = await make.subscription(status="active", ends_at=now - timedelta(hours=1))
    future_sub = await make.subscription(status="active", ends_at=now + timedelta(days=30))
    already_sub = await make.subscription(status="expired", ends_at=now - timedelta(days=30))
    await session.commit()

    count = await expire_due(session)
    assert count == 1

    await session.refresh(expired_sub)
    await session.refresh(future_sub)
    await session.refresh(already_sub)
    assert expired_sub.status == "expired"
    assert future_sub.status == "active"
    assert already_sub.status == "expired"


@pytest.mark.asyncio
async def test_expire_due_returns_zero_when_nothing_to_do(session, make, monkeypatch):
    _patch_bot_and_tg(monkeypatch)
    now = datetime.now(tz=timezone.utc)
    await make.subscription(status="active", ends_at=now + timedelta(days=30))
    await session.commit()
    count = await expire_due(session)
    assert count == 0
