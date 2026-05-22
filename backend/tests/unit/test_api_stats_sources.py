"""API: GET /api/stats/sources — агрегация по источникам.

Часть тестов с inline async_sessionmaker помечена xfail — переписать в Phase 2.
"""
from __future__ import annotations

from datetime import datetime, timezone  # noqa: F401

import pytest


@pytest.mark.asyncio
async def test_stats_sources_returns_totals_shape(admin_client, clean_db):
    r = await admin_client.get("/api/stats/sources?group_by=source")
    assert r.status_code == 200
    body = r.json()
    assert "rows" in body
    assert "totals" in body
    assert "from" in body
    assert "to" in body
    assert body["group_by"] == "source"
    for k in ("clicks", "unique_users", "leads", "payments", "revenue"):
        assert k in body["totals"]


@pytest.mark.asyncio
async def test_stats_sources_with_clicks(admin_client, make_committed, clean_db):
    """Реальный кейс: ссылка с кликами должна попасть в rows."""
    product = await make_committed.product()
    await make_committed.tracking_link(
        product=product, utm_source="instagram", click_count=42, unique_users=20,
    )

    r = await admin_client.get("/api/stats/sources?group_by=source")
    body = r.json()
    sources = {row.get("source") for row in body["rows"]}
    assert "instagram" in sources
    ig = next(row for row in body["rows"] if row.get("source") == "instagram")
    assert ig["clicks"] == 42
    assert ig["unique_users"] == 20


@pytest.mark.asyncio
async def test_stats_sources_group_by_campaign(admin_client, make_committed, clean_db):
    product = await make_committed.product()
    await make_committed.tracking_link(
        product=product, utm_source="ig", utm_campaign="spring", click_count=10,
    )
    await make_committed.tracking_link(
        product=product, utm_source="ig", utm_campaign="black_friday", click_count=20,
    )

    r = await admin_client.get("/api/stats/sources?group_by=campaign")
    body = r.json()
    assert body["group_by"] == "campaign"
    camps = {row.get("campaign") for row in body["rows"]}
    assert "spring" in camps
    assert "black_friday" in camps


@pytest.mark.asyncio
async def test_stats_sources_invalid_group_by_returns_422(admin_client, clean_db):
    r = await admin_client.get("/api/stats/sources?group_by=nope")
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_stats_sources_requires_auth(api_client):
    r = await api_client.get("/api/stats/sources")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_stats_overview_returns_expected_shape(admin_client, clean_db):
    r = await admin_client.get("/api/stats/overview")
    assert r.status_code == 200
    body = r.json()
    for k in ("users", "leads", "subscriptions", "revenue", "catalog",
              "recent_leads", "recent_payments"):
        assert k in body
