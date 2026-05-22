# Infobizbot — Telegram‑бот продажи доступа в закрытые каналы

Telegram‑бот + админ‑панель + PostgreSQL + nginx, упакованные в `docker-compose`.

## Быстрый старт

```bash
cp .env.example .env
# отредактировать .env (POSTGRES_PASSWORD, JWT_SECRET, ADMIN_PASSWORD)

# Сгенерировать самоподписанный TLS на IP
mkdir -p nginx/ssl
openssl req -x509 -nodes -days 1825 -newkey rsa:2048 \
  -keyout nginx/ssl/key.pem -out nginx/ssl/cert.pem \
  -subj "/CN=72.56.72.136"

docker compose up -d --build
```

Открыть `https://<host>/`, залогиниться (логин/пароль из `.env`).

## Компоненты
- `backend/` — FastAPI + aiogram 3 (polling) + APScheduler.
- `admin/` — Next.js 15 (standalone).
- `nginx/` — обратный прокси и TLS.

## Документация
- ТЗ: `docs/TZ_Client.docx`, конвертация в md: `docs/TZ_Client.md`.
- Планы: `docs/plans/`.

## Полезное
```bash
docker compose logs -f backend
docker compose exec backend alembic upgrade head
docker compose exec db psql -U $POSTGRES_USER $POSTGRES_DB
```
