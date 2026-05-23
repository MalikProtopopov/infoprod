"""Тесты FunnelTriggersService — case-insensitive lookup, unique, validation."""
from __future__ import annotations

import pytest

from app.services.funnel_triggers import (
    FunnelTriggersService,
    InvalidTriggerWordError,
    TriggerConflictError,
)


@pytest.mark.asyncio
async def test_create_lowercases_word(session, make):
    funnel = await make.funnel()
    svc = FunnelTriggersService(session)
    t = await svc.create(word="КЛУБ", funnel_id=funnel.id)
    assert t.word == "клуб"


@pytest.mark.asyncio
async def test_create_strips_spaces(session, make):
    funnel = await make.funnel()
    svc = FunnelTriggersService(session)
    t = await svc.create(word="  start ", funnel_id=funnel.id)
    assert t.word == "start"


@pytest.mark.asyncio
async def test_create_duplicate_raises_conflict(session, make):
    funnel = await make.funnel()
    svc = FunnelTriggersService(session)
    await svc.create(word="dupe", funnel_id=funnel.id)
    await session.flush()
    with pytest.raises(TriggerConflictError):
        await svc.create(word="DUPE", funnel_id=funnel.id)


@pytest.mark.asyncio
async def test_validation_min_length(session, make):
    funnel = await make.funnel()
    svc = FunnelTriggersService(session)
    with pytest.raises(InvalidTriggerWordError):
        await svc.create(word="a", funnel_id=funnel.id)


@pytest.mark.asyncio
async def test_validation_max_length(session, make):
    funnel = await make.funnel()
    svc = FunnelTriggersService(session)
    with pytest.raises(InvalidTriggerWordError):
        await svc.create(word="x" * 65, funnel_id=funnel.id)


@pytest.mark.asyncio
async def test_validation_no_spaces_inside(session, make):
    funnel = await make.funnel()
    svc = FunnelTriggersService(session)
    with pytest.raises(InvalidTriggerWordError):
        await svc.create(word="two words", funnel_id=funnel.id)


@pytest.mark.asyncio
async def test_find_by_word_case_insensitive(session, make):
    funnel = await make.funnel()
    svc = FunnelTriggersService(session)
    await svc.create(word="кожа", funnel_id=funnel.id)
    await session.flush()

    for variant in ["КОЖА", "кожа", "Кожа", "  кожа  "]:
        found = await svc.find_by_word(variant)
        assert found is not None, f"Не нашёл {variant!r}"


@pytest.mark.asyncio
async def test_find_by_word_returns_none_when_inactive(session, make):
    funnel = await make.funnel()
    svc = FunnelTriggersService(session)
    t = await svc.create(word="test_trig", funnel_id=funnel.id)
    t.is_active = False
    await session.flush()
    assert await svc.find_by_word("test_trig") is None


@pytest.mark.asyncio
async def test_find_by_word_empty_input(session):
    svc = FunnelTriggersService(session)
    assert await svc.find_by_word("") is None
    assert await svc.find_by_word("   ") is None


@pytest.mark.asyncio
async def test_increment_use_count(session, make):
    funnel = await make.funnel()
    svc = FunnelTriggersService(session)
    t = await svc.create(word="counter", funnel_id=funnel.id)
    await session.flush()
    assert t.use_count == 0
    await svc.increment_use_count(t.id)
    await svc.increment_use_count(t.id)
    await session.refresh(t)
    assert t.use_count == 2


@pytest.mark.asyncio
async def test_update_word_to_new_unique(session, make):
    funnel = await make.funnel()
    svc = FunnelTriggersService(session)
    t = await svc.create(word="old1", funnel_id=funnel.id)
    await session.flush()
    updated = await svc.update(t.id, word="new1")
    assert updated.word == "new1"


@pytest.mark.asyncio
async def test_update_word_to_existing_409(session, make):
    funnel = await make.funnel()
    svc = FunnelTriggersService(session)
    t1 = await svc.create(word="aaa1", funnel_id=funnel.id)
    t2 = await svc.create(word="bbb1", funnel_id=funnel.id)
    await session.flush()
    with pytest.raises(TriggerConflictError):
        await svc.update(t2.id, word="aaa1")


@pytest.mark.asyncio
async def test_update_unknown_returns_none(session):
    svc = FunnelTriggersService(session)
    assert await svc.update(99999, is_active=False) is None


@pytest.mark.asyncio
async def test_delete(session, make):
    funnel = await make.funnel()
    svc = FunnelTriggersService(session)
    t = await svc.create(word="todelete", funnel_id=funnel.id)
    await session.flush()
    ok = await svc.delete(t.id)
    assert ok is True
    assert await svc.delete(99999) is False
