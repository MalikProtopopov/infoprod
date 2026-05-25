# Infobizbot — полный контекст проекта

Документ — слепок состояния системы на **2026‑05‑22**. Назначение: основа для отдельного ТЗ на продуктовую аналитику с когортами, воронками, триггерами и событиями. Описана бизнес-модель, доменные сущности, поля БД, состояния, точки в коде где «что-то происходит» (т.е. кандидаты в события), а также готовый каркас событийной схемы.

---

## 1. Краткая суть продукта

Infobizbot — это **B2B-инструмент монетизации Telegram-каналов**. Владелец канала подключает Telegram-бота к админ-панели; через бота продаёт доступ в свои закрытые каналы по подписочной модели (3/6/12 мес.).

Поток клиента (happy path):
1. Клиент переходит в TG-бот по deep-link `t.me/<bot>?start=<product_code>` (из рекламы / сториз / поста).
2. Бот показывает карточку продукта (название, описание, цены).
3. Клиент жмёт **«Оставить заявку»** → в БД создаётся `Lead{status=new}`.
4. Администратор связывается с клиентом (вне системы), договаривается об оплате.
5. После получения денег администратор фиксирует факт оплаты в админке (`POST /api/payments`).
6. Сервер автоматически: создаёт `Payment`, создаёт/продлевает `Subscription{status=active, ends_at=…}`, **через бота** отправляет клиенту одноразовый invite-link, сохраняет ссылку в подписке.
7. Клиент переходит по ссылке, попадает в закрытый канал.
8. По истечении срока подписки (`ends_at < now`) воркер каждый час: банит-unban пользователя в канале → ставит статус `expired` → шлёт ему уведомление с предложением продлить.

Бизнес-метрики, которые продукт уже умеет считать (см. `/api/stats/overview`):
- Total users / new users (7d)
- Total leads / new leads / leads (24h)
- Active subscriptions / subscriptions expiring in 7d
- Revenue (total / last 30d) / payments (30d)
- Active bots / channels / products

---

## 2. Архитектура и стек

```
                       ┌─────────────────────────────────────────────┐
                       │                  nginx :443                  │
                       │  Let's Encrypt cert (grammy + api subdomain) │
                       └────────────┬────────────────────────────────┘
        grammy.mediann.dev          │           api.grammy.mediann.dev
        (admin UI + same-origin /api)            (внешний clean-API без префикса /api)
                       │                          │
              ┌────────▼────────┐        ┌────────▼───────────┐
              │ Next.js 15 SSR  │        │  FastAPI / uvicorn │
              │  (standalone)   │        │  + aiogram polling │
              │  React 19       │        │  + APScheduler     │
              └─────────────────┘        └────────┬───────────┘
                                                  │
                                          ┌───────▼────────┐
                                          │ PostgreSQL 16  │
                                          │  (volume)      │
                                          └────────────────┘
                                          
   Внешняя интеграция: Telegram Bot API (polling) — N ботов в одном процессе.
   Все 5 сервисов: nginx, admin (Next.js), backend (FastAPI+бот+воркер), db (Postgres),
   certbot (renew) — управляются docker compose, рестарт unless-stopped.
```

Стек:
| Слой | Технология |
|------|------------|
| Frontend / админка | Next.js 15 (App Router) + TypeScript + Tailwind + SWR |
| Backend / API | Python 3.12, FastAPI 0.115, SQLAlchemy 2.x async, asyncpg |
| Telegram-бот | aiogram 3.15 (polling, multi-bot manager) |
| Воркер | APScheduler 3.11 (внутри backend lifespan, hourly job) |
| Хранилище | PostgreSQL 16 |
| Авторизация админа | JWT в HttpOnly+Secure+SameSite=Lax cookie, bcrypt пароли |
| Веб-сервер | nginx alpine — HTTPS, HSTS, X-Frame, X-Content-Type |
| Деплой | docker compose, swap 2 GB на хосте |

