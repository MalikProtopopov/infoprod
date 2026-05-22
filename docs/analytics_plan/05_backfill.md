# 05. Backfill исторических данных

Когда применяются миграции Phase 1, у уже существующих записей `users / leads / payments` поля атрибуции — `NULL`. Бэкфил восстанавливает максимум возможного.

## Когда запускается

Один раз — **сразу после `alembic upgrade head` в Phase 1**. Идемпотентен — повторный запуск ничего не сломает (везде `WHERE ... IS NULL`).

## Куда положить

Файл: `backend/scripts/backfill_attribution.py` — отдельный одноразовый CLI-скрипт. Запуск:

```bash
docker compose exec backend python -m scripts.backfill_attribution
```

## Алгоритм

### 1. `users.first_product_id` — из самой ранней связи (lead или payment)

```sql
UPDATE users u
SET first_product_id = sub.product_id
FROM (
  SELECT user_id, product_id
  FROM (
    SELECT user_id, product_id, created_at,
           ROW_NUMBER() OVER (
             PARTITION BY user_id ORDER BY created_at ASC
           ) AS rn
    FROM (
      SELECT user_id, product_id, created_at FROM leads
      UNION ALL
      SELECT user_id, product_id, created_at FROM payments
    ) all_touches
  ) ranked
  WHERE rn = 1
) sub
WHERE u.id = sub.user_id AND u.first_product_id IS NULL;
```

### 2. `users.first_bot_id` — если активный бот один, проставить всем

```python
rows = await db.execute("SELECT id FROM bots WHERE is_active = true")
active = list(rows)
if len(active) == 1:
    await db.execute(
        "UPDATE users SET first_bot_id = $1 WHERE first_bot_id IS NULL",
        active[0]['id'],
    )
else:
    print("[warn] more than one active bot, first_bot_id остаётся NULL для исторических")
```

### 3. `users.first_utm_*` — оставляем `NULL`

Исторические источники неизвестны — рекламы тогда ещё не было / атрибуция не велась.

### 4. Таймстампы `leads.contacted_at / paid_at / closed_at`

Грубое приближение по `created_at` (точной даты перехода в статус мы не знаем):

```sql
UPDATE leads SET contacted_at = created_at
WHERE status IN ('contacted','paid','closed') AND contacted_at IS NULL;

UPDATE leads SET paid_at = created_at
WHERE status IN ('paid','closed') AND paid_at IS NULL;

UPDATE leads SET closed_at = created_at
WHERE status = 'closed' AND closed_at IS NULL;
```

После Phase 1 все НОВЫЕ изменения статусов будут писать реальные timestamps — данные постепенно «выпрямятся».

### 5. `leads.tracking_link_id`, `leads.utm_*` — `NULL`

Атрибуции для исторических заявок нет.

### 6. `payments.tracking_link_id`, `payments.admin_id` — `NULL`

То же. Новые платежи будут наследовать `tracking_link_id` от lead и `admin_id` из текущей сессии.

## Результат на текущей БД

На момент написания: 3 users, 2 leads, 1 payment, 1 active bot.

После бэкфила:
- 1 пользователь (тот, у кого есть оплата) — `first_product_id` заполнен
- Все 3 пользователя — `first_bot_id = 4` (наш единственный активный бот)
- 0 пользователей — `first_utm_*` (исторических ссылок не было)
- 2 leads — `contacted_at/paid_at/closed_at` могут быть проставлены если статусы менялись; сейчас оба `new`, поэтому NULL.

## Реализация на Python

```python
# backend/scripts/backfill_attribution.py
import asyncio
import logging

from sqlalchemy import text

from app.db.session import SessionLocal

logger = logging.getLogger("backfill")
logging.basicConfig(level=logging.INFO)


async def backfill() -> None:
    async with SessionLocal() as session:
        # 1) first_product_id
        result = await session.execute(text("""
            UPDATE users u
            SET first_product_id = sub.product_id
            FROM (
              SELECT user_id, product_id FROM (
                SELECT user_id, product_id, created_at,
                       ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at ASC) rn
                FROM (
                  SELECT user_id, product_id, created_at FROM leads
                  UNION ALL
                  SELECT user_id, product_id, created_at FROM payments
                ) all_touches
              ) ranked WHERE rn = 1
            ) sub
            WHERE u.id = sub.user_id AND u.first_product_id IS NULL
        """))
        logger.info("first_product_id filled for %s users", result.rowcount)

        # 2) first_bot_id
        active = (await session.execute(text("SELECT id FROM bots WHERE is_active = true"))).all()
        if len(active) == 1:
            bot_id = active[0][0]
            r = await session.execute(
                text("UPDATE users SET first_bot_id = :b WHERE first_bot_id IS NULL"),
                {"b": bot_id},
            )
            logger.info("first_bot_id=%s filled for %s users", bot_id, r.rowcount)
        else:
            logger.warning("more than one active bot, first_bot_id оставлен NULL")

        # 3) leads timestamps
        for col, statuses in [
            ("contacted_at", "'contacted','paid','closed'"),
            ("paid_at",      "'paid','closed'"),
            ("closed_at",    "'closed'"),
        ]:
            r = await session.execute(text(f"""
                UPDATE leads SET {col} = created_at
                WHERE status IN ({statuses}) AND {col} IS NULL
            """))
            logger.info("%s filled for %s leads", col, r.rowcount)

        await session.commit()
    logger.info("backfill done")


if __name__ == "__main__":
    asyncio.run(backfill())
```

## Проверка после запуска

```sql
-- сколько пользователей с известным first_product_id?
SELECT COUNT(*) FILTER (WHERE first_product_id IS NOT NULL) AS with_product,
       COUNT(*)                                              AS total
FROM users;

-- проверка таймстампов leads
SELECT status, COUNT(*),
       COUNT(*) FILTER (WHERE contacted_at IS NOT NULL) AS with_contacted,
       COUNT(*) FILTER (WHERE paid_at IS NOT NULL)       AS with_paid,
       COUNT(*) FILTER (WHERE closed_at IS NOT NULL)     AS with_closed
FROM leads
GROUP BY status;
```
