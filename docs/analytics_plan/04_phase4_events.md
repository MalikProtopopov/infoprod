# Phase 4 — Events и KPI менеджеров (отложенная)

**Срок**: 3–4 рабочих дня. Запускается **по необходимости**, когда:
- понадобится считать **micro-conversions** (просмотр карточки vs нажатие на заявку);
- появятся **роли** в `admins` (главный/оператор) и потребуются **KPI менеджеров**;
- захочется подключить внешнюю аналитику (PostHog/Amplitude) — нужен общий поток событий.

**Результат**: единый event-стрим внутри платформы, разрезы аналитики по администраторам, точный учёт промежуточных кликов в боте.

---

## Шаг 4.1 — Таблица `events`

Миграция `20260xxx_events.py`:

```sql
CREATE TABLE events (
  id           bigserial PRIMARY KEY,
  event_id     uuid NOT NULL UNIQUE DEFAULT gen_random_uuid(),
  name         text NOT NULL,
  ts           timestamptz NOT NULL DEFAULT now(),
  actor_type   text NOT NULL,   -- 'user' | 'admin' | 'system'
  user_id      bigint NULL REFERENCES users(id) ON DELETE SET NULL,
  tg_user_id   bigint NULL,
  admin_id     bigint NULL REFERENCES admins(id) ON DELETE SET NULL,
  source       text NOT NULL,   -- 'bot' | 'admin' | 'cron' | 'webhook'
  bot_id       bigint NULL,
  channel_id   bigint NULL,
  product_id   bigint NULL,
  tracking_link_id bigint NULL,
  payload      jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX events_name_ts        ON events (name, ts DESC);
CREATE INDEX events_user_ts        ON events (user_id, ts DESC) WHERE user_id IS NOT NULL;
CREATE INDEX events_link_ts        ON events (tracking_link_id, ts DESC) WHERE tracking_link_id IS NOT NULL;
CREATE INDEX events_admin_ts       ON events (admin_id, ts DESC) WHERE admin_id IS NOT NULL;
CREATE INDEX events_payload_gin    ON events USING gin (payload);
```

Для UUID понадобится `CREATE EXTENSION IF NOT EXISTS "pgcrypto"`.

---

## Шаг 4.2 — Сервис `events.emit()`

Файл: `backend/app/services/events.py`

```python
async def emit(
    session: AsyncSession,
    name: str,
    *,
    actor_type: str,
    source: str,
    user_id: int | None = None,
    tg_user_id: int | None = None,
    admin_id: int | None = None,
    bot_id: int | None = None,
    channel_id: int | None = None,
    product_id: int | None = None,
    tracking_link_id: int | None = None,
    payload: dict | None = None,
) -> None:
    await session.execute(
        insert(Event).values(
            name=name,
            actor_type=actor_type, source=source,
            user_id=user_id, tg_user_id=tg_user_id, admin_id=admin_id,
            bot_id=bot_id, channel_id=channel_id, product_id=product_id,
            tracking_link_id=tracking_link_id,
            payload=payload or {},
        )
    )
```

Используется в той же транзакции что и основная мутация — `emit()` не открывает свою транзакцию, не коммитит. Это даёт **транзакционную консистентность**: если основной INSERT упал, event тоже не запишется.

---

## Шаг 4.3 — Где emit'ить

### Бот (`backend/app/bot/handlers.py`)

| Хендлер | Событие | Что в payload |
|---|---|---|
| `start_with_arg` | `bot.start_received` | `{has_arg, has_tracking_link, has_product, arg}` |
| `start_with_arg` (если new user) | `bot.user_created` | — |
| `start_with_arg` (показ каталога) | `bot.catalog_viewed` | `{products_count}` |
| `start_with_arg` (показ карточки) | `bot.product_card_viewed` | `{from_deep_link: true}` |
| `cb_product` | `bot.product_card_viewed` | `{from_deep_link: false}` |
| `cb_lead` | `bot.lead_created` | `{ttl_active: bool}` |
| `cmd_my` | `bot.my_requested` | `{has_active: bool}` |
| `cmd_help` | `bot.help_requested` | — |

### Backend API

| Эндпоинт | Событие | Payload |
|---|---|---|
| `POST /api/auth/login` (success) | `admin.login_success` | — |
| `POST /api/auth/login` (fail) | `admin.login_fail` | `{reason: 'wrong_password' \| 'rate_limited'}` |
| `POST /api/payments` | `admin.payment_created` | `{amount, period_months, was_extension}` |
| `DELETE /api/payments/{id}` | `admin.payment_deleted` | — |
| `PATCH /api/leads/{id}` (status) | `admin.lead_status_changed` | `{from, to}` |
| `POST /api/subscriptions/{id}/revoke` | `admin.subscription_revoked` | — |
| `POST /api/subscriptions/{id}/extend` | `admin.subscription_extended` | `{days, months}` |
| `POST /api/tracking-links` | `admin.tracking_link_created` | `{utm_source}` |