---

## 3. Инфраструктура и доступы

| Что | Значение |
|---|---|
| Сервер | **72.56.72.136** (Ubuntu 24.04, ~1 GB RAM + 2 GB swap, 14 GB disk) |
| SSH | `ssh root@72.56.72.136` |
| Папка проекта | `/opt/infobizbot/` |
| Файл секретов | `/opt/infobizbot/.env` (chmod 600) |
| Frontend домен | **https://grammy.mediann.dev** |
| Public API домен | **https://api.grammy.mediann.dev** |
| TLS | Let's Encrypt (E7/E8), автообновление через certbot-контейнер 12 ч цикл |
| Admin login | `admin` / см. в `.env` (`ADMIN_PASSWORD`) |
| Postgres | внутри сети compose, наружу не выставлен |
| Telegram-боты | хранятся в таблице `bots`, токены plaintext в БД |

---

## 4. Доменная модель

Все таймстампы — `timestamptz`, время в UTC. Расчёт периодов подписок — **календарные** месяцы (`dateutil.relativedelta`), не 30-дневные.

### 4.1 Сущности (ER-обзор)

```
admins                 (учётки админ-панели; bcrypt password_hash; локально засеян из .env)
                                              
bots ──┐  (Telegram-бот: token, telegram_bot_id, username, title, is_active)
       │
       ├──► channels  (закрытые каналы: telegram_chat_id, title, username; FK bot_id)
                        │
                        ├──► products (карточки продаж: code, name, description,
                        │              cover_url, price_3m/6m/12m, currency, is_active;
                        │              ─ price=0 трактуется как «период не для продажи»)
                        │
                        └──► subscriptions ◄─┐
                                              │
users (Telegram-пользователи)                 │
  ├──► leads ────────► products               │
  ├──► payments ─────► products ──────────────┘
  └──► subscriptions ─► channels (и опционально → product, → payment)
```

### 4.2 Таблицы и поля

#### `admins`
| Поле | Тип | Назначение |
|---|---|---|
| id | bigserial PK | |
| username | text unique | логин админа |
| password_hash | text | bcrypt |
| created_at | timestamptz | |

#### `bots`
| Поле | Тип | Назначение |
|---|---|---|
| id | bigserial PK | |
| token | text unique | API-токен Telegram-бота (plaintext в БД, риск) |
| telegram_bot_id | bigint | id из Telegram getMe |
| username | text | @-имя бота |
| title | text | first_name бота |
| is_active | bool | при false — polling выключается; платеж под бот недоступен |
| created_at | timestamptz | |

#### `channels`
| Поле | Тип | Назначение |
|---|---|---|
| id | bigserial PK | |
| telegram_chat_id | bigint unique | id канала (например `-100…`) |
| title | text | |
| username | text null | @-имя канала, если публичное |
| bot_id | FK bots | через какого бота управляется |
| created_at | timestamptz | |

#### `products`
| Поле | Тип | Назначение |
|---|---|---|
| id | bigserial PK | |
| code | text unique | используется в deep-link `/start <code>` |
| name | text | |
| description | text null | |
| cover_url | text null | прямая ссылка на картинку |
| channel_id | FK channels | в какой канал даёт доступ |
| price_3m, price_6m, price_12m | numeric(12,2) | 0 = период не продаётся |
| currency | text default 'RUB' | |
| is_active | bool | |
| created_at | timestamptz | |

#### `users`
Telegram-пользователи, у которых был хотя бы один контакт с любым из ботов.
| Поле | Тип | Назначение |
|---|---|---|
| id | bigserial PK | |
| telegram_user_id | bigint unique | id из Telegram |
| username | text null | @-username, может меняться |
| first_name, last_name | text null | имя из TG |
| language_code | text null | `ru`, `en`… |
| phone, email | text null | заполняет админ вручную |
| notes | text null | заметки админа |
| first_seen_at | timestamptz | дата первого `/start` или клика |
| last_seen_at | timestamptz | обновляется при каждом upsert |

