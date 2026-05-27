"""Тесты гейтинга бэкенда: сборка /api-роутера по флагам + require_feature."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api.deps import require_feature
from app.core.features import FEATURE_REGISTRY, current_features, resolve
from app.main import FEATURE_ROUTERS, build_api_router


def _paths(features: dict[str, bool]) -> set[str]:
    router = build_api_router(features)
    return {getattr(r, "path", "") for r in router.routes}


def test_feature_routers_cover_registry_exactly():
    """Карта FEATURE_ROUTERS не должна разъезжаться с реестром фич."""
    assert set(FEATURE_ROUTERS) == set(FEATURE_REGISTRY)


def test_all_features_on_includes_funnels_and_core():
    paths = _paths(resolve({}))
    assert any(p.startswith("/api/funnels") for p in paths)
    assert any(p.startswith("/api/products") for p in paths)
    assert "/api/stats/overview" in paths
    assert "/api/healthz" in paths
    assert "/api/config/features" in paths


def test_funnels_off_removes_subsystem_keeps_core():
    paths = _paths(resolve({"funnels": False}))
    # выключенный хаб и всё, что от него зависит — отсутствуют
    for prefix in ("/api/funnels", "/api/funnel-triggers", "/api/quizzes",
                   "/api/forms", "/api/lead-magnets", "/api/funnel-steps",
                   "/api/funnel-entries"):
        assert not any(p.startswith(prefix) for p in paths), prefix
    # ядро и независимые фичи остаются
    assert any(p.startswith("/api/products") for p in paths)
    assert "/api/stats/overview" in paths
    assert any(p.startswith("/api/payments") for p in paths)  # monetization on


def test_analytics_off_keeps_overview_but_drops_deep_stats():
    paths = _paths(resolve({"analytics": False}))
    assert "/api/stats/overview" in paths            # ядро
    assert not any(p.startswith("/api/stats/sources") for p in paths)
    assert not any(p.startswith("/api/stats/timeline") for p in paths)


def test_monetization_off_removes_payments_and_subscriptions():
    paths = _paths(resolve({"monetization": False}))
    assert not any(p.startswith("/api/payments") for p in paths)
    assert not any(p.startswith("/api/subscriptions") for p in paths)


@pytest.mark.asyncio
async def test_require_feature_blocks_when_disabled(monkeypatch):
    monkeypatch.setenv("FEATURE_ANALYTICS", "false")
    current_features.cache_clear()
    try:
        check = require_feature("analytics")
        with pytest.raises(HTTPException) as exc:
            await check()
        assert exc.value.status_code == 404
    finally:
        current_features.cache_clear()


@pytest.mark.asyncio
async def test_require_feature_passes_when_enabled():
    current_features.cache_clear()
    check = require_feature("analytics")
    assert await check() is None  # не бросает
