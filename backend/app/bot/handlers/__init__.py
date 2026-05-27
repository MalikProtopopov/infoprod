"""Пакет хендлеров бота, разнесённый по фичам.

build_dispatcher() собирает shared Dispatcher: ядро всегда + фичевые роутеры
по флагам. Имена реэкспортируются для обратной совместимости (manager и тесты
импортируют из app.bot.handlers).
"""
from __future__ import annotations

from aiogram import Dispatcher

from app.bot.handlers import common, core, forms, funnels, leads, quizzes
from app.bot.handlers.common import (  # noqa: F401  back-compat реэкспорт
    CURRENT_LINK_TTL,
    MAIN_MENU_BTN,
    _product_kb,
    _send_catalog,
    _set_current_link,
    _set_first_touch,
    _upsert_user,
)
from app.bot.handlers.core import (  # noqa: F401
    cb_main_menu,
    cb_product,
    cb_unsubscribe,
    cmd_help,
    cmd_my,
    on_text_message,
    start_plain,
    start_with_arg,
)
from app.bot.handlers.forms import cb_form_cancel, cb_form_start  # noqa: F401
from app.bot.handlers.funnels import cb_funnel_start  # noqa: F401
from app.bot.handlers.leads import cb_lead  # noqa: F401
from app.bot.handlers.quizzes import cb_quiz_answer, cb_quiz_start  # noqa: F401
from app.core.features import current_features


# Фича → её бот-роутер. Ядро (core) подключается всегда.
_FEATURE_ROUTERS = {
    "leads": leads.router,
    "funnels": funnels.router,
    "quizzes": quizzes.router,
    "forms": forms.router,
}


def enabled_routers(feats: dict) -> list:
    """Список роутеров под текущий набор фич (ядро + включённые фичевые).

    Вынесено отдельно, чтобы тестировать выбор без attach: роутеры —
    модульные синглтоны, их нельзя присоединить к двум Dispatcher'ам.
    """
    routers = [core.router]
    for key, r in _FEATURE_ROUTERS.items():
        if feats.get(key):
            routers.append(r)
    return routers


def build_dispatcher() -> Dispatcher:
    """Один shared Dispatcher; фичевые роутеры подключаются по флагам.

    Вызывается один раз (manager кэширует через _get_shared_dp): роутеры —
    синглтоны и не могут быть присоединены к нескольким Dispatcher'ам.
    """
    dp = Dispatcher()
    for r in enabled_routers(current_features()):
        dp.include_router(r)
    return dp