#### `leads`
| Поле | Тип | Назначение |
|---|---|---|
| id | bigserial PK | |
| user_id | FK users | |
| product_id | FK products | |
| status | text default 'new' | `new` / `contacted` / `paid` / `closed` (меняется вручную админом) |
| created_at | timestamptz | |

⚠️ **Ограничение**: один и тот же пользователь может оставить много заявок по одному продукту — мы не дедуплицируем.

#### `payments`
| Поле | Тип | Назначение |
|---|---|---|
| id | bigserial PK | |
| user_id | FK users | |
| product_id | FK products | |
| period_months | int (3 / 6 / 12) | |
| amount | numeric(12,2) | по умолчанию = `price_<period>` продукта |
| currency | text default 'RUB' | копия из продукта |
| comment | text null | свободная заметка админа |
| created_at | timestamptz | |

#### `subscriptions`
| Поле | Тип | Назначение |
|---|---|---|
| id | bigserial PK | |
| user_id | FK users | |
| channel_id | FK channels | |
| product_id | FK products null | NULL для «ручного продления» без платежа |
| payment_id | FK payments null | при extend перезаписывается на «последний», при delete платежа → SET NULL |
| starts_at | timestamptz | |
| ends_at | timestamptz | |
| status | text | `active` / `expired` / `revoked` |
| invite_link | text null | одноразовая Telegram invite-ссылка, member_limit=1 |
| created_at, updated_at | timestamptz | |

Индексы: `(status, ends_at)`, `(user_id, channel_id, status)` — для воркера и поиска активных.

---

## 5. Жизненный цикл пользователя и подписки (state machines)

### 5.1 User
```
(нет в БД) ─ /start ────► users.row (first_seen_at = now)
                          last_seen_at обновляется на каждом /start, callback, payment
```

### 5.2 Lead
```
new ─ кнопка «Оставить заявку» в боте ───► new
new ─ админ меняет ─► contacted ─► paid ─► closed
                              \─► closed
```
Смена статуса — вручную через `PATCH /api/leads/{id}`. Автоматического перехода в `paid` при создании платежа сейчас **нет** (потенциальное улучшение).

### 5.3 Subscription
```
              POST /payments
(нет)  ─────────────────────► active(ends_at = now + Nм, invite_link отправлен)
                                  │
        POST /payments (повтор)   │ extend существующую: ends_at += Nм
        ──────────────────────────►
                                  │
        cron каждый час: ends_at<=now
        ──────────────────────────► expired   (kick + notify)
                                  │
        POST /subscriptions/{id}/revoke
        ──────────────────────────► revoked   (kick + notify)
                                  │
        POST /subscriptions/{id}/extend (вручную)
        ──────────────────────────► active    (если до этого было active/expired/revoked;
                                              для не-active дополнительно: новая invite-link)
```

### 5.4 Платёж
- Создание платежа — критический атомарный момент: создаётся payment + subscription + invite_link на стороне Telegram + сообщение клиенту.
- При удалении платежа: все связанные подписки (по `payment_id`) идут в `revoked`, пользователь кикается из канала.

---

## 6. Бот-сценарии (точки взаимодействия)

Бот реализован в `backend/app/bot/handlers.py`. Все хендлеры один Dispatcher на бота, polling.

| Команда / событие | Что делает | Что меняется в БД |
|---|---|---|
| `/start` (без аргумента) | Приветствие + каталог активных продуктов (inline-кнопки) | upsert user (`last_seen_at`) |
| `/start <product_code>` | Карточка конкретного продукта | upsert user |
| `/help` | Краткая справка | — |
| `/my` | Список активных подписок и их сроков | — |
| Callback `prod:<id>` | Раскрыть карточку продукта | upsert user |
| Callback `lead:<id>` | **Оставить заявку** | upsert user + INSERT `leads{status=new}` |

