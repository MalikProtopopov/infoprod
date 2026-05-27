# 11. Аудит источников 500 + план исправления

> Цель: отловить, где сейчас может возникнуть необработанный 500, и устранить
> системно. Симптом на фронте: 500 отдаётся **plain-text** «Internal Server Error»,
> и `fetch`-клиент падает на `JSON.parse` → «Unexpected token 'I'…». Дата: 2026-05-27.

## Главный вывод

- **Бизнес-правила в основном уже защищены 409** (см. «Уже ок» ниже) — кроме
  удаления продукта (исправлено ранее, коммит `8a00255`).
- **Системный корень проблемы:** в приложении **нет глобального обработчика
  исключений**. Любая непредвиденная ошибка (баг, сбой БД, ошибка Telegram) →
  Starlette отдаёт сырой текст «Internal Server Error» с `Content-Type: text/plain`
  → фронт `JSON.parse` падает. Это и есть причина «Unexpected token I».

## Сценарии, где 500 ещё возможен

| # | Severity | Эндпойнт / поток | Когда 500 | Причина |
|---|---|---|---|---|
| E1 | 🔴 High (систем.) | **любой** | любая непойманная ошибка | нет глобального exception handler → plain-text 500, фронт крэшится на JSON.parse |
| E2 | 🟠 Medium | `POST /payments` | сбой Telegram при выдаче инвайта | `tg.create_one_time_invite` в `grant_for_payment` **не обёрнут** → исключение Telegram (бот выкинут из канала, rate-limit, сеть) поднимается как 500 |
| E3 | 🟡 Low (defense) | любой create/delete | будущий незакрытый FK/unique | нет глобального `IntegrityError`-handler → новый путь без ручного guard'а = сырой 500 |
| E4 | 🟢 Info | `tracking_links` create | сервис кидает прочее | уже ловится, но fallback отдаёт `HTTPException(500, str(e))` — статус 500, хотя бы JSON |

### Уже ок (проверено, трогать не нужно)
- `DELETE /products/{id}` с платежами → **409** (исправлено, `8a00255`).
- `DELETE /bots/{id}` с каналами → **409** (`bots.py`, count Channel).
- `DELETE /channels/{id}` с продуктами/подписками → **409** (`channels.py`).
- `POST /bots` дубликат токена → **409**; `POST /channels` дубликат чата → **409**;
  `POST /products` / `PATCH` дубликат `code` → **409**.
- `POST /funnel-triggers` дубликат слова → **409** (сервис + ловля ValueError).
- `DELETE /users/{id}` — **не существует** (есть только GDPR `/forget`, это UPDATE, не delete) → RESTRICT на payments/subscriptions не достигается.
- `func.count()` / `func.coalesce(sum())` + `.scalar_one()` — всегда 1 строка, безопасно.

## План исправления

### Фаза 1 — системные обработчики (закрывают E1 + E3 разом) 🔴
Добавить в `app/main.py` глобальные handlers:

1. **`Exception` → JSON 500.** Любая непойманная ошибка возвращается как
   `JSONResponse(500, {"detail": "Внутренняя ошибка сервера", "request_id": ...})`.
   Убирает «Unexpected token I» **для всех** эндпойнтов навсегда. Логирование уже
   есть в `RequestContextMiddleware` (`request.unhandled_exception`).
2. **`sqlalchemy.exc.IntegrityError` → JSON 409.** Перехват нарушений целостности
   (FK RESTRICT / UNIQUE) с понятным сообщением «Операция нарушает связи данных
   (есть зависимые записи или дубликат)». Делает rollback. Defense-in-depth: даже
   если в будущем добавят endpoint без ручного guard'а — клиент получит 409 JSON,
   а не 500.

> Нюанс: при использовании `BaseHTTPMiddleware` (request_id/audit/metrics) важно,
> чтобы `add_exception_handler` срабатывал. Проверить, что handler ловит — если
> middleware перехватывает раньше, использовать `ServerErrorMiddleware`-совместимый
> подход или ловить в самих middleware. Покрыть тестом (эндпойнт, кидающий ошибку).

### Фаза 2 — точечно E2 (платёж + Telegram) 🟠
В `services/subscriptions.py::grant_for_payment` обернуть `create_one_time_invite`
в try/except: при ошибке Telegram — **не валить весь платёж** (подписка уже создана),
а оставить `invite_link=None` (как при отсутствии бота) и залогировать. Платёж
успешен, инвайт администратор досылает вручную. Альтернатива — отдавать 502 с ясным
текстом, но это откатит уже выданную подписку; предпочтительно «успех + отметка».

### Фаза 3 — тесты
- Тест: эндпойнт, бросающий `Exception`, → 500 **с JSON-телом** и `Content-Type: application/json`.
- Тест: `IntegrityError` → 409 JSON.
- Тест: `grant_for_payment` при падающем `create_one_time_invite` → платёж создаётся,
  подписка есть, 201 (а не 500).

## Приоритет
1. **Фаза 1** (E1+E3) — обязательно, дёшево, системно. Один раз закрывает класс проблем.
2. **Фаза 2** (E2) — желательно, реальный edge на проде с платежами.
3. Фаза 3 — тесты к обоим.

После — прогон тестов, деплой на zaza (grammy — по отдельному решению, как договорились).
