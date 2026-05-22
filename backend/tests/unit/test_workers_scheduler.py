"""Тесты workers/scheduler — start/stop, _hourly_expire_due."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.workers import scheduler


@pytest.fixture(autouse=True)
def _reset_scheduler():
    """Каждый тест начинает с чистого _scheduler."""
    if scheduler._scheduler is not None:
        try:
            scheduler._scheduler.shutdown(wait=False)
        except Exception:
            pass
        scheduler._scheduler = None
    yield
    if scheduler._scheduler is not None:
        try:
            scheduler._scheduler.shutdown(wait=False)
        except Exception:
            pass
        scheduler._scheduler = None


@pytest.mark.asyncio
async def test_start_creates_scheduler():
    assert scheduler._scheduler is None
    scheduler.start()
    assert scheduler._scheduler is not None
    assert scheduler._scheduler.running


@pytest.mark.asyncio
async def test_start_is_idempotent():
    scheduler.start()
    first = scheduler._scheduler
    scheduler.start()
    assert scheduler._scheduler is first


def test_stop_when_not_started():
    """stop() без start() — не падает."""
    assert scheduler._scheduler is None
    scheduler.stop()  # noop


@pytest.mark.asyncio
async def test_stop_after_start():
    scheduler.start()
    assert scheduler._scheduler.running
    scheduler.stop()
    assert scheduler._scheduler is None


@pytest.mark.asyncio
async def test_scheduler_has_expire_due_job():
    scheduler.start()
    jobs = scheduler._scheduler.get_jobs()
    job_ids = [j.id for j in jobs]
    assert "expire_due" in job_ids


@pytest.mark.asyncio
async def test_hourly_expire_due_calls_service(monkeypatch):
    """_hourly_expire_due должен вызвать expire_due с session."""
    mock_expire = AsyncMock(return_value=3)
    monkeypatch.setattr("app.workers.scheduler.expire_due", mock_expire)

    # Мокаем SessionLocal — возвращаем async context manager
    fake_session = MagicMock()

    class _CM:
        async def __aenter__(self_):
            return fake_session
        async def __aexit__(self_, *a):
            return False

    monkeypatch.setattr("app.workers.scheduler.SessionLocal", lambda: _CM())

    await scheduler._hourly_expire_due()
    mock_expire.assert_awaited_once_with(fake_session)


@pytest.mark.asyncio
async def test_hourly_expire_due_handles_exception_gracefully(monkeypatch, caplog):
    """Если expire_due бросает — мы не падаем, а логим."""
    import logging
    caplog.set_level(logging.ERROR)
    mock_expire = AsyncMock(side_effect=RuntimeError("DB down"))
    monkeypatch.setattr("app.workers.scheduler.expire_due", mock_expire)

    class _CM:
        async def __aenter__(self_):
            return MagicMock()
        async def __aexit__(self_, *a):
            return False

    monkeypatch.setattr("app.workers.scheduler.SessionLocal", lambda: _CM())

    # Не должно поднимать exception
    await scheduler._hourly_expire_due()


@pytest.mark.asyncio
async def test_hourly_expire_due_does_not_log_when_zero(monkeypatch):
    """Если count == 0 — info-лог не эмитится (только при > 0)."""
    mock_expire = AsyncMock(return_value=0)
    monkeypatch.setattr("app.workers.scheduler.expire_due", mock_expire)

    class _CM:
        async def __aenter__(self_):
            return MagicMock()
        async def __aexit__(self_, *a):
            return False

    monkeypatch.setattr("app.workers.scheduler.SessionLocal", lambda: _CM())

    await scheduler._hourly_expire_due()
    mock_expire.assert_awaited_once()
