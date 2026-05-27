from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.features import is_enabled
from app.db.session import SessionLocal
from app.services.subscriptions import expire_due
from app.workers.scheduled_messages import process_due_messages

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def _hourly_expire_due() -> None:
    try:
        async with SessionLocal() as session:
            count = await expire_due(session)
        if count:
            logger.info("expire_due processed %s subscriptions", count)
    except Exception as e:
        logger.exception("hourly_expire_due failed: %s", e)


async def _process_scheduled_messages() -> None:
    try:
        async with SessionLocal() as session:
            stats = await process_due_messages(session)
        if any(stats.values()):
            logger.info("scheduled_messages tick: %s", stats)
    except Exception as e:
        logger.exception("scheduled_messages tick failed: %s", e)


def start() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    sch = AsyncIOScheduler(timezone="UTC")
    # expire_due обслуживает подписки → джоба нужна только при monetization.
    if is_enabled("monetization"):
        sch.add_job(
            _hourly_expire_due,
            IntervalTrigger(hours=1),
            id="expire_due",
            max_instances=1,
            coalesce=True,
            next_run_time=datetime.now(tz=timezone.utc) + timedelta(seconds=60),
        )
    # scheduled_messages доставляет шаги воронок → только при funnels.
    if is_enabled("funnels"):
        sch.add_job(
            _process_scheduled_messages,
            # 30 сек — компромисс между latency для шагов с маленьким delay
            # и нагрузкой. Для шагов с delay=0 теперь sync-отправка из
            # handler'а (см. handlers.py · _flush_funnel_entry_now), так что
            # тик нужен в основном для D1+, где минута расхождения не важна.
            IntervalTrigger(seconds=30),
            id="scheduled_messages",
            max_instances=1,
            coalesce=True,
            next_run_time=datetime.now(tz=timezone.utc) + timedelta(seconds=15),
        )
    sch.start()
    _scheduler = sch
    logger.info("Scheduler started")


def stop() -> None:
    global _scheduler
    if _scheduler is None:
        return
    _scheduler.shutdown(wait=False)
    _scheduler = None
    logger.info("Scheduler stopped")
