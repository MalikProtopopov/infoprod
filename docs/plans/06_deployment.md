# 06. Деплой и инфраструктура

## docker-compose.yml — сервисы
- `db`: postgres:16-alpine, volume `pgdata`, healthcheck.
- `backend`: build ./backend, depends_on db (healthy), envfile `.env`. Запускает `uvicorn app.main:app --host 0.0.0.0 --port 8000`. Внутри процесса — aiogram polling и APScheduler.
- `admin`: build ./admin, internal port 3000.
- `nginx`: nginx:alpine, проброс 80/443, монтируется `nginx/nginx.conf` и `nginx/ssl/`.

Все сервисы — в одной сети `internal`. Наружу выставлен только nginx.

## nginx
- `:80` → редирект на `:443`.
- `:443` (HTTPS):
  - `/api/` → `backend:8000` (без префикса убираем — backend сам с `/api`).
  - `/`   → `admin:3000` (Next.js).
- `client_max_body_size 10m;` (для обложек продуктов в будущем).
- HSTS, gzip.

## Сертификат
- На IP без домена: самоподписанный сертификат (openssl), вшит в образ nginx через volume.
- Если у заказчика появится домен — заменить на Let's Encrypt (`certbot` контейнером).

## Развёртывание на 72.56.72.136
Шаги:
1. `apt-get update && apt-get install -y docker.io docker-compose-plugin git`.
2. Клонировать (или rsync) проект в `/opt/infobizbot`.
3. Скопировать `.env.example` → `.env`, проставить секреты.
4. Сгенерировать самоподписанный TLS в `nginx/ssl/`.
5. `docker compose pull && docker compose build && docker compose up -d`.
6. `docker compose exec backend alembic upgrade head`.
7. Открыть в браузере `https://72.56.72.136`, залогиниться (`ADMIN_USERNAME`/`ADMIN_PASSWORD` из .env).

## Бэкап БД
Скрипт `scripts/backup.sh`:
```bash
docker compose exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > /var/backups/infobizbot/db-$(date +%F).sql.gz
```
Прописать в cron на сервере ежедневно (опционально — вне рамок ТЗ).
