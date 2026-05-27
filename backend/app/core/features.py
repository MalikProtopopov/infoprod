"""Модульные фичефлаги.

Единственный источник истины о том, какие фичи включены в текущем деплое.
Флаги — runtime-only: схема БД всегда полная, выключение лишь гасит точки входа
(роутеры, джобы scheduler, хуки/клавиатуры бота, пункты меню и секции в админке).

Формат env: по одной булевой переменной на фичу с префиксом FEATURE_, напр.
    FEATURE_FUNNELS=false
    FEATURE_LEAD_MAGNETS=false
Значение по умолчанию для всех фич — включено (True), чтобы существующие деплои
не менялись, пока клиент явно не отключит фичу.

Зависимости резолвятся каскадно: фича эффективно включена, только если включена
сама И все её зависимости (см. resolve()). Это гарантирует, что, например,
выключение `funnels` автоматически выключает `quizzes`/`forms`/`lead_magnets`/
`funnel_triggers`, которые доставляются через шаги воронки.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class FeatureDef:
    key: str
    label: str
    depends_on: tuple[str, ...] = ()
    default: bool = True


# Реестр отключаемых фич. Ядро (auth/боты/каналы/продукты/юзеры) флага не имеет.
FEATURE_REGISTRY: dict[str, FeatureDef] = {
    "leads": FeatureDef("leads", "Заявки"),
    "monetization": FeatureDef("monetization", "Платежи и подписки"),
    "tracking_links": FeatureDef("tracking_links", "Трекинг-ссылки"),
    "analytics": FeatureDef("analytics", "Аналитика"),
    "funnels": FeatureDef("funnels", "Воронки"),
    "funnel_triggers": FeatureDef("funnel_triggers", "Кодовые слова", ("funnels",)),
    "quizzes": FeatureDef("quizzes", "Квизы", ("funnels",)),
    "forms": FeatureDef("forms", "Формы", ("funnels", "leads")),
    "lead_magnets": FeatureDef("lead_magnets", "Лидмагниты", ("funnels",)),
}

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def resolve(raw: dict[str, bool]) -> dict[str, bool]:
    """Применяет дефолты и каскад зависимостей.

    Фича эффективно включена ТОЛЬКО если включена сама И все её зависимости.
    Выключение зависимости каскадно гасит зависимые — итерируем до стабилизации
    (на случай транзитивных цепочек A→B→C).
    """
    eff: dict[str, bool] = {
        key: raw.get(key, d.default) for key, d in FEATURE_REGISTRY.items()
    }
    changed = True
    while changed:
        changed = False
        for key, d in FEATURE_REGISTRY.items():
            if eff[key] and any(not eff.get(dep, False) for dep in d.depends_on):
                eff[key] = False
                changed = True
    return eff


def _read_env() -> dict[str, bool]:
    """Читает FEATURE_* из окружения. Неуказанные фичи остаются на дефолте."""
    raw: dict[str, bool] = {}
    for key in FEATURE_REGISTRY:
        val = os.environ.get(f"FEATURE_{key.upper()}")
        if val is None:
            continue
        norm = val.strip().lower()
        if norm in _TRUE:
            raw[key] = True
        elif norm in _FALSE:
            raw[key] = False
        # иначе игнорируем мусорное значение → останется дефолт
    return raw


@lru_cache(maxsize=1)
def current_features() -> dict[str, bool]:
    """Эффективный набор фич (кэшируется на процесс).

    В тестах, меняющих FEATURE_* через monkeypatch, вызывать
    current_features.cache_clear() после смены окружения.
    """
    return resolve(_read_env())


def is_enabled(key: str) -> bool:
    return current_features().get(key, False)
