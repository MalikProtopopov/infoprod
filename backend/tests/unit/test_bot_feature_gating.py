"""Гейтинг бота по фичефлагам: клавиатуры и ранние guard'ы в колбэках.

Все проверки чистые — guard'ы срабатывают ДО обращения к БД, поэтому контейнер
не нужен.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import User as TgUser

from app.bot.handlers import (
    _product_kb,
    cb_form_start,
    cb_funnel_start,
    cb_lead,
    cb_quiz_start,
)
from app.core.features import current_features


def _flat_callbacks(kb) -> list[str | None]:
    return [b.callback_data for row in kb.inline_keyboard for b in row]


def _make_cb(data: str = "x:1"):
    cb = MagicMock()
    cb.from_user = TgUser(id=1, is_bot=False, first_name="X", username="xu")
    cb.data = data
    cb.answer = AsyncMock()
    cb.message = MagicMock()
    cb.message.answer = AsyncMock()
    return cb


@pytest.fixture
def _features(monkeypatch):
    """Хелпер: выставить FEATURE_* и сбросить кэш; восстановить после теста."""
    def _set(**flags: bool):
        for key, val in flags.items():
            monkeypatch.setenv(f"FEATURE_{key.upper()}", "true" if val else "false")
        current_features.cache_clear()
    yield _set
    current_features.cache_clear()


def test_product_kb_includes_lead_button_when_leads_on(_features):
    _features(leads=True)
    cbs = _flat_callbacks(_product_kb(7))
    assert "lead:7" in cbs
    assert "menu:main" in cbs


def test_product_kb_hides_lead_button_when_leads_off(_features):
    _features(leads=False)
    cbs = _flat_callbacks(_product_kb(7))
    assert "lead:7" not in cbs
    assert "menu:main" in cbs  # навигация остаётся


@pytest.mark.asyncio
async def test_cb_lead_blocked_when_leads_off(_features):
    _features(leads=False)
    cb = _make_cb("lead:1")
    await cb_lead(cb)
    cb.answer.assert_awaited()  # ответил «Недоступно», не упал
    cb.message.answer.assert_not_called()  # заявка НЕ создана/не подтверждена


@pytest.mark.asyncio
async def test_cb_funnel_start_blocked_when_funnels_off(_features):
    _features(funnels=False)
    cb = _make_cb("funnel:start:1")
    await cb_funnel_start(cb)
    cb.answer.assert_awaited()


@pytest.mark.asyncio
async def test_cb_quiz_start_blocked_when_quizzes_off(_features):
    # quizzes зависит от funnels → выключаем хаб, каскад гасит квизы
    _features(funnels=False)
    cb = _make_cb("quiz:start:1")
    await cb_quiz_start(cb)
    cb.answer.assert_awaited()


@pytest.mark.asyncio
async def test_cb_form_start_blocked_when_forms_off(_features):
    _features(forms=False)
    cb = _make_cb("form:start:1")
    await cb_form_start(cb)
    cb.answer.assert_awaited()


def test_enabled_routers_selected_by_flags():
    """Выбор бот-роутеров по фичам (без attach — роутеры синглтоны)."""
    from app.bot.handlers import enabled_routers
    from app.core.features import resolve

    full = enabled_routers(resolve({}))
    assert {r.name for r in full} == {
        "public_core", "public_leads", "public_funnels", "public_quizzes", "public_forms",
    }

    # funnels off → каскад гасит quizzes/forms/...; leads off отдельно
    minimal = enabled_routers(resolve({"funnels": False, "leads": False}))
    assert [r.name for r in minimal] == ["public_core"]
