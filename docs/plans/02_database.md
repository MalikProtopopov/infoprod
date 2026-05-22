# 02. База данных (PostgreSQL 16)

Все таблицы — UTC времена, мягкое удаление не используется (по ТЗ удаление с подтверждением).

## Таблицы

### admins
| Поле | Тип | Комментарий |
|------|-----|-------------|
| id | bigserial PK | |
| username | text unique not null | |
| password_hash | text not null | bcrypt |
| created_at | timestamptz default now() | |

Сидится миграцией из env: `ADMIN_USERNAME` / `ADMIN_PASSWORD`.

### bots
| Поле | Тип |
|------|-----|
| id | bigserial PK |
| token | text unique not null |
| telegram_bot_id | bigint not null |
| username | text not null |
| title | text |
| is_active | bool default true |
| created_at | timestamptz default now() |

### channels
| Поле | Тип |
|------|-----|
| id | bigserial PK |
| telegram_chat_id | bigint unique not null |
| title | text not null |
| username | text null |
| bot_id | fk → bots.id not null |
| created_at | timestamptz default now() |

### products
| Поле | Тип |
|------|-----|
| id | bigserial PK |
| code | text unique not null  ─ короткий код для deep-link `/start <code>` |
| name | text not null |
| description | text |
| cover_url | text null |
| channel_id | fk → channels.id not null |
| price_3m | numeric(12,2) not null |
| price_6m | numeric(12,2) not null |
| price_12m | numeric(12,2) not null |
| currency | text default 'RUB' |
| is_active | bool default true |
| created_at | timestamptz default now() |

### users
Telegram-пользователи, нажавшие /start.

| Поле | Тип |
|------|-----|
| id | bigserial PK |
| telegram_user_id | bigint unique not null |
| username | text null |
| first_name | text null |
| last_name | text null |
| language_code | text null |
| phone | text null  (редактируется админом) |
| email | text null  (редактируется админом) |
| notes | text null  (заметки админа) |
| first_seen_at | timestamptz default now() |
| last_seen_at | timestamptz default now() |

### leads (заявки)
Сохраняются по кнопке «Оставить заявку».

| Поле | Тип |
|------|-----|
| id | bigserial PK |
| user_id | fk → users.id |
| product_id | fk → products.id |
| status | text default 'new'  -- new / contacted / paid / closed |
| created_at | timestamptz default now() |

### payments
| Поле | Тип |
|------|-----|
| id | bigserial PK |
| user_id | fk → users.id |
| product_id | fk → products.id |
| period_months | int in (3,6,12) not null |
| amount | numeric(12,2) not null |
| currency | text default 'RUB' |
| comment | text null |
| created_at | timestamptz default now() |

### subscriptions
| Поле | Тип |
|------|-----|
| id | bigserial PK |
| user_id | fk → users.id |
| channel_id | fk → channels.id |
| product_id | fk → products.id null  (для ручного продления — null) |
| payment_id | fk → payments.id null  (для ручного продления — null) |
| starts_at | timestamptz not null |
| ends_at | timestamptz not null |
| status | text not null  -- active / expired / revoked |
| invite_link | text null |
| created_at | timestamptz default now() |
| updated_at | timestamptz default now() |

Индексы:
- `(user_id, channel_id, status)` — быстрый поиск активной подписки.
- `(status, ends_at)` — для воркера, который выбирает истёкшие.

## Бизнес-правила
- Создание оплаты → создаётся подписка `active` с `ends_at = now + period`. Если активная подписка уже есть для этой связки (user_id, channel_id) — продлеваем её, добавляя период.
- Удаление оплаты → подписка, связанная по `payment_id`, отзывается (`revoked`), пользователь удаляется из канала.
- Фоновая задача → выбирает `status='active' AND ends_at <= now()` → меняет статус на `expired`, удаляет из канала, шлёт уведомление.
- Действие «Отозвать» в админке → `status='revoked'`, удаление из канала.
- Действие «Продлить вручную» → `ends_at += delta`, без создания платежа.

## Миграции
Alembic. Стартовая миграция — все таблицы и сидирование `admins` из env (если нет ни одного администратора).
