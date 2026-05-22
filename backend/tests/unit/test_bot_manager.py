"""Тесты bot/manager — get_aiogram_bot, start/stop, sync."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.bot import manager


@pytest.fixture(autouse=True)
def _reset_runners():
    """Каждый тест начинает с пустого _runners."""
    manager._runners.clear()
    yield
    manager._runners.clear()


def test_get_aiogram_bot_returns_none_when_not_running():
    assert manager.get_aiogram_bot(99999) is None


def test_get_aiogram_bot_returns_bot_when_running():
    fake_bot = MagicMock()
    runner = manager._BotRunner(bot=fake_bot, dp=MagicMock(), task=MagicMock())
    manager._runners[5] = runner
    assert manager.get_aiogram_bot(5) is fake_bot


@pytest.mark.asyncio
async def test_start_with_no_bots_in_db(monkeypatch):
    """Если в БД нет активных ботов — start() ничего не делает."""
    class _CM:
        async def __aenter__(self_):
            s = MagicMock()
            s.execute = AsyncMock(return_value=MagicMock(
                scalars=lambda: MagicMock(all=lambda: [])
            ))
            return s
        async def __aexit__(self_, *a):
            return False

    monkeypatch.setattr("app.bot.manager.SessionLocal", lambda: _CM())
    await manager.start()
    assert len(manager._runners) == 0


@pytest.mark.asyncio
async def test_stop_when_no_runners():
    """stop() без runners — noop."""
    assert len(manager._runners) == 0
    await manager.stop()


@pytest.mark.asyncio
async def test_stop_cancels_runner_task(monkeypatch):
    """stop() отменяет задачу runner'а и удаляет из _runners."""
    fake_bot = MagicMock()
    fake_bot.session.close = AsyncMock()

    fake_dp = MagicMock()
    fake_dp.stop_polling = AsyncMock()

    # Реальная asyncio.Task, которая ждёт sleep — её можно отменить
    # Используем AsyncMock task: cancel() noop, await не блокирует
    task = MagicMock()
    task.cancel = MagicMock()
    # await task — нужен awaitable. Используем done future.
    import asyncio
    done = asyncio.get_event_loop().create_future()
    done.set_result(None)
    task.__await__ = lambda self: done.__await__()
    manager._runners[42] = manager._BotRunner(bot=fake_bot, dp=fake_dp, task=task)

    await manager.stop()
    assert len(manager._runners) == 0
    fake_dp.stop_polling.assert_awaited()


@pytest.mark.asyncio
async def test_sync_stops_inactive_bots(monkeypatch):
    """Если активная ссылка деактивирована — sync() остановит её."""
    fake_bot = MagicMock()
    fake_bot.session.close = AsyncMock()
    fake_dp = MagicMock()
    fake_dp.stop_polling = AsyncMock()

    # Используем AsyncMock task: cancel() noop, await не блокирует
    task = MagicMock()
    task.cancel = MagicMock()
    # await task — нужен awaitable. Используем done future.
    import asyncio
    done = asyncio.get_event_loop().create_future()
    done.set_result(None)
    task.__await__ = lambda self: done.__await__()
    manager._runners[42] = manager._BotRunner(bot=fake_bot, dp=fake_dp, task=task)

    # Возвращаем пустой список активных ботов
    class _CM:
        async def __aenter__(self_):
            s = MagicMock()
            s.execute = AsyncMock(return_value=MagicMock(
                scalars=lambda: MagicMock(all=lambda: [])
            ))
            return s
        async def __aexit__(self_, *a):
            return False

    monkeypatch.setattr("app.bot.manager.SessionLocal", lambda: _CM())
    await manager.sync()
    assert 42 not in manager._runners


@pytest.mark.asyncio
async def test_start_bot_idempotent_when_already_running(monkeypatch):
    """_start_bot не создаёт runner повторно если уже есть."""
    existing_runner = manager._BotRunner(bot=MagicMock(), dp=MagicMock(), task=MagicMock())
    manager._runners[100] = existing_runner

    bot_row = MagicMock(id=100, token="x", username="bot")
    await manager._start_bot(bot_row)
    # Не заменили
    assert manager._runners[100] is existing_runner
