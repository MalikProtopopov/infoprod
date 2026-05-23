"""Тесты FunnelsService — start_for_user, cancel, find_active, completion."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select

from app.models.funnel_entry import FunnelEntry
from app.models.scheduled_message import ScheduledMessage
from app.services.funnels import FunnelsService


@pytest.mark.asyncio
async def test_create_funnel_with_steps(session, make):
    product = await make.product()
    svc = FunnelsService(session)
    f = await svc.create(
        name="Test funnel",
        product_id=product.id,
        steps=[
            {"order_idx": 0, "delay_minutes": 0, "message_text": "Hello"},
            {"order_idx": 1, "delay_minutes": 60, "message_text": "Next"},
        ],
    )
    await session.flush()
    assert f.id is not None
    assert f.name == "Test funnel"
    from app.models.funnel_step import FunnelStep
    steps = (
        await session.execute(select(FunnelStep).where(FunnelStep.funnel_id == f.id))
    ).scalars().all()
    assert len(steps) == 2


@pytest.mark.asyncio
async def test_start_for_user_creates_entry_and_messages(session, make):
    user = await make.user()
    funnel = await make.funnel()
    await make.funnel_step(funnel=funnel, order_idx=0, delay_minutes=0)
    await make.funnel_step(funnel=funnel, order_idx=1, delay_minutes=60)
    await make.funnel_step(funnel=funnel, order_idx=2, delay_minutes=1440)

    svc = FunnelsService(session)
    entry = await svc.start_for_user(
        user_id=user.id, funnel_id=funnel.id, source="manual",
    )
    assert entry is not None
    assert entry.status == "active"

    msgs = (
        await session.execute(
            select(ScheduledMessage).where(ScheduledMessage.funnel_entry_id == entry.id)
        )
    ).scalars().all()
    assert len(msgs) == 3


@pytest.mark.asyncio
async def test_start_for_user_skips_when_user_unsubscribed(session, make):
    user = await make.user(notifications_enabled=False)
    funnel = await make.funnel()
    await make.funnel_step(funnel=funnel, order_idx=0, delay_minutes=0)
    svc = FunnelsService(session)
    entry = await svc.start_for_user(
        user_id=user.id, funnel_id=funnel.id, source="manual",
    )
    assert entry is None


@pytest.mark.asyncio
async def test_start_for_user_skips_when_funnel_inactive(session, make):
    user = await make.user()
    funnel = await make.funnel(is_active=False)
    svc = FunnelsService(session)
    entry = await svc.start_for_user(
        user_id=user.id, funnel_id=funnel.id, source="manual",
    )
    assert entry is None


@pytest.mark.asyncio
async def test_start_for_user_idempotent_returns_existing(session, make):
    """Повторный вызов возвращает существующую entry, не создаёт новую."""
    user = await make.user()
    funnel = await make.funnel()
    await make.funnel_step(funnel=funnel, order_idx=0, delay_minutes=0)
    svc = FunnelsService(session)
    e1 = await svc.start_for_user(user_id=user.id, funnel_id=funnel.id, source="manual")
    e2 = await svc.start_for_user(user_id=user.id, funnel_id=funnel.id, source="code_word")
    assert e1 is not None and e2 is not None
    assert e1.id == e2.id


@pytest.mark.asyncio
async def test_find_active_entry(session, make):
    user = await make.user()
    funnel = await make.funnel()
    svc = FunnelsService(session)

    # Нет активных — None
    assert await svc.find_active_entry(user_id=user.id, funnel_id=funnel.id) is None

    entry = await make.funnel_entry(user=user, funnel=funnel, status="active")
    found = await svc.find_active_entry(user_id=user.id, funnel_id=funnel.id)
    assert found is not None and found.id == entry.id

    # Cancelled — не возвращается
    entry.status = "cancelled"
    await session.flush()
    assert await svc.find_active_entry(user_id=user.id, funnel_id=funnel.id) is None


@pytest.mark.asyncio
async def test_cancel_entry_marks_messages_cancelled(session, make):
    user = await make.user()
    funnel = await make.funnel()
    step = await make.funnel_step(funnel=funnel, delay_minutes=0)
    svc = FunnelsService(session)
    entry = await svc.start_for_user(user_id=user.id, funnel_id=funnel.id, source="manual")

    ok = await svc.cancel_entry(entry.id, reason="payment_received")
    assert ok is True
    await session.refresh(entry)
    assert entry.status == "cancelled"
    assert entry.cancel_reason == "payment_received"

    msgs = (
        await session.execute(
            select(ScheduledMessage).where(ScheduledMessage.funnel_entry_id == entry.id)
        )
    ).scalars().all()
    for m in msgs:
        assert m.cancelled_at is not None
        assert m.cancel_reason == "payment_received"


@pytest.mark.asyncio
async def test_cancel_entry_returns_false_for_inactive(session, make):
    entry = await make.funnel_entry(status="cancelled")
    svc = FunnelsService(session)
    assert await svc.cancel_entry(entry.id) is False


@pytest.mark.asyncio
async def test_cancel_entries_for_user_on_payment(session, make):
    user = await make.user()
    product = await make.product()
    # Воронка #1 — связана с продуктом, cancel_on_payment=True
    f1 = await make.funnel(product=product, cancel_on_payment=True)
    # Воронка #2 — другой продукт
    other = await make.product()
    f2 = await make.funnel(product=other, cancel_on_payment=True)
    # Воронка #3 — этот продукт но cancel_on_payment=False
    f3 = await make.funnel(product=product, cancel_on_payment=False)

    e1 = await make.funnel_entry(user=user, funnel=f1, status="active")
    e2 = await make.funnel_entry(user=user, funnel=f2, status="active")
    e3 = await make.funnel_entry(user=user, funnel=f3, status="active")

    svc = FunnelsService(session)
    count = await svc.cancel_entries_for_user_on_payment(user_id=user.id, product_id=product.id)
    assert count == 1  # Только f1 отменилось

    await session.refresh(e1)
    await session.refresh(e2)
    await session.refresh(e3)
    assert e1.status == "cancelled" and e1.cancel_reason == "payment_received"
    assert e2.status == "active"  # другой продукт
    assert e3.status == "active"  # cancel_on_payment=False


@pytest.mark.asyncio
async def test_check_and_complete(session, make):
    user = await make.user()
    funnel = await make.funnel()
    step = await make.funnel_step(funnel=funnel, delay_minutes=0)
    svc = FunnelsService(session)
    entry = await svc.start_for_user(user_id=user.id, funnel_id=funnel.id, source="manual")

    # Пока есть unsent — не complete
    assert await svc.check_and_complete(entry.id) is False
    await session.refresh(entry)
    assert entry.status == "active"

    # Помечаем сообщения как sent
    from sqlalchemy import update
    await session.execute(
        update(ScheduledMessage)
        .where(ScheduledMessage.funnel_entry_id == entry.id)
        .values(sent_at=datetime.now(tz=timezone.utc))
    )

    assert await svc.check_and_complete(entry.id) is True
    # entry изменён внутри svc — наша ссылка может быть свежей, читаем напрямую
    from sqlalchemy import select as _sel
    res = (
        await session.execute(_sel(FunnelEntry.status, FunnelEntry.completed_at)
                              .where(FunnelEntry.id == entry.id))
    ).first()
    assert res[0] == "completed"
    assert res[1] is not None


@pytest.mark.asyncio
async def test_add_step(session, make):
    funnel = await make.funnel()
    svc = FunnelsService(session)
    step = await svc.add_step(
        funnel.id, order_idx=5, delay_minutes=120,
        message_text="Added step",
    )
    assert step.funnel_id == funnel.id
    assert step.order_idx == 5
    assert step.delay_minutes == 120


@pytest.mark.asyncio
async def test_reorder_steps(session, make):
    funnel = await make.funnel()
    s1 = await make.funnel_step(funnel=funnel, order_idx=0, message_text="A")
    s2 = await make.funnel_step(funnel=funnel, order_idx=1, message_text="B")
    s3 = await make.funnel_step(funnel=funnel, order_idx=2, message_text="C")

    svc = FunnelsService(session)
    await svc.reorder_steps(funnel.id, [s3.id, s1.id, s2.id])
    await session.refresh(s1)
    await session.refresh(s2)
    await session.refresh(s3)
    assert s3.order_idx == 0
    assert s1.order_idx == 1
    assert s2.order_idx == 2