Сообщения, которые **отправляет** бот (исходящие — это тоже события для аналитики):
- `WELCOME` — приветствие в `/start` без кода
- `NO_PRODUCTS` — если нет активных продуктов
- `PRODUCT_NOT_FOUND` — неверный код
- `LEAD_SENT` — после клика «Оставить заявку»
- `NO_SUBSCRIPTIONS` — `/my` без активных подписок
- `access_granted(…)` — после фиксации платежа: invite-link + срок
- `access_expired(channel_title)` — после истечения/отзыва подписки

Карточка продукта формируется в `texts.product_card()` — **периоды с ценой 0 скрываются**, если все нули — единый текст «Цена уточняется».

---

## 7. Админ-флоу

Меню: Обзор, Заявки, Пользователи, Платежи, Подписки, Продукты, Каналы, Боты, Профиль.

| Раздел | Действия | Что бьёт в БД |
|---|---|---|
| Обзор `/` | только чтение из `/api/stats/overview` | — |
| Боты `/bots` | CRUD, активация/деактивация (запуск/стоп polling) | bots ± |
| Каналы `/channels` | CRUD; при добавлении проверяется, что бот — админ канала | channels ± |
| Продукты `/products` | CRUD (включая обложку и цены 3/6/12) | products ± |
| Пользователи `/users` | поиск, карточка, заметки/телефон/email | users.update |
| Заявки `/leads` | фильтр по статусу; деталка с инфо о юзере, продукте, канале; смена статуса | leads.update / delete |
| Платежи `/payments` | список + добавление через автокомплит пользователя | payments ± + subscriptions ± + Telegram side-effects |
| Подписки `/subscriptions` | фильтр active/expired/revoked + revoke + extend (вручную, без платежа) | subscriptions.update + Telegram side-effects |
| Профиль `/account` | смена пароля | admins.update |

Авторизация — `POST /api/auth/login` → JWT в cookie. Защита от брутфорса: 10 попыток / 60с / IP.

---

## 8. API (полный перечень)

Все эндпоинты, кроме `/auth/login` и `/healthz`, требуют JWT cookie.

### Auth / Admin
- `POST   /api/auth/login` `{username, password}`
- `POST   /api/auth/logout`
- `GET    /api/auth/me`
- `POST   /api/admin/password` `{old_password, new_password}`

### Bots
- `GET    /api/bots`
- `POST   /api/bots` `{token}` (проверка через Telegram `getMe`)
- `PATCH  /api/bots/{id}` `{is_active?}`
- `DELETE /api/bots/{id}` (409 если есть каналы)

### Channels
- `GET    /api/channels`
- `POST   /api/channels` `{bot_id, telegram_chat_id, title?, username?}` (проверка прав бота)
- `PATCH  /api/channels/{id}` `{title?, username?}`
- `DELETE /api/channels/{id}` (409 если есть продукты или active subs)

### Products
- `GET    /api/products`
- `GET    /api/products/{id}`
- `POST   /api/products` (полная карточка)
- `PATCH  /api/products/{id}`
- `DELETE /api/products/{id}`

### Users
- `GET    /api/users?q=&limit=&offset=` (поиск по first/last/username/TG id; `@` отсекается)
- `GET    /api/users/{id}` (полная карточка: data + leads + payments + subscriptions)
- `PATCH  /api/users/{id}` `{phone?, email?, notes?}`

### Leads
- `GET    /api/leads?status=new|contacted|paid|closed|all`
- `GET    /api/leads/{id}`
- `PATCH  /api/leads/{id}` `{status}`
- `DELETE /api/leads/{id}`

### Payments
- `GET    /api/payments`
- `POST   /api/payments` `{user_id, product_id, period_months, amount?, comment?}`  
  — требует активный бот для соответствующего канала, иначе 409
