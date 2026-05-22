# 01. Архитектура

## Структура репозитория
```
infobizbot/
├── docs/                  # ТЗ и планы
│   ├── TZ_Client.docx
│   └── plans/
├── backend/               # FastAPI + aiogram + воркер
│   ├── app/
│   │   ├── api/           # роуты FastAPI
│   │   ├── bot/           # aiogram-обработчики, multi-bot manager
│   │   ├── core/          # config, security, deps
│   │   ├── db/            # session, base
│   │   ├── models/        # SQLAlchemy ORM
│   │   ├── schemas/       # Pydantic
│   │   ├── services/      # бизнес-логика
│   │   ├── workers/       # APScheduler-задачи
│   │   └── main.py        # FastAPI + lifespan для бота/воркера
│   ├── alembic/
│   ├── alembic.ini
│   ├── pyproject.toml
│   ├── requirements.txt
│   └── Dockerfile
├── admin/                 # Next.js 15
│   ├── app/
│   │   ├── (auth)/login
│   │   ├── (dash)/bots, channels, products, users, payments, subscriptions, account
│   │   └── api/proxy      # серверный прокси к backend (опционально)
│   ├── components/
│   ├── lib/               # api-client, auth-context
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   └── Dockerfile
├── nginx/
│   ├── nginx.conf
│   └── ssl/               # сертификаты
├── docker-compose.yml
├── .env.example
└── README.md
```

## Поток данных
```
Telegram-клиент ──► aiogram (polling) ──► services ──► PostgreSQL
                                           ▲
                                           │
Браузер (admin) ──► nginx ──► Next.js ──► nginx ──► FastAPI ──► PostgreSQL
                                                       │
                                                  APScheduler (raz/час)
                                                       │
                                                   bot.kick_member / send_message
```

## Сетевое разграничение (Docker Compose)
- `db` (postgres) — внутри сети, без публикации портов.
- `backend` — публикует 8000 только в сеть compose. Воркер и бот живут внутри backend.
- `admin` — Next.js standalone, публикует 3000 внутри сети.
- `nginx` — наружный 80/443, проксирует `/api/*` → backend, остальное → admin.

## Решения
- **Polling вместо webhook** — упрощает поддержку нескольких ботов и не требует публичного домена.
- **Один процесс для API + бот + воркер** — через FastAPI `lifespan`, фоновые задачи запускаются вместе с приложением. Простой деплой одной командой.
- **JWT (HS256)** в HTTP‑куке `Secure; HttpOnly; SameSite=Lax` для авторизации админа.
- **Bcrypt** для хранения пароля администратора.
- **APScheduler AsyncIOScheduler** — ежечасный джоб, без отдельного Celery/Redis.
- **Конфиг через env** — `.env` читается через `pydantic-settings`.
