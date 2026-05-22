# 06. Acceptance-тесты

Минимальный набор сценариев для приёмки каждой фазы. Все сценарии — ручные или скриптовые curl-сценарии; автотесты опционально.

---

## Phase 1 — Атрибуция и /sources

### 1.1 Создание ссылки и переход по ней

1. Создать `tracking_link` в админке для продукта P с `utm_source='test_source'`.
2. Скопировать сгенерированный URL.
3. Перейти по нему в Telegram с **нового аккаунта**.
4. Проверить:
   ```sql
   SELECT click_count, unique_users FROM tracking_links WHERE slug = '<slug>';
   -- click_count = 1, unique_users = 1
   ```
5. Проверить запись в `users`:
   ```sql
   SELECT first_utm_source, first_tracking_link_id, first_product_id, first_bot_id
   FROM users WHERE telegram_user_id = <tg_id>;
   -- first_utm_source = 'test_source', все поля заполнены
   ```
6. Нажать «Оставить заявку».
7. Проверить:
   ```sql
   SELECT tracking_link_id, utm_source FROM leads WHERE user_id = <user_id>;
   -- tracking_link_id корректный, utm_source = 'test_source'
   ```

### 1.2 TTL контекста ссылки (30 минут)

1. Пользователь приходит по ссылке: `users.current_link_set_at = T`.
2. Эмулировать прошествие 31 минуты:
   ```sql
   UPDATE users SET current_link_set_at = current_link_set_at - interval '31 minutes'
   WHERE id = <user_id>;
   ```
3. Пользователь нажимает «Оставить заявку».
4. Проверить:
   ```sql
   SELECT tracking_link_id, utm_source FROM leads WHERE id = <last>;
   -- tracking_link_id = NULL, utm_source = NULL
   ```

### 1.3 Возврат по другой ссылке

1. Пользователь U1 пришёл по ссылке L1 (`instagram`).
2. Через час U1 переходит по другой ссылке L2 (`youtube`).
3. Проверить:
   ```sql
   SELECT first_utm_source, current_tracking_link_id FROM users WHERE id = U1.id;
   -- first_utm_source = 'instagram' (НЕ изменился)
   -- current_tracking_link_id = L2.id (обновился)
   ```
4. U1 оставляет заявку.
5. Проверить:
   ```sql
   SELECT tracking_link_id, utm_source FROM leads WHERE id = <last>;
   -- tracking_link_id = L2.id, utm_source = 'youtube'
   ```

### 1.4 Деактивация ссылки

1. `UPDATE tracking_links SET is_active = false WHERE id = L.id;`
2. Новый пользователь делает `/start <L.slug>`.
3. Проверить: ссылка не резолвится → fallback на `products.code` или отображение каталога с уведомлением `LINK_EXPIRED_OR_INVALID`.
4. Существующие leads и payments с `tracking_link_id = L.id` остаются валидными — атрибуция сохранена снапшотом.

### 1.5 Коллизия slug с product.code

1. В системе есть продукт с `code = 'yoga12'`.
2. `POST /api/tracking-links {custom_slug: 'yoga12', ...}`.
3. Проверить: API возвращает **409 Conflict**, ссылка не создаётся.
4. Обратная коллизия: создать tracking_link с slug `'abc123'`. Попытка создать product с `code = 'abc123'`.
5. Проверить: API возвращает **409 Conflict**.

### 1.6 Валидация формата slug

1. `POST /api/tracking-links {custom_slug: 'ab', ...}` → 422 (короче 4 символов).
2. `POST /api/tracking-links {custom_slug: 'with space', ...}` → 422 (недопустимый символ).
3. `POST /api/tracking-links {custom_slug: 'a'*65, ...}` → 422 (длиннее 64).

### 1.7 Бэкфил

1. Применить миграции на БД с 3 users, 2 leads, 1 payment.
2. Запустить `python -m scripts.backfill_attribution`.
3. Проверить:
   - У пользователя с оплатой `first_product_id` заполнен (= product из payment).
   - У всех users `first_bot_id` = единственный активный бот.
   - У leads со статусами `paid/closed` — `paid_at, closed_at` заполнены (если такие были; сейчас оба `new`).

### 1.8 `/api/stats/sources`

1. После теста 1.1 — `GET /api/stats/sources?group_by=source`.
2. Проверить: в ответе есть строка с `source='test_source'`, `clicks=1`, `unique_users=1`, `leads=1`, `payments=0`, `revenue=0`.
3. Создать платёж для этого пользователя по этому продукту.
4. Повторить запрос — `payments=1`, `revenue=...`.