- `PATCH  /api/payments/{id}` `{comment?}` (только комментарий, чтобы не нарушить связь с подпиской)
- `DELETE /api/payments/{id}` (отзывает связанные подписки)

### Subscriptions
- `GET    /api/subscriptions?status=active|expired|revoked|all`
- `POST   /api/subscriptions/{id}/revoke`
- `POST   /api/subscriptions/{id}/extend` `{days?, months?}`

### Stats
- `GET    /api/stats/overview` — агрегаты для дашборда

### Healthcheck
- `GET    /api/healthz`

---

## 9. Где в коде «что-то происходит» (кандидаты на события для аналитики)

Это — карта точек, где надо вставить логирование событий, когда вы будете подключать tracker.

### 9.1 Бот (`backend/app/bot/handlers.py`)
- `start_plain()` — отправлен каталог.
- `start_with_code()` — открыт продукт через deep-link (важно: тут есть `<product_code>`, можно ловить utm-замены).
- `cmd_help()` — клик `/help`.
- `cmd_my()` — клик `/my`.
- `cb_product()` — пользователь развернул карточку продукта.
- `cb_lead()` — пользователь оставил заявку.
- `_upsert_user()` — создание / обновление пользователя.

### 9.2 Backend сервисы (`backend/app/services/subscriptions.py`)
- `grant_for_payment()` — успешное создание/продление подписки и выпуск invite-link.
- `revoke()` — пользователь удалён из канала + уведомление; вызывается из API revoke и из expire_due.
- `extend()` — ручное продление; для не-active дополнительно отправляется новый invite.
- `expire_due()` — пакетная обработка истёкших подписок (часовой воркер).

### 9.3 Backend API (`backend/app/api/*.py`)
Каждая мутация — кандидат на server-side событие:
- `auth.login` (success / fail / rate-limited)
- `bots.create / update / delete`
- `channels.create / delete`
- `products.create / update / delete`
- `users.update`
- `leads.update / delete`
- `payments.create / delete`
- `subscriptions.revoke / extend`

### 9.4 Telegram side-effects (`backend/app/services/telegram.py`)
- `create_one_time_invite` — успех/неуспех (Telegram API может вернуть rate-limit)
- `kick_user` — успех/неуспех
- `send_message_safe` — успех/неуспех (важно для воронки активации)

### 9.5 Cron-воркер (`backend/app/workers/scheduler.py`)
- Запуск задачи `_hourly_expire_due` каждый час
- Количество обработанных подписок в каждом тике

---

## 10. Каркас событийной аналитики (база для второго ТЗ)

Все ID в событиях — **внутренние БД-id**, для связки. Дополнительно отдельный `event_id` UUID.

### 10.1 Сущности identity

| Идентификатор | Где | Назначение |
|---|---|---|
| `tg_user_id` | bigint, из Telegram | стабильный, уникальный |
| `user_id` | bigint, наш PK | основной для аналитики |
| `bot_id` | bigint | какой бот обслуживает |
| `channel_id` | bigint | конкретный канал |
| `product_id` / `product_code` | bigint / text | |
| `lead_id`, `payment_id`, `subscription_id` | bigint | |
| `admin_id` | bigint | автор админ-действия |

Сессия в боте — отсутствует (TG не даёт стабильный session_id). Можно эмулировать «сеанс = клик в течение 30 мин с момента предыдущего».

### 10.2 Предлагаемая таксономия событий

Формат: `category.action` (snake_case). Все события несут общие поля `event_id, ts, actor_type (user|admin|system), user_id?, tg_user_id?, admin_id?, source ('bot'|'admin'|'cron'|'webhook'), bot_id?, channel_id?, product_id?, payload`.

#### Acquisition (приобретение)
- `bot.start_received` — `payload: {has_deep_link, product_code?}`
- `bot.user_created` — впервые увидели пользователя; **first-touch**
- `bot.catalog_viewed` — открыли каталог из `/start`
- `bot.product_card_viewed` — раскрыли карточку (deep-link или callback)
- `bot.help_requested`
- `bot.my_requested` — посмотрел свои подписки

