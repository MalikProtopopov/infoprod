"""Multi-bot polling manager.

Хранит активные экземпляры aiogram.Bot и задачу polling для каждого активного бота.
API:
    await start(): инициализация по текущему состоянию БД
    await stop(): остановка всех polling-задач
    await sync(): пересобрать список активных под текущее состояние БД
    get_aiogram_bot(bot_id): получить активный Bot по id из БД (или None)
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, Optional

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from sqlalchemy import select

from app.bot.handlers import build_dispatcher
from app.db.session import SessionLocal
from app.models.bot import Bot as BotModel

logger = logging.getLogger(__name__)


@dataclass
class _BotRunner:
    bot: Bot
    dp: Dispatcher
    task: asyncio.Task


_runners: Dict[int, _BotRunner] = {}
_lock = asyncio.Lock()


async def _start_bot(bot_row: BotModel) -> None:
    if bot_row.id in _runners:
        return
    bot = Bot(token=bot_row.token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = build_dispatcher()
    task = asyncio.create_task(_run_polling(bot, dp, bot_row.id), name=f"bot-poll-{bot_row.id}")
    _runners[bot_row.id] = _BotRunner(bot=bot, dp=dp, task=task)
    logger.info("Bot started: id=%s username=%s", bot_row.id, bot_row.username)


async def _run_polling(bot: Bot, dp: Dispatcher, bot_id: int) -> None:
    crashed = False
    try:
        await bot.delete_webhook(drop_pending_updates=False)
        await dp.start_polling(bot, handle_signals=False)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        crashed = True
        logger.exception("Polling for bot_id=%s crashed: %s", bot_id, e)
    finally:
        try:
            await bot.session.close()
        except Exception:
            pass
        # Если упал по ошибке — удалим из реестра, чтобы при следующей sync() запустить заново.
        if crashed:
            _runners.pop(bot_id, None)
        logger.info("Polling stopped: bot_id=%s (crashed=%s)", bot_id, crashed)


async def _stop_bot(bot_id: int) -> None:
    runner = _runners.pop(bot_id, None)
    if runner is None:
        return
    runner.task.cancel()
    try:
        await runner.dp.stop_polling()
    except Exception:
        pass
    try:
        await runner.task
    except Exception:
        pass


async def start() -> None:
    async with _lock:
        async with SessionLocal() as session:
            rows = (
                await session.execute(select(BotModel).where(BotModel.is_active.is_(True)))
            ).scalars().all()
        for row in rows:
            try:
                await _start_bot(row)
            except Exception as e:
                logger.exception("Failed to start bot id=%s: %s", row.id, e)


async def stop() -> None:
    async with _lock:
        ids = list(_runners.keys())
        for bot_id in ids:
            await _stop_bot(bot_id)


async def sync() -> None:
    """Пересобрать множество активных ботов согласно БД."""
    async with _lock:
        async with SessionLocal() as session:
            active_rows = (
                await session.execute(select(BotModel).where(BotModel.is_active.is_(True)))
            ).scalars().all()
        active_ids = {r.id for r in active_rows}
        # Стоп неактивных
        for bot_id in list(_runners.keys()):
            if bot_id not in active_ids:
                await _stop_bot(bot_id)
        # Старт новых
        for row in active_rows:
            if row.id not in _runners:
                try:
                    await _start_bot(row)
                except Exception as e:
                    logger.exception("sync: failed to start bot id=%s: %s", row.id, e)


def get_aiogram_bot(bot_id: int) -> Optional[Bot]:
    runner = _runners.get(bot_id)
    return runner.bot if runner else None
