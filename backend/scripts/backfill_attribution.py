"""One-shot скрипт восстановления исторической атрибуции.

Запуск из контейнера:
    docker compose exec backend python -m scripts.backfill_attribution

Идемпотентен: все UPDATE с WHERE ... IS NULL.
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import text

from app.db.session import SessionLocal

logger = logging.getLogger("backfill")
logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s — %(message)s")


SQL_FIRST_PRODUCT = """
UPDATE users u
SET first_product_id = sub.product_id
FROM (
  SELECT user_id, product_id FROM (
    SELECT user_id, product_id, created_at,
           ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at ASC) AS rn
    FROM (
      SELECT user_id, product_id, created_at FROM leads
      UNION ALL
      SELECT user_id, product_id, created_at FROM payments
    ) all_touches
  ) ranked WHERE rn = 1
) sub
WHERE u.id = sub.user_id AND u.first_product_id IS NULL
"""

SQL_LEADS_TS = [
    (
        "contacted_at",
        "UPDATE leads SET contacted_at = created_at "
        "WHERE status IN ('contacted','paid','closed') AND contacted_at IS NULL",
    ),
    (
        "paid_at",
        "UPDATE leads SET paid_at = created_at "
        "WHERE status IN ('paid','closed') AND paid_at IS NULL",
    ),
    (
        "closed_at",
        "UPDATE leads SET closed_at = created_at "
        "WHERE status = 'closed' AND closed_at IS NULL",
    ),
]


async def backfill() -> None:
    async with SessionLocal() as session:
        # 1) first_product_id
        result = await session.execute(text(SQL_FIRST_PRODUCT))
        logger.info("first_product_id filled for %s users", result.rowcount)

        # 2) first_bot_id — если активный бот один, проставляем всем
        active = (await session.execute(text("SELECT id FROM bots WHERE is_active = true"))).all()
        if len(active) == 1:
            bot_id = active[0][0]
            r = await session.execute(
                text("UPDATE users SET first_bot_id = :b WHERE first_bot_id IS NULL"),
                {"b": bot_id},
            )
            logger.info("first_bot_id=%s filled for %s users", bot_id, r.rowcount)
        elif len(active) == 0:
            logger.warning("нет активных ботов — first_bot_id остаётся NULL")
        else:
            logger.warning(
                "несколько активных ботов (%s) — first_bot_id оставлен NULL", len(active)
            )

        # 3) Таймстампы смены статуса leads
        for col, sql in SQL_LEADS_TS:
            r = await session.execute(text(sql))
            logger.info("%s filled for %s leads", col, r.rowcount)

        await session.commit()
    logger.info("backfill done")


if __name__ == "__main__":
    asyncio.run(backfill())