#### Conversion (конверсия)
- `bot.lead_created` — клик «Оставить заявку»; основная микро-конверсия
- `admin.lead_status_changed` — `payload: {from, to}`
- `admin.payment_created` — макро-конверсия; `payload: {amount, period_months, currency, product_id, channel_id, user_id, was_extension: bool}`
- `admin.payment_deleted`

#### Access (доступ к каналу)
- `subscription.created`
- `subscription.extended` — `payload: {by_payment_id?, manual: bool, delta_days, delta_months}`
- `subscription.expired` — наступил `ends_at`; от cron
- `subscription.revoked` — от админа или каскадно при удалении платежа
- `tg.invite_link_generated` — успех + сохранение в подписке
- `tg.invite_link_failed`
- `tg.user_kicked` — успех
- `tg.user_kick_failed`
- `bot.notification_sent` — `payload: {kind: 'access_granted'|'access_expired'}`

#### Admin telemetry
- `admin.login` (`success|failure|rate_limited`)
- `admin.password_changed`
- `admin.bot_added`, `admin.bot_activated`, `admin.bot_deactivated`, `admin.bot_deleted`
- `admin.channel_added`, `admin.channel_deleted`
- `admin.product_created`, `admin.product_updated`, `admin.product_deleted`
- `admin.user_edited` — `payload: {fields_changed: ['phone','email','notes']}`
- `admin.subscription_revoked`, `admin.subscription_extended_manual`

#### System / health
- `cron.expire_due.run` — `payload: {processed_count}`
- `bot.polling_started`, `bot.polling_crashed`, `bot.polling_restarted`
- `system.startup`

### 10.3 Когорты (cohort dimensions)

| Когорта | По чему режем | Где брать |
|---|---|---|
| **Acquisition cohort** | месяц/неделя первого `users.first_seen_at` | `users.first_seen_at` |
| **Source cohort** | `product_code` deep-link при первом `/start` | сохранить отдельно в `users.first_product_code` (новое поле!) |
| **Bot cohort** | первый бот, на котором появился пользователь | сохранить `users.first_bot_id` (новое поле!) |
| **Channel cohort** | первый канал, в который куплен доступ | вычисляется из `subscriptions` |
| **Product cohort** | по первому купленному продукту | из `payments` |
| **Period cohort** | первый купленный период (3/6/12) | из `payments` |
| **Language cohort** | `users.language_code` | уже есть |

⚠️ Сейчас в БД нет полей `first_product_code`, `first_bot_id`. Это **минимум, который надо добавить** для атрибуции — иначе ретроспективно неоткуда взять источник захода.

### 10.4 Воронки

**Главная — Acquisition → Revenue**:
```
bot.start_received
  └─► bot.product_card_viewed
        └─► bot.lead_created
              └─► admin.lead_status_changed(to='contacted')
                    └─► admin.payment_created
                          └─► subscription.created
                                └─► (через N мес.) subscription.expired
                                      └─► продление? (новая payment) ─► retention
```

KPI на каждом шаге:
- **CTR на карточку** = `card_viewed / start_received`
- **Lead rate** = `lead_created / card_viewed`
- **Contact rate** = `contacted / lead_created` (скорость работы менеджера)
- **Payment rate** = `payment_created / lead_created`
- **Activation rate** = `subscription.created / payment_created` (должен быть ~100%)
- **Renewal rate** (когортная) = % подписчиков, продливших до или в течение N дней после `ends_at`
- **Churn** = `1 - renewal_rate`

**Менеджерская**:
```
lead_created (timestamp t0)
  └─► contacted (t1)  ─► T_contact = t1 - t0   (avg, median, p90)
        └─► paid (t2) ─► T_close = t2 - t0
              └─► closed/lost
```