### Services (`backend/app/services/subscriptions.py`)

| Функция | Событие |
|---|---|
| `grant_for_payment` | `subscription.created` или `subscription.extended` |
| `revoke` | `subscription.revoked` (или `expired` если вызов из cron) |
| `expire_due` | `cron.expire_due.run` `{processed}` |

### Telegram side-effects

В `services/telegram.py` — emit при успехе и при ошибке:
- `tg.invite_link_generated` / `tg.invite_link_failed`
- `tg.user_kicked` / `tg.user_kick_failed`
- `tg.notification_sent` (с `payload.kind`)

---

## Шаг 4.4 — Воронка с micro-conversions

После Phase 4 воронка `/funnel` обогащается промежуточным шагом:

```
Клики → /start → Просмотр карточки → Заявка → Оплата
```

Шаг «Просмотр карточки» = `COUNT(DISTINCT user_id)` где `events.name = 'bot.product_card_viewed'` и `ts BETWEEN from AND to`.

Это даёт ответ на вопрос: «доходят ли клиенты до карточки и сваливаются там, или сваливаются раньше?»

---

## Шаг 4.5 — KPI менеджеров

### Предусловие — роли в `admins`

Миграция:

```sql
ALTER TABLE admins
  ADD COLUMN role text NOT NULL DEFAULT 'admin',
  ADD COLUMN full_name text NULL;
-- роли: 'admin' (главный), 'operator' (менеджер)
```

### Логика

При `POST /api/payments` — `payment.admin_id = current_admin.id`. Это уже сделано в миграции 004 Phase 1 — поле есть, осталось заполнять.

### Эндпоинт `GET /api/stats/managers`

```json
{
  "rows": [
    {
      "admin_id": 4, "username": "anna", "full_name": "Анна",
      "leads_handled": 124,
      "payments_closed": 38,
      "revenue": "456000",
      "avg_time_to_contact_hours": 2.4,
      "avg_time_to_close_hours": 14.7,
      "close_rate": 0.31
    }
  ]
}
```

Считаем по `events`:
- `avg_time_to_contact` = avg(`leads.contacted_at - leads.created_at`) для leads, где `admin_id` менеджера фигурирует в `lead_status_changed`.
- `avg_time_to_close` = avg(`leads.paid_at - leads.created_at`).
- `payments_closed` = `payments.admin_id = X`.

### Frontend: страница `/managers`

Таблица KPI, лидерборд, sparkline на каждого.

---

## Шаг 4.6 — Backfill events из исторических таблиц

Одноразовый скрипт `services/events_backfill.py`:

```python
# Из users.first_seen_at → 'bot.user_created'
await session.execute("""
INSERT INTO events (name, ts, actor_type, source, user_id, tg_user_id, bot_id,
                    product_id, tracking_link_id, payload)
SELECT 'bot.user_created', first_seen_at, 'user', 'bot',
       id, telegram_user_id, first_bot_id, first_product_id,
       first_tracking_link_id,
       jsonb_build_object('backfill', true,
                          'utm_source', first_utm_source)
FROM users
""")

# Из leads.created_at → 'bot.lead_created'
# Из payments.created_at → 'admin.payment_created'
# Из subscriptions.created_at → 'subscription.created'
# Из leads.contacted_at / paid_at / closed_at → 'admin.lead_status_changed' (3 события для каждого)
```

После бэкфила — events содержат «синтетические» таймстампы из текущих таблиц.

---

## Шаг 4.7 — Опционально: экспорт events во внешний tracker

Если решите подключить PostHog / Mixpanel / Amplitude — добавить **outbox worker**:

1. Колонка `events.exported_at timestamptz NULL`.
2. Cron-job каждые 30 секунд: выбрать `events WHERE exported_at IS NULL LIMIT 100`, отправить batch'ем в API tracker'а, проставить `exported_at = now()`.
3. Это даёт надёжную доставку: если внешний сервис лежит — события не теряются.

---

## Чек-лист Phase 4

- [ ] Миграция `events`
- [ ] Сервис `events.emit()` с транзакционной семантикой
- [ ] Расстановка emit во всех точках бота
- [ ] Расстановка emit во всех мутирующих эндпоинтах
- [ ] Расстановка emit в services/subscriptions, telegram
- [ ] Миграция ролей в `admins` (role, full_name)
- [ ] Заполнение `payments.admin_id` при создании платежа
- [ ] Эндпоинт `GET /api/stats/managers`
- [ ] Frontend: страница `/managers` с лидербордом
- [ ] Воронка `/funnel` дополняется шагом «Просмотр карточки»
- [ ] Скрипт backfill events
- [ ] (Опционально) Outbox для экспорта во внешний tracker
- [ ] Acceptance-тесты
