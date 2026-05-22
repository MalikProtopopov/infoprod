# 07. Очерёдность реализации

## Фаза 0. Подготовка (10 мин)
1. Утвердить структуру проекта (см. `01_architecture.md`).
2. Создать `.env.example`, `docker-compose.yml`, `nginx/nginx.conf`, `README.md`.

## Фаза 1. Бэкенд‑скелет (1‑2 ч)
1. `requirements.txt`, `Dockerfile`, `app/core/config.py`, `app/main.py`.
2. Подключение SQLAlchemy async, alembic init, базовая миграция со всеми таблицами + сид admin.
3. JWT‑auth (`/auth/login`, `/auth/me`, `/auth/logout`), мидлварь.
4. Healthcheck `/healthz`.

## Фаза 2. CRUD‑эндпоинты (2 ч)
- bots, channels, products, users, payments, subscriptions, admin/password.
- Только данные, без интеграции с Telegram.

## Фаза 3. Интеграция с Telegram (1‑2 ч)
1. `services/telegram.py`: проверка токена, проверка прав в канале, создание invite‑link, кик.
2. Multi‑bot polling manager.
3. Хэндлеры `/start`, `/start <code>`, `/my`, `/help`, кнопка «Оставить заявку».
4. Завязать `POST /payments` на выдачу доступа.

## Фаза 4. Воркер (30 мин)
- APScheduler в `lifespan`.
- Хорошо: graceful shutdown.

## Фаза 5. Админ‑панель (3‑4 ч)
1. Скелет Next.js standalone, Tailwind.
2. Логин / лейаут / API‑клиент.
3. Разделы по очереди:  `bots → channels → products → users → payments → subscriptions → account`.
4. Каждая страница: список + создание + редактирование + удаление.

## Фаза 6. nginx + сертификат (30 мин)
- Конфиг nginx.
- Самоподписанный TLS на IP.

## Фаза 7. Локальная сборка и smoke‑тест (30 мин)
- `docker compose build && up`. Проверка `/healthz`, логина в админку, создания продукта, проверки бота.

## Фаза 8. Деплой на 72.56.72.136 (1 ч)
- Установить docker, rsync проекта, запуск, миграции.

## Критерии приёмки (по ТЗ)
- В админке можно добавить бота, канал, продукт, ввести оплату, и пользователь получает invite‑ссылку.
- `/my` показывает срок подписки.
- По истечении срока пользователь удаляется из канала и получает уведомление о возможности продлить.
- Веб‑панель работает по HTTPS.