### 1.9 QR-код

1. `curl -o test.png https://grammy.mediann.dev/api/tracking-links/<id>/qr.png`.
2. Открыть PNG, отсканировать камерой → должна открыться правильная Telegram-ссылка.

### 1.10 Frontend: модалка генерации

1. Открыть карточку продукта.
2. Нажать «Создать ссылку с источником».
3. Заполнить только обязательное поле `utm_source`.
4. Жмём «Сгенерировать» → должен показаться URL с slug 8 символов.
5. Жмём «Скопировать» → URL в буфере.
6. Жмём «QR-код» → скачивается PNG.

---

## Phase 2 — Funnel и продуктовая аналитика

### 2.1 `/api/stats/funnel`

1. Создать ссылку → один пользователь по ней пришёл → оставил заявку → создан платёж.
2. `GET /api/stats/funnel?from=2026-05-01&to=2026-05-31`.
3. Проверить:
   ```json
   {"steps": [
     {"name":"Клики","count":1},
     {"name":"/start","count":1,"drop_pct":0},
     {"name":"Заявка","count":1,"drop_pct":0},
     {"name":"Оплата","count":1,"drop_pct":0}
   ]}
   ```

### 2.2 `/api/stats/products`

1. Несколько платежей разных периодов на разные продукты.
2. `GET /api/stats/products?from=&to=`.
3. Проверить: `by_period` корректно разнесён по 3/6/12 мес. Сумма `by_period.payments` = `payments_count`.

### 2.3 Sparkline

1. `GET /api/stats/overview` за 30 дней.
2. `sparklines.users` — массив длины 30, целые числа ≥0, сумма = `users.new_30d`.

### 2.4 Frontend: воронка

1. Открыть `/funnel`, выбрать период с данными.
2. Бары визуально пропорциональны, нижний % дроп-оффа корректный.
3. Tooltip по «Клики» поясняет: «точный учёт по дате в Phase 4».

---

## Phase 3 — Подписки

### 3.1 Renewal rate

1. Создать подписку на 3 мес у пользователя U1.
2. Прокрутить `ends_at` в прошлое: `UPDATE subscriptions SET ends_at = now() - interval '5 days' WHERE id = ...`.
3. Запустить cron вручную или подождать — подписка перейдёт в `expired`.
4. Создать новый платёж для U1 на этот же продукт.
5. `GET /api/stats/subscriptions` — `renewal_rate.renewed_within_30d = 1`.

### 3.2 Snapshot истечений

1. Создать подписки с `ends_at` через 3, 10, 25 дней.
2. `GET /api/stats/subscriptions` — `expiring.next_7d=1`, `next_14d=2`, `next_30d=3`.

### 3.3 Когортная матрица (если реализована)

1. Подождать накопления данных или сидировать тестовые когорты:
   ```sql
   INSERT INTO users (telegram_user_id, first_seen_at) VALUES (..., '2026-04-15');
   ```
2. Открыть `/retention` — матрица отображается.

---

## Phase 4 — Events

### 4.1 emit() из бота

1. Пользователь делает `/start <slug>`.
2. Проверить:
   ```sql
   SELECT name FROM events WHERE user_id = <u> ORDER BY ts DESC LIMIT 5;
   -- bot.product_card_viewed, bot.user_created, bot.start_received
   ```

### 4.2 emit() из admin API

1. `POST /api/payments` → `events.name = 'admin.payment_created'`, `admin_id` совпадает.

### 4.3 Backfill events

1. Запустить backfill — для каждого user должна появиться запись `bot.user_created` с `payload.backfill = true`.

### 4.4 KPI менеджеров

1. Создать админа `operator` с `role='operator'`.
2. Залогиниться им, оформить платёж.
3. `GET /api/stats/managers` — у этого менеджера `payments_closed=1`, `revenue=...`.

---

## Регрессионные тесты (для каждой фазы)

После любой фазы — прогон существующего smoke-теста (см. `docs/plans/`):
- Логин → 200
- Создание продукта / канала / бота — 200 / 409 / 422 по ожиданиям
- Платёж → выдача invite → подписка active
- Истечение подписки → expired + kick
- Все 9 страниц фронта → 200

Это гарантирует, что новые миграции и хендлеры не сломали покупательский флоу.
