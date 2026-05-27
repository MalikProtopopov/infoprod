"""Тесты bot/handlers.py — резолвер /start, first-touch, cb_lead с TTL."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Message, User as TgUser

from app.bot.handlers import (
    CURRENT_LINK_TTL,
    _set_current_link,
    _set_first_touch,
    _upsert_user,
    cb_lead,
    start_with_arg,
)


# ──────── helpers ────────


def _make_message(*, tg_id: int = 999, first_name: str = "Tester", username: str = "tester", language: str = "ru"):
    msg = MagicMock(spec=Message)
    msg.from_user = TgUser(
        id=tg_id, is_bot=False, first_name=first_name, last_name=None,
        username=username, language_code=language,
    )
    msg.answer = AsyncMock()
    return msg


def _make_callback(*, tg_id: int = 999, data: str = "lead:1"):
    cb = MagicMock()
    cb.from_user = TgUser(id=tg_id, is_bot=False, first_name="X", username="xu")
    cb.data = data
    cb.answer = AsyncMock()
    cb.message = MagicMock()
    cb.message.answer = AsyncMock()
    return cb


def _make_command(args: str | None):
    cmd = MagicMock()
    cmd.args = args
    return cmd


def _make_aiogram_bot(telegram_bot_id: int):
    bot = MagicMock()
    me = MagicMock()
    me.id = telegram_bot_id
    bot.get_me = AsyncMock(return_value=me)
    return bot


def _make_test_sessionmaker(session):
    """Async context manager возвращающий нашу тестовую сессию."""
    class _CM:
        async def __aenter__(self_):
            return session
        async def __aexit__(self_, *_):
            return False
    return lambda *args, **kwargs: _CM()


# ──────── _upsert_user ────────


@pytest.mark.asyncio
async def test_upsert_user_creates_new(session):
    msg = _make_message(tg_id=111, first_name="Alice", username="alice", language="en")
    user, is_new = await _upsert_user(session, msg)

    assert is_new is True
    assert user.telegram_user_id == 111
    assert user.first_name == "Alice"
    assert user.username == "alice"
    assert user.language_code == "en"


@pytest.mark.asyncio
async def test_upsert_user_updates_existing(session, make):
    user = await make.user(telegram_user_id=111, username="oldname", first_name="Old")

    msg = _make_message(tg_id=111, first_name="New", username="newname")
    result, is_new = await _upsert_user(session, msg)

    assert is_new is False
    assert result.id == user.id
    assert result.username == "newname"
    assert result.first_name == "New"


# ──────── _set_first_touch ────────


@pytest.mark.asyncio
async def test_first_touch_writes_attribution(session, make):
    user = await make.user()
    bot = await make.bot()
    product = await make.product()
    link = await make.tracking_link(
        utm_source="instagram", utm_medium="reels", utm_campaign="spring",
    )

    await _set_first_touch(
        session, user_id=user.id, bot_id=bot.id,
        product_id=product.id, tracking_link=link,
    )
    await session.refresh(user)
    assert user.first_bot_id == bot.id
    assert user.first_product_id == product.id
    assert user.first_tracking_link_id == link.id
    assert user.first_utm_source == "instagram"
    assert user.first_utm_medium == "reels"
    assert user.first_utm_campaign == "spring"


@pytest.mark.asyncio
async def test_first_touch_is_idempotent(session, make):
    user = await make.user()
    bot1 = await make.bot()
    bot2 = await make.bot()

    await _set_first_touch(session, user_id=user.id, bot_id=bot1.id, product_id=None, tracking_link=None)
    await session.refresh(user)
    assert user.first_bot_id == bot1.id

    await _set_first_touch(session, user_id=user.id, bot_id=bot2.id, product_id=None, tracking_link=None)
    await session.refresh(user)
    assert user.first_bot_id == bot1.id  # не перезаписался


# ──────── _set_current_link ────────


@pytest.mark.asyncio
async def test_set_current_link(session, make):
    user = await make.user()
    link = await make.tracking_link()

    await _set_current_link(session, user.id, link.id)
    await session.refresh(user)
    assert user.current_tracking_link_id == link.id
    assert user.current_link_set_at is not None
    now = datetime.now(tz=timezone.utc)
    age = (now - user.current_link_set_at).total_seconds()
    assert 0 <= age < 5


# ──────── start_with_arg ────────


@pytest.mark.asyncio
async def test_start_with_slug_resolves_tracking_link(session, make, monkeypatch):
    bot_model = await make.bot()
    channel = await make.channel(bot=bot_model)
    product = await make.product(channel=channel)
    link = await make.tracking_link(slug="mySlug12", product=product, utm_source="ig")
    await session.commit()

    # Хендлеры разнесены по сабмодулям; SessionLocal патчим в обоих,
    # где он используется (core: /start, leads: cb_lead).
    from app.bot.handlers import core as _hc, leads as _hl
    _sm = _make_test_sessionmaker(session)
    monkeypatch.setattr(_hc, "SessionLocal", _sm)
    monkeypatch.setattr(_hl, "SessionLocal", _sm)

    msg = _make_message(tg_id=999)
    cmd = _make_command("mySlug12")
    aiogram_bot = _make_aiogram_bot(bot_model.telegram_bot_id)

    await start_with_arg(msg, cmd, aiogram_bot)

    await session.refresh(link)
    assert link.click_count == 1
    assert link.unique_users == 1

    from sqlalchemy import select
    from app.models.user import User
    user = (await session.execute(select(User).where(User.telegram_user_id == 999))).scalar_one()
    assert user.first_utm_source == "ig"
    assert user.first_tracking_link_id == link.id
    assert user.first_product_id == product.id
    assert user.current_tracking_link_id == link.id


@pytest.mark.asyncio
async def test_start_with_invalid_slug_shows_expired_message(session, make, monkeypatch):
    bot_model = await make.bot()
    await make.product(channel=await make.channel(bot=bot_model))
    await session.commit()

    # Хендлеры разнесены по сабмодулям; SessionLocal патчим в обоих,
    # где он используется (core: /start, leads: cb_lead).
    from app.bot.handlers import core as _hc, leads as _hl
    _sm = _make_test_sessionmaker(session)
    monkeypatch.setattr(_hc, "SessionLocal", _sm)
    monkeypatch.setattr(_hl, "SessionLocal", _sm)

    msg = _make_message(tg_id=999)
    cmd = _make_command("nosuchslug")
    aiogram_bot = _make_aiogram_bot(bot_model.telegram_bot_id)
    await start_with_arg(msg, cmd, aiogram_bot)

    sent_texts = [c.args[0] for c in msg.answer.call_args_list if c.args]
    assert any("устарела" in t.lower() or "недоступна" in t.lower() for t in sent_texts)


@pytest.mark.asyncio
async def test_start_falls_back_to_product_code(session, make, monkeypatch):
    bot_model = await make.bot()
    product = await make.product(code="yogapro", channel=await make.channel(bot=bot_model))
    await session.commit()

    # Хендлеры разнесены по сабмодулям; SessionLocal патчим в обоих,
    # где он используется (core: /start, leads: cb_lead).
    from app.bot.handlers import core as _hc, leads as _hl
    _sm = _make_test_sessionmaker(session)
    monkeypatch.setattr(_hc, "SessionLocal", _sm)
    monkeypatch.setattr(_hl, "SessionLocal", _sm)

    msg = _make_message(tg_id=999)
    cmd = _make_command("yogapro")
    aiogram_bot = _make_aiogram_bot(bot_model.telegram_bot_id)
    await start_with_arg(msg, cmd, aiogram_bot)

    from sqlalchemy import select
    from app.models.user import User
    user = (await session.execute(select(User).where(User.telegram_user_id == 999))).scalar_one()
    assert user.first_product_id == product.id
    assert user.first_tracking_link_id is None


@pytest.mark.asyncio
async def test_start_with_deactivated_link_shows_expired(session, make, monkeypatch):
    bot_model = await make.bot()
    product = await make.product(channel=await make.channel(bot=bot_model))
    await make.tracking_link(slug="deadslug", product=product, is_active=False)
    await session.commit()

    # Хендлеры разнесены по сабмодулям; SessionLocal патчим в обоих,
    # где он используется (core: /start, leads: cb_lead).
    from app.bot.handlers import core as _hc, leads as _hl
    _sm = _make_test_sessionmaker(session)
    monkeypatch.setattr(_hc, "SessionLocal", _sm)
    monkeypatch.setattr(_hl, "SessionLocal", _sm)

    msg = _make_message(tg_id=999)
    cmd = _make_command("deadslug")
    aiogram_bot = _make_aiogram_bot(bot_model.telegram_bot_id)
    await start_with_arg(msg, cmd, aiogram_bot)

    sent_texts = [c.args[0] for c in msg.answer.call_args_list if c.args]
    assert any("устарела" in t.lower() or "недоступна" in t.lower() for t in sent_texts)


# ──────── cb_lead ────────


@pytest.mark.asyncio
async def test_cb_lead_creates_lead_with_fresh_attribution(session, make, monkeypatch):
    bot_model = await make.bot()
    product = await make.product(channel=await make.channel(bot=bot_model))
    link = await make.tracking_link(product=product, utm_source="yt", utm_medium="video")
    now = datetime.now(tz=timezone.utc)
    user = await make.user(
        telegram_user_id=777,
        current_tracking_link_id=link.id,
        current_link_set_at=now - timedelta(minutes=5),
    )
    await session.commit()

    # Хендлеры разнесены по сабмодулям; SessionLocal патчим в обоих,
    # где он используется (core: /start, leads: cb_lead).
    from app.bot.handlers import core as _hc, leads as _hl
    _sm = _make_test_sessionmaker(session)
    monkeypatch.setattr(_hc, "SessionLocal", _sm)
    monkeypatch.setattr(_hl, "SessionLocal", _sm)

    cb = _make_callback(tg_id=777, data=f"lead:{product.id}")
    await cb_lead(cb)

    from sqlalchemy import select
    from app.models.lead import Lead
    lead = (await session.execute(select(Lead).where(Lead.user_id == user.id))).scalar_one()
    assert lead.tracking_link_id == link.id
    assert lead.utm_source == "yt"
    assert lead.utm_medium == "video"


@pytest.mark.asyncio
async def test_cb_lead_ignores_expired_ttl(session, make, monkeypatch):
    bot_model = await make.bot()
    product = await make.product(channel=await make.channel(bot=bot_model))
    link = await make.tracking_link(product=product, utm_source="ig")
    now = datetime.now(tz=timezone.utc)
    user = await make.user(
        telegram_user_id=778,
        current_tracking_link_id=link.id,
        current_link_set_at=now - CURRENT_LINK_TTL - timedelta(minutes=1),
    )
    await session.commit()

    # Хендлеры разнесены по сабмодулям; SessionLocal патчим в обоих,
    # где он используется (core: /start, leads: cb_lead).
    from app.bot.handlers import core as _hc, leads as _hl
    _sm = _make_test_sessionmaker(session)
    monkeypatch.setattr(_hc, "SessionLocal", _sm)
    monkeypatch.setattr(_hl, "SessionLocal", _sm)

    cb = _make_callback(tg_id=778, data=f"lead:{product.id}")
    await cb_lead(cb)

    from sqlalchemy import select
    from app.models.lead import Lead
    lead = (await session.execute(select(Lead).where(Lead.user_id == user.id))).scalar_one()
    assert lead.tracking_link_id is None
    assert lead.utm_source is None


@pytest.mark.asyncio
async def test_cb_lead_with_deactivated_link_no_attribution(session, make, monkeypatch):
    bot_model = await make.bot()
    product = await make.product(channel=await make.channel(bot=bot_model))
    link = await make.tracking_link(product=product, utm_source="ig", is_active=False)
    now = datetime.now(tz=timezone.utc)
    user = await make.user(
        telegram_user_id=779,
        current_tracking_link_id=link.id,
        current_link_set_at=now - timedelta(minutes=5),
    )
    await session.commit()

    # Хендлеры разнесены по сабмодулям; SessionLocal патчим в обоих,
    # где он используется (core: /start, leads: cb_lead).
    from app.bot.handlers import core as _hc, leads as _hl
    _sm = _make_test_sessionmaker(session)
    monkeypatch.setattr(_hc, "SessionLocal", _sm)
    monkeypatch.setattr(_hl, "SessionLocal", _sm)

    cb = _make_callback(tg_id=779, data=f"lead:{product.id}")
    await cb_lead(cb)

    from sqlalchemy import select
    from app.models.lead import Lead
    lead = (await session.execute(select(Lead).where(Lead.user_id == user.id))).scalar_one()
    assert lead.tracking_link_id is None
    assert lead.utm_source is None
