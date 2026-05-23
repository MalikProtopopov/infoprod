"""Тесты для analytics endpoints: /timeline, /funnels/{id}/conversion, /funnels/summary, /health."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest


# ============================================================
# /stats/timeline
# ============================================================

@pytest.mark.asyncio
async def test_timeline_requires_auth(api_client, clean_db):
    r = await api_client.get("/api/stats/timeline")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_timeline_empty_returns_valid_shape(admin_client, clean_db):
    r = await admin_client.get("/api/stats/timeline")
    assert r.status_code == 200
    body = r.json()
    assert body["granularity"] == "day"
    assert body["dimension"] == "source"
    assert body["attribution"] == "last"
    assert body["points"] == []
    assert body["dims"] == []
    assert body["buckets"] == []
    assert body["totals"] == {"leads": 0, "payments": 0, "revenue": "0"}


@pytest.mark.asyncio
async def test_timeline_groups_leads_by_source(admin_client, make_committed, clean_db):
    user = await make_committed.user()
    product = await make_committed.product()
    await make_committed.lead(user=user, product=product, utm_source="instagram")
    await make_committed.lead(user=user, product=product, utm_source="instagram")
    await make_committed.lead(user=user, product=product, utm_source="youtube")

    r = await admin_client.get("/api/stats/timeline?dimension=source")
    body = r.json()
    assert body["totals"]["leads"] == 3
    # Должны быть как минимум 2 уникальных dim
    assert set(body["dims"]) >= {"instagram", "youtube"}


@pytest.mark.asyncio
async def test_timeline_first_touch_uses_user_first_utm(admin_client, make_committed, clean_db):
    """В режиме first-touch — берётся User.first_utm_source, а не Lead.utm_source."""
    user = await make_committed.user(first_utm_source="initial_fb_ad")
    product = await make_committed.product()
    # Лид без utm — но юзер пришёл с fb_ad
    await make_committed.lead(user=user, product=product, utm_source=None)

    r = await admin_client.get("/api/stats/timeline?attribution=first")
    body = r.json()
    assert body["totals"]["leads"] == 1
    assert "initial_fb_ad" in body["dims"]


@pytest.mark.asyncio
async def test_timeline_product_filter(admin_client, make_committed, clean_db):
    user = await make_committed.user()
    p1 = await make_committed.product()
    p2 = await make_committed.product()
    await make_committed.lead(user=user, product=p1)
    await make_committed.lead(user=user, product=p2)

    r = await admin_client.get(f"/api/stats/timeline?product_id={p1.id}")
    body = r.json()
    assert body["totals"]["leads"] == 1


@pytest.mark.asyncio
async def test_timeline_granularity_week(admin_client, make_committed, clean_db):
    user = await make_committed.user()
    product = await make_committed.product()
    await make_committed.lead(user=user, product=product)
    r = await admin_client.get("/api/stats/timeline?granularity=week")
    assert r.status_code == 200
    assert r.json()["granularity"] == "week"


@pytest.mark.asyncio
async def test_timeline_payments_included_with_revenue(admin_client, make_committed, clean_db):
    user = await make_committed.user()
    product = await make_committed.product()
    await make_committed.payment(user=user, product=product, amount=1500)
    r = await admin_client.get("/api/stats/timeline?dimension=none")
    body = r.json()
    assert body["totals"]["payments"] == 1
    assert float(body["totals"]["revenue"]) == 1500.0


@pytest.mark.asyncio
async def test_timeline_invalid_granularity_422(admin_client, clean_db):
    r = await admin_client.get("/api/stats/timeline?granularity=invalid")
    assert r.status_code == 422


# ============================================================
# /stats/funnels/{id}/conversion
# ============================================================

@pytest.mark.asyncio
async def test_funnel_conversion_404_for_unknown(admin_client, clean_db):
    r = await admin_client.get("/api/stats/funnels/99999/conversion")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_funnel_conversion_empty(admin_client, make_committed, clean_db):
    funnel = await make_committed.funnel()
    await make_committed.funnel_step(funnel=funnel, order_idx=0)
    await make_committed.funnel_step(funnel=funnel, order_idx=1)

    r = await admin_client.get(f"/api/stats/funnels/{funnel.id}/conversion")
    body = r.json()
    assert body["funnel_id"] == funnel.id
    assert body["total_entered"] == 0
    assert body["completed"] == 0
    assert body["successful_outcomes"] == 0
    assert len(body["steps"]) == 2
    assert body["steps"][0]["delivered"] == 0


@pytest.mark.asyncio
async def test_funnel_conversion_excludes_manual_entries(admin_client, make_committed, clean_db):
    """source='manual' (test-run) не должны попадать в метрики."""
    funnel = await make_committed.funnel()
    await make_committed.funnel_step(funnel=funnel, order_idx=0)
    user = await make_committed.user()
    # Реальный entry
    await make_committed.funnel_entry(funnel=funnel, user=user, source="tracking_link")
    # Тестовый entry — должен быть исключён
    await make_committed.funnel_entry(funnel=funnel, user=user, source="manual")

    r = await admin_client.get(f"/api/stats/funnels/{funnel.id}/conversion")
    body = r.json()
    assert body["total_entered"] == 1  # без manual


@pytest.mark.asyncio
async def test_funnel_conversion_counts_cancelled_by_payment_as_success(admin_client, make_committed, clean_db):
    """Воронка с cancel_on_payment=True — cancelled с reason='paid' это успех."""
    funnel = await make_committed.funnel()
    await make_committed.funnel_step(funnel=funnel, order_idx=0)
    user = await make_committed.user()
    await make_committed.funnel_entry(
        funnel=funnel, user=user,
        source="tracking_link",
        status="cancelled", cancel_reason="paid",
    )

    r = await admin_client.get(f"/api/stats/funnels/{funnel.id}/conversion")
    body = r.json()
    assert body["cancelled_by_payment"] == 1
    assert body["successful_outcomes"] == 1


# ============================================================
# /stats/funnels/summary
# ============================================================

@pytest.mark.asyncio
async def test_funnels_summary_empty(admin_client, clean_db):
    r = await admin_client.get("/api/stats/funnels/summary")
    assert r.status_code == 200
    assert r.json()["rows"] == []


@pytest.mark.asyncio
async def test_funnels_summary_returns_per_funnel(admin_client, make_committed, clean_db):
    funnel = await make_committed.funnel()
    user = await make_committed.user()
    await make_committed.funnel_entry(funnel=funnel, user=user, source="tracking_link")

    r = await admin_client.get("/api/stats/funnels/summary")
    body = r.json()
    assert len(body["rows"]) == 1
    assert body["rows"][0]["funnel_id"] == funnel.id
    assert body["rows"][0]["entered"] == 1


@pytest.mark.asyncio
async def test_funnels_summary_sorted_by_revenue_desc(admin_client, make_committed, clean_db):
    f1 = await make_committed.funnel(name="A")
    f2 = await make_committed.funnel(name="B")
    user = await make_committed.user()
    # f2 — есть платёж
    await make_committed.funnel_entry(funnel=f2, user=user, source="tracking_link")
    await make_committed.payment(user=user, product_id=f2.product_id, amount=5000)
    # f1 — только entry, без платежей
    await make_committed.funnel_entry(funnel=f1, user=user, source="tracking_link")

    r = await admin_client.get("/api/stats/funnels/summary")
    body = r.json()
    # f2 должен быть первым (больше revenue)
    assert body["rows"][0]["funnel_id"] == f2.id


# ============================================================
# /stats/health
# ============================================================

@pytest.mark.asyncio
async def test_health_empty_returns_warnings(admin_client, clean_db):
    """Пустая БД → warning'и: no_tracking_links, no_funnels."""
    r = await admin_client.get("/api/stats/health")
    assert r.status_code == 200
    body = r.json()
    keys = {w["key"] for w in body["warnings"]}
    assert "no_tracking_links" in keys
    assert "no_funnels" in keys
    assert body["summary"]["leads_30d"] == 0


