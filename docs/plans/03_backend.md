# 03. Backend (FastAPI)

## Зависимости (requirements.txt)
- fastapi, uvicorn[standard]
- sqlalchemy[asyncio], asyncpg, alembic
- pydantic, pydantic-settings, email-validator
- passlib[bcrypt]
- python-jose[cryptography] (JWT)
- aiogram==3.*
- apscheduler
- httpx
- python-multipart

## Конфиг (`app/core/config.py`)
Env‑переменные:
- `DATABASE_URL` (например `postgresql+asyncpg://...`)
- `JWT_SECRET`, `JWT_TTL_MIN` (default 60*24*7)
- `ADMIN_USERNAME`, `ADMIN_PASSWORD` — стартовый сид.
- `CORS_ORIGINS` (csv)
- `DEFAULT_CURRENCY` (default RUB)
- `PUBLIC_BASE_URL` — для построения ссылок (если потребуется).

## Эндпоинты (префикс `/api`)

### Auth
- `POST /auth/login` `{username, password}` → set cookie `access_token` + `{ok: true}`
- `POST /auth/logout` → clear cookie
- `GET /auth/me` → текущий админ

### Bots
- `GET /bots` — список
- `POST /bots` `{token}` — добавление; вызываем `getMe` через Telegram API, сохраняем `username/title`, регистрируем бота в multi-bot менеджере (запуск polling).
- `PATCH /bots/{id}` `{is_active}` — активация/деактивация
- `DELETE /bots/{id}` — удаление с подтверждением (frontend); остановка polling.

### Channels
- `GET /channels`
- `POST /channels` `{bot_id, telegram_chat_id_or_username, title?}` — проверяем что бот — админ и может приглашать.
- `PATCH /channels/{id}` — переименование.
- `DELETE /channels/{id}` — удаление.

### Products
- `GET /products`
- `POST /products` `{code, name, description, channel_id, price_3m, price_6m, price_12m, currency, cover_url?}`
- `PATCH /products/{id}`
- `DELETE /products/{id}`

### Users
- `GET /users?q=&limit=&offset=` — список с поиском по имени/username.
- `GET /users/{id}` — карточка: данные TG (read-only), редактируемые поля, заявки, платежи, подписки.
- `PATCH /users/{id}` `{phone?, email?, notes?}`

### Payments
- `GET /payments`
- `POST /payments` `{user_id, product_id, period_months, amount?, comment?}` — если `amount` не передан, подставляется из цены. В одной транзакции: создаём `payment` + продлеваем/создаём `subscription` + строим `invite_link` через Telegram API + отправляем сообщение пользователю.
- `PATCH /payments/{id}` `{comment?}`
- `DELETE /payments/{id}` — удаление платежа отзывает связанную подписку.

### Subscriptions
- `GET /subscriptions?status=active|expired|revoked|all`
- `POST /subscriptions/{id}/revoke` — отозвать сейчас.
- `POST /subscriptions/{id}/extend` `{days|months}` — ручное продление.

### Admin account
- `POST /admin/password` `{old_password, new_password}` — смена пароля.

## Сервисы
- `services/telegram.py` — обёртка над aiogram Bot для:
  - `get_me(token)`
  - `is_admin_in_chat(bot, chat_id)`
  - `create_one_time_invite(bot, chat_id, member_limit=1, expire_date?)`
  - `kick_user(bot, chat_id, user_id)` — `ban_chat_member` + `unban_chat_member` (чтобы можно было вернуться).
- `services/subscriptions.py` — `grant`, `revoke`, `extend`, `expire_due`.
- `services/payments.py` — `create_payment_and_grant`.

## Фоновые задачи (`workers/scheduler.py`)
- AsyncIOScheduler, запуск в `lifespan`.
- Job каждый час: `subscriptions.expire_due()` — выбирает истёкшие активные, вызывает `revoke` (или `expire`) и шлёт уведомление о возможности продлить.

## Безопасность
- Все `/api/*` (кроме `/auth/login`) требуют JWT‑кук.
- CORS: только origin админки.
- Cookie: `HttpOnly`, `SameSite=Lax`, `Secure` (в проде).
- Rate limit на `/auth/login` (простой счётчик в памяти).

## Логи
- structlog или стандартный logging с JSON-форматтером в проде, текст в dev.
