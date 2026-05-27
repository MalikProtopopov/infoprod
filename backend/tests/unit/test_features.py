"""Тесты резолвера фичефлагов: дефолты + каскад зависимостей."""
from __future__ import annotations

import pytest

from app.core import features
from app.core.features import FEATURE_REGISTRY, current_features, resolve


def test_registry_matches_canonical_keys():
    """Список ключей зафиксирован. При изменении — синхронизировать фронт
    (admin/lib/features.ts::FEATURE_KEYS) и __tests__/lib/features.test.ts."""
    assert set(FEATURE_REGISTRY) == {
        "leads",
        "monetization",
        "tracking_links",
        "analytics",
        "funnels",
        "funnel_triggers",
        "quizzes",
        "forms",
        "lead_magnets",
    }


def test_default_all_enabled():
    """Без указанных флагов все фичи включены."""
    eff = resolve({})
    assert all(eff.values())
    assert set(eff) == set(FEATURE_REGISTRY)


def test_disabling_funnels_cascades_to_dependents():
    """Выключение хаба-воронок гасит всё, что доставляется через шаги."""
    eff = resolve({"funnels": False})
    assert eff["funnels"] is False
    for dep in ("funnel_triggers", "quizzes", "forms", "lead_magnets"):
        assert eff[dep] is False, dep
    # независимые фичи остаются включёнными
    for indep in ("leads", "monetization", "tracking_links", "analytics"):
        assert eff[indep] is True, indep


def test_enabling_dependent_without_dependency_is_suppressed():
    """Нельзя включить quizzes без funnels — резолвер гасит."""
    eff = resolve({"quizzes": True, "funnels": False})
    assert eff["quizzes"] is False


def test_forms_requires_both_funnels_and_leads():
    assert resolve({"funnels": True, "leads": False})["forms"] is False
    assert resolve({"funnels": False, "leads": True})["forms"] is False
    assert resolve({"funnels": True, "leads": True})["forms"] is True


def test_independent_feature_toggles_alone():
    eff = resolve({"analytics": False})
    assert eff["analytics"] is False
    assert eff["funnels"] is True  # не затронуто


@pytest.mark.parametrize("val,expected", [
    ("true", True), ("1", True), ("yes", True), ("on", True),
    ("false", False), ("0", False), ("no", False), ("off", False),
])
def test_env_parsing(monkeypatch, val, expected):
    monkeypatch.setenv("FEATURE_ANALYTICS", val)
    current_features.cache_clear()
    try:
        assert current_features()["analytics"] is expected
    finally:
        current_features.cache_clear()


def test_env_garbage_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("FEATURE_FUNNELS", "maybe")
    current_features.cache_clear()
    try:
        assert current_features()["funnels"] is True  # мусор → дефолт
    finally:
        current_features.cache_clear()


def test_is_enabled_helper(monkeypatch):
    monkeypatch.setenv("FEATURE_FUNNELS", "false")
    current_features.cache_clear()
    try:
        assert features.is_enabled("funnels") is False
        assert features.is_enabled("quizzes") is False  # каскад
    finally:
        current_features.cache_clear()