@pytest.mark.asyncio
async def test_health_no_warning_when_well_configured(admin_client, make_committed, clean_db):
    """Когда есть ссылки, воронки и хорошая атрибуция — warnings уменьшаются."""
    product = await make_committed.product()
    funnel = await make_committed.funnel(product=product)
    link = await make_committed.tracking_link(product_id=product.id, funnel_id=funnel.id)
    user = await make_committed.user()
    await make_committed.lead(user=user, product=product, tracking_link_id=link.id, utm_source="ig")

    r = await admin_client.get("/api/stats/health")
    body = r.json()
    keys = {w["key"] for w in body["warnings"]}
    assert "no_tracking_links" not in keys
    assert "no_funnels" not in keys
    assert body["summary"]["leads_attributed_30d"] == 1
    assert body["summary"]["tracking_links_total"] == 1


@pytest.mark.asyncio
async def test_health_test_data_warning(admin_client, make_committed, clean_db):
    funnel = await make_committed.funnel()
    user = await make_committed.user()
    await make_committed.funnel_entry(funnel=funnel, user=user, source="manual")

    r = await admin_client.get("/api/stats/health")
    body = r.json()
    keys = {w["key"] for w in body["warnings"]}
    assert "test_data_present" in keys
    assert body["summary"]["test_entries"] == 1


@pytest.mark.asyncio
async def test_health_requires_auth(api_client):
    r = await api_client.get("/api/stats/health")
    assert r.status_code == 401