**Бот-вовлечённость**:
- `start_received` → `my_requested` через N дней (повторные касания)
- LTV: сумма всех payments на одного user_id по acquisition cohort

### 10.5 Retention / cohort matrix

Когорта = месяц первого `users.first_seen_at`. Метрика — % из когорты с активной подпиской на N-й месяц после acquisition. Или — % сделавших M-й платёж.

```
                месяц 0   месяц 1   месяц 2   ...
2026-05 N=1234   100%     12%       8%        ...
2026-06 N=2150            100%      18%       ...
```

Реализация — стандартная: SELECT cohort_month, n_months_after, COUNT(DISTINCT user_id).

### 10.6 Дополнительные размерности (атрибуты пользователя)

Каждый event обогащаем:
- `language_code`, `first_seen_at`, `acquisition_cohort_month`
- `first_product_id`, `first_channel_id`, `first_bot_id` (см. п. 10.3)
- `is_paid_ever` (boolean)
- `active_subscriptions_count` на момент события
- `total_payments_sum_rub` на момент события

Для real-time трекинга — пересчёт on-the-fly или периодический materialized view.

---

## 11. Технические рекомендации к реализации аналитики

### 11.1 Где хранить события

Варианты:
1. **Отдельная таблица `events` в той же Postgres** — самый простой старт. JSONB `payload`, индексы на `(name, ts)`, `(user_id, ts)`. Удобно: транзакционно с основной БД (выпуск инвайта и событие — в одной транзакции). Минус: смешаны OLTP и OLAP.
2. **ClickHouse / Tinybird / BigQuery** — для зрелой аналитики, дёшево пишем и быстро селектим. Требует pipeline.
3. **Готовый сервис: PostHog (self-hosted или cloud), Mixpanel, Amplitude, Yandex Metrika (через JS на админке + кастомные события через backend)**. Быстрее всего, не надо строить SQL.

Совет на старт — **Postgres + таблица events** с миграционным путём:
```sql
CREATE TABLE events (
  id           bigserial PRIMARY KEY,
  event_id     uuid NOT NULL UNIQUE,
  name         text NOT NULL,
  ts           timestamptz NOT NULL DEFAULT now(),
  actor_type   text NOT NULL,              -- user|admin|system
  user_id      bigint NULL REFERENCES users(id),
  tg_user_id   bigint NULL,
  admin_id     bigint NULL REFERENCES admins(id),
  source       text NOT NULL,              -- bot|admin|cron|webhook
  bot_id       bigint NULL,
  channel_id   bigint NULL,
  product_id   bigint NULL,
  payload      jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX events_name_ts ON events (name, ts DESC);
CREATE INDEX events_user_ts ON events (user_id, ts DESC);
CREATE INDEX events_payload_gin ON events USING gin (payload);
```

### 11.2 Куда вставлять `emit_event(...)`

Чёткая декомпозиция: в `backend/app/services/events.py` сделать функцию `emit(name, actor, **fields)` и вызывать её в каждой точке из раздела 9. Это даёт **один шов** для смены backend-а (Postgres → ClickHouse → 3rd-party).

### 11.3 UTM / атрибуция

Сейчас единственный сигнал — `<product_code>` в deep-link. Чтобы различать рекламные площадки, используйте паттерн `<product_code>__<utm_source>__<campaign>`. Бот распарсит, сохранит в `users.first_product_code`, `users.first_utm_source`. На стороне рекламы — генерируйте уникальные ссылки на одну посадочную (один продукт, разные коды).

### 11.4 Backfill для исторических событий

На момент включения аналитики у вас уже есть:
- `users.first_seen_at` → можно восстановить `bot.user_created`
- `leads.created_at` → `bot.lead_created`
- `payments.created_at` → `admin.payment_created` (но без acting admin_id, его не пишем сейчас — это пробел)
- `subscriptions.created_at`, `ends_at`, `status` → начальное состояние

