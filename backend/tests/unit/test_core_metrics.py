"""Тесты Prometheus метрик."""
from __future__ import annotations

import pytest

from app.core.metrics import _normalize_path


class TestNormalizePath:
    def test_keeps_static_segments(self):
        assert _normalize_path("/api/healthz") == "/api/healthz"

    def test_replaces_numeric_id(self):
        assert _normalize_path("/api/users/42") == "/api/users/:id"

    def test_replaces_multiple_ids(self):
        assert _normalize_path("/api/products/1/links/99") == "/api/products/:id/links/:id"

    def test_does_not_replace_letters(self):
        assert _normalize_path("/api/tracking-links/abc123/qr.png") == "/api/tracking-links/abc123/qr.png"


@pytest.mark.asyncio
async def test_metrics_endpoint_returns_prometheus_format(api_client):
    """GET /metrics — content-type prometheus, ненулевой output."""
    r = await api_client.get("/metrics")
    assert r.status_code == 200
    # prometheus_client возвращает text/plain; version=0.0.4
    assert "text/plain" in r.headers["content-type"]
    body = r.text
    # Должны быть наши счётчики
    assert "http_requests_total" in body or "# HELP" in body


@pytest.mark.asyncio
async def test_metrics_counts_requests(api_client):
    """После 3 запросов на /healthz — счётчик увеличился минимум на 3."""
    # Прогреваем
    await api_client.get("/api/healthz")
    await api_client.get("/api/healthz")
    await api_client.get("/api/healthz")

    r = await api_client.get("/metrics")
    body = r.text
    # Ищем строку метрики http_requests_total для /api/healthz
    healthz_lines = [
        line for line in body.split("\n")
        if 'http_requests_total{' in line and 'path="/api/healthz"' in line
    ]
    assert healthz_lines, "Метрика http_requests_total для healthz не найдена"
    # Каждая строка — counter value, sum >= 3
    values = []
    for line in healthz_lines:
        parts = line.rsplit(" ", 1)
        if len(parts) == 2:
            try:
                values.append(float(parts[1]))
            except ValueError:
                pass
    assert sum(values) >= 3


@pytest.mark.asyncio
async def test_metrics_records_duration_histogram(api_client):
    """histogram записывает duration с buckets."""
    await api_client.get("/api/healthz")
    r = await api_client.get("/metrics")
    body = r.text
    assert "http_request_duration_seconds" in body
    # есть _bucket / _count / _sum строки
    assert "_bucket" in body
    assert "_count" in body
    assert "_sum" in body


@pytest.mark.asyncio
async def test_metrics_endpoint_itself_not_counted(api_client):
    """GET /metrics не должен инкрементить counter, иначе циклически растёт."""
    # Первый запрос /metrics
    r1 = await api_client.get("/metrics")
    body1 = r1.text
    # ... ещё несколько /metrics
    await api_client.get("/metrics")
    await api_client.get("/metrics")
    r2 = await api_client.get("/metrics")
    body2 = r2.text
    # Path "/metrics" не должен появляться в http_requests_total
    assert 'path="/metrics"' not in body1
    assert 'path="/metrics"' not in body2


@pytest.mark.asyncio
async def test_metrics_normalizes_dynamic_ids(api_client, make_committed, clean_db):
    """Запрос /api/users/42 → метрика c path=/api/users/:id, не /api/users/42."""
    user = await make_committed.user()
    # Будет 404 если без auth, но всё равно посчитается с path=/api/users/:id
    await api_client.get(f"/api/users/{user.id}")

    r = await api_client.get("/metrics")
    body = r.text
    assert '/api/users/:id' in body
    assert f'/api/users/{user.id}' not in body
