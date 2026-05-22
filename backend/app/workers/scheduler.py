from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.db.session import SessionLocal
from app.services.subscriptions import expire_due

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


def start() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    sch = AsyncIOScheduler(timezone="UTC")
    sch.add_job(
        _hourly_expire_due,
        IntervalTrigger(hours=1),
        id="expire_due",
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(tz=timezone.utc) + timedelta(seconds=60),
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