Стартовый backfill — один SQL-скрипт, который сгенерирует «синтетические» события с правильными timestamps.

### 11.5 Что добавить в текущий код, чтобы потом не страдать

Минимальный список изменений в БД и API **до** старта аналитики:
1. `users.first_product_code TEXT NULL` — заполняется первым `/start <code>`.
2. `users.first_bot_id BIGINT NULL REFERENCES bots(id)`.
3. `users.first_utm_source TEXT NULL` — опционально, для парсинга `code__utm`.
4. `payments.admin_id BIGINT NULL REFERENCES admins(id)` — кто провёл платёж (для KPI менеджеров).
5. `subscriptions.created_by_admin_id BIGINT NULL` — для ручного extend без платежа.
6. `leads.contacted_at, paid_at, closed_at TIMESTAMPTZ NULL` — материализованные перевод в новый статус (упрощает аналитику lead-to-cash).
7. Логировать ответы Telegram API (success/fail) — сейчас просто warn'ы.

### 11.6 Что показывать в админке (analytics-ready)

После накопления событий — добавить страницы:
- `/analytics/overview` — KPI: MRR (с прогнозом по active subs), Conversion (lead→pay), Churn (cohort)
- `/analytics/cohorts` — матрица retention по acquisition month
- `/analytics/funnels` — конструктор / preset «start → card → lead → payment»
- `/analytics/products` — таблица продуктов с CTR, lead rate, ARPU, ARPPU
- `/analytics/channels` — какие каналы лучше монетизируются
- `/analytics/bots` — какой бот эффективнее (CTR, conversion)
- `/analytics/managers` — время отклика, % закрытых заявок (когда добавите admin_id в payments)

---

## 12. Текущее состояние данных (на момент написания)

| Сущность | Записей |
|---|---|
| Bots | 1 активный (`@zazacosmbot`) |
| Channels | 1 |
| Products | 2 |
| Users | 3 |
| Leads | 2 (все `new`) |
| Payments | 1 (`120 000 RUB`, 12 мес.) |
| Subscriptions | 1 (active) |

— минимум для первого подключения трекера и теста воронок.

---

## 13. Готовые ссылки

- Дашборд (live): https://grammy.mediann.dev/
- Внешний API (для интеграций / выгрузок): https://api.grammy.mediann.dev/
- Папка проекта на сервере: `/opt/infobizbot/`
- Бэкап БД: `docker compose exec db pg_dump -U $POSTGRES_USER $POSTGRES_DB` (скрипт можно добавить в cron)

---

## 14. Что НЕ покрывает текущий код (важно для ТЗ аналитики)

1. **Нет ни одного evento-логгера** — пока только SQL-мутации и стандартные `logger.info`. Все события надо проектировать с нуля.
2. **Нет атрибуции** — `users.first_product_code`/`first_bot_id`/`first_utm_source` не сохраняется. Сейчас атрибутировать первое касание можно только по совпадению timestamp+id, что хрупко.
3. **Нет `admin_id` в платежах** — нельзя посчитать KPI менеджеров.
4. **Нет таймстампов смены lead.status** — `t_contact`, `t_close` только в логах FastAPI (через 30 дней их нет).
5. **Нет CDC / outbox** — события не «отправляются» во внешний бус, только пишутся в БД. Для PostHog/Mixpanel понадобится либо webhook, либо отдельный воркер, тянущий новые события из `events`-таблицы.
6. **Нет реальных «сессий»** в боте — TG не даёт. Может имитироваться сессия = непрерывность кликов в N минут.
7. **Один админ** — нет ролей (operator / chief). Для KPI менеджеров — надо доработать таблицу `admins`.

Все эти пункты — **должны попасть в ТЗ на аналитику** как условия и подзадачи (миграции БД + протокол событий + бэкенд-логирование + бэкфил + интеграция с инструментом визуализации).
