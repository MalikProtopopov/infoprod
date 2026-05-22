# 04. Логирование — structured logs + request_id

## 4.1 Принципы

1. **Все логи — JSON в stdout**. Парсятся любым агрегатором.
2. **Каждый лог несёт `request_id`** — сквозной идентификатор. Запрос приходит → middleware ставит → все логи внутри запроса несут его.
3. **Контекст автоматически**: `user_id` (если есть), `admin_id`, `bot_id`, `tg_user_id` — добавляются автоматически где известны.
4. **Никаких секретов в логах**. JWT, токены ботов, пароли — маскируются.
5. **Schema-first**: единая структура поля для всех событий.
6. **Log levels**:
   - `DEBUG` — шум для разработчика, в проде выключен
   - `INFO` — нормальные события (start/stop, успешный запрос, отправка сообщения)
   - `WARNING` — заметные отклонения (TTL истёк, retry, fallback)
   - `ERROR` — что-то не сработало (TG API упал, БД отвалилась)
   - `CRITICAL` — нужен немедленный человек (БД полностью недоступна, миграция упала)

## 4.2 Backend — `structlog`

Установка: `structlog==24.4.0` + `python-json-logger==2.0.7` (для совместимости с stdlib).

### 4.2.1 Базовая настройка — `app/core/logging.py`

```python
from __future__ import annotations

import logging
import os
import sys
from typing import Any

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars, merge_contextvars

ENV = os.environ.get("ENV", "production")


def configure_logging(level: str = "INFO") -> None:
    """Один раз при старте приложения."""
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)
    processors: list[structlog.types.Processor] = [
        merge_contextvars,                                # request_id и пр. из ContextVar
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.CallsiteParameterAdder(
            parameters=[
                structlog.processors.CallsiteParameter.MODULE,
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.LINENO,
            ]
        ),
        _mask_secrets_processor,
        structlog.processors.dict_tracebacks,
    ]
    if ENV == "development":
        # Цветной красивый вывод
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level)),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


# Маскирование секретов
SECRET_KEYS = {"password", "token", "jwt", "secret", "authorization", "cookie", "access_token", "api_key"}


def _mask_secrets_processor(
    logger: Any, method_name: str, event_dict: structlog.types.EventDict
) -> structlog.types.EventDict:
    for k in list(event_dict.keys()):
        if k.lower() in SECRET_KEYS:
            event_dict[k] = "***REDACTED***"
        elif isinstance(event_dict[k], str) and len(event_dict[k]) > 100:
            # длинные токены маскируем частично
            v = event_dict[k]
            if any(s in k.lower() for s in ("token", "key", "secret")):
                event_dict[k] = v[:4] + "..." + v[-4:]
    return event_dict


def get_logger(name: str | None = None):
    return structlog.get_logger(name)
```

Вызвать в `app/main.py`:

```python
from app.core.logging import configure_logging
configure_logging(level=os.environ.get("LOG_LEVEL", "INFO"))
```

### 4.2.2 `request_id` middleware

```python
# app/api/middleware/request_id.py
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from structlog.contextvars import bind_contextvars, clear_contextvars
import structlog

logger = structlog.get_logger("http")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Уважаем входящий X-Request-ID (от nginx или клиента); иначе генерим
        req_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        clear_contextvars()
        bind_contextvars(
            request_id=req_id,
            method=request.method,
            path=request.url.path,
            client_ip=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
        import time
        t0 = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as e:
            logger.exception("request.unhandled_exception", error=str(e))
            raise
        dt_ms = round((time.perf_counter() - t0) * 1000, 2)
        logger.info(
            "request.completed",
            status=response.status_code,
            duration_ms=dt_ms,
        )
        response.headers["x-request-id"] = req_id
        return response


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() or (request.client.host if request.client else "?")
```

В `main.py` подключаем перед `CORSMiddleware`:
```python
app.add_middleware(RequestContextMiddleware)
```

В `nginx.conf` добавить пробрасывание:
```
proxy_set_header X-Request-ID $request_id;
```

### 4.2.3 Bind контекста в боте

В `bot/handlers.py`:

```python
from structlog.contextvars import bind_contextvars, clear_contextvars

@router.message(CommandStart(deep_link=True))
async def start_with_arg(m: Message, command: CommandObject, bot: Bot):
    clear_contextvars()
    bind_contextvars(
        request_id=str(uuid.uuid4()),
        tg_user_id=m.from_user.id if m.from_user else None,
        bot_id=bot.id,
        handler="start_with_arg",
        arg=command.args,
    )
    log = structlog.get_logger("bot")
    log.info("bot.start_received")
    ...
    log.info("bot.user_upserted", user_id=user.id, is_new=is_new)
    ...
```

### 4.2.4 Что логировать

| Событие | Уровень | Поля |
|---------|---------|------|
| `request.completed` | INFO | method, path, status, duration_ms, client_ip |
| `request.unhandled_exception` | ERROR | + exception, traceback |
| `auth.login_success` | INFO | username, client_ip |
| `auth.login_failure` | WARNING | username, reason (`wrong_password` / `rate_limited`), client_ip |
| `bot.start_received` | INFO | tg_user_id, arg, has_tracking_link |
| `bot.lead_created` | INFO | user_id, product_id, tracking_link_id |
| `bot.product_card_viewed` | INFO | user_id, product_id, deep_link |
| `payment.created` | INFO | payment_id, user_id, product_id, amount, admin_id |
| `subscription.granted` | INFO | sub_id, user_id, ends_at |
| `subscription.expired` | INFO | sub_id, user_id, by_cron |
| `subscription.revoked` | INFO | sub_id, by_admin_id |
| `tg.invite_link_generated` | INFO | sub_id, link_short |
| `tg.invite_link_failed` | WARNING | reason, chat_id |
| `tg.user_kicked` | INFO | user_id, channel_id |
| `tg.api_error` | ERROR | endpoint, status, body |
| `cron.expire_due.run` | INFO | processed_count, duration_ms |
| `bot.polling_started` | INFO | bot_id, username |
| `bot.polling_crashed` | ERROR | bot_id, exception |

## 4.3 Frontend — `pino` или плоский console-wrapper

Серверная часть Next.js использует `pino`. На клиенте — простой обёртка с маскированием:

### 4.3.1 `admin/lib/logger.ts`

```ts
const ENV = process.env.NODE_ENV;

type LogLevel = 'debug' | 'info' | 'warn' | 'error';

function emit(level: LogLevel, event: string, context: Record<string, unknown> = {}) {
  const payload = {
    ts: new Date().toISOString(),
    level,
    event,
    ...context,
    request_id: getRequestId(),
    href: typeof window !== 'undefined' ? location.pathname : undefined,
  };
  // В dev — красивый console; в prod — JSON
  if (ENV === 'development') {
    const fn = level === 'error' ? console.error : level === 'warn' ? console.warn : console.log;
    fn(`[${level}] ${event}`, context);
  } else {
    console.log(JSON.stringify(payload));
  }
  // В случае error — пробросить в Sentry (см. 05_observability.md)
  if (level === 'error' && typeof window !== 'undefined') {
    // @ts-ignore
    window.Sentry?.captureMessage?.(event, { extra: context });
  }
}

// request_id живёт в localStorage, чтобы переходы по SPA сохраняли trace
let _rid: string | null = null;
function getRequestId(): string {
  if (_rid) return _rid;
  if (typeof window === 'undefined') return 'ssr';
  const cached = sessionStorage.getItem('rid');
  if (cached) { _rid = cached; return cached; }
  _rid = crypto.randomUUID();
  sessionStorage.setItem('rid', _rid);
  return _rid;
}

export const log = {
  debug: (event: string, ctx?: Record<string, unknown>) => emit('debug', event, ctx),
  info:  (event: string, ctx?: Record<string, unknown>) => emit('info',  event, ctx),
  warn:  (event: string, ctx?: Record<string, unknown>) => emit('warn',  event, ctx),
  error: (event: string, ctx?: Record<string, unknown>) => emit('error', event, ctx),
};
```

### 4.3.2 Прокинуть request_id в API-клиент

```ts
// admin/lib/api.ts
import { log } from './logger';

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const rid = getRequestId();
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    credentials: 'include',
    headers: {
      ...(body ? { 'Content-Type': 'application/json' } : {}),
      'X-Request-ID': rid,
    },
    body: body ? JSON.stringify(body) : undefined,
    cache: 'no-store',
  });
  if (!res.ok && res.status >= 500) {
    log.error('api.server_error', { method, path, status: res.status, request_id: rid });
  }
  ...
}
```

Так все клиентские логи и серверные логи сшиваются по одному `X-Request-ID`.

## 4.4 nginx — `request_id` и access-логи в JSON

```nginx
http {
    log_format json_combined escape=json
      '{'
        '"ts":"$time_iso8601",'
        '"request_id":"$request_id",'
        '"remote_addr":"$remote_addr",'
        '"method":"$request_method",'
        '"path":"$request_uri",'
        '"status":$status,'
        '"bytes_sent":$bytes_sent,'
        '"duration_ms":$request_time,'
        '"upstream_ms":"$upstream_response_time",'
        '"user_agent":"$http_user_agent",'
        '"referer":"$http_referer"'
      '}';

    access_log /var/log/nginx/access.log json_combined;

    # ...
    proxy_set_header X-Request-ID $request_id;
}
```

Теперь nginx → backend → клиент несут один `X-Request-ID`. Полный путь видно в логах любого слоя.

## 4.5 Маскирование секретов

В `_mask_secrets_processor` (см. 4.2.1) — маскируем по ключам. Дополнительно для тел запроса:

```python
# app/api/middleware/request_body_log.py (опционально, на спорные эндпоинты)
class BodyLogMiddleware(BaseHTTPMiddleware):
    SENSITIVE_PATHS = {"/api/auth/login", "/api/admin/password", "/api/bots"}

    async def dispatch(self, request, call_next):
        if request.method in ("POST", "PATCH", "PUT") and request.url.path not in self.SENSITIVE_PATHS:
            body = await request.body()
            try:
                payload = json.loads(body)
            except Exception:
                payload = None
            if payload:
                bind_contextvars(request_body=_redact(payload))
        return await call_next(request)


def _redact(obj):
    if isinstance(obj, dict):
        return {k: ("***" if k.lower() in SECRET_KEYS else _redact(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    return obj
```

## 4.6 Schema log-событий

Жёсткая схема (типизация поможет в Loki/Grafana):

```typescript
// docs/log_schema.ts (документация)
type LogEvent = {
  ts: string;                  // ISO8601 UTC
  level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';
  event: string;               // namespace.action — bot.lead_created
  request_id: string;
  service: 'backend' | 'admin' | 'bot' | 'nginx' | 'cron';
  // optional
  user_id?: number;
  tg_user_id?: number;
  admin_id?: number;
  bot_id?: number;
  channel_id?: number;
  product_id?: number;
  tracking_link_id?: number;
  // payload-специфичный
  [key: string]: unknown;
};
```

Все события следуют этой схеме.

## 4.7 Где смотреть логи

| Инструмент | Когда |
|-----------|-------|
| `docker compose logs -f backend admin nginx --tail=200` | быстрая проверка прямо сейчас |
| Grafana → Loki | поиск по request_id, user_id, error в окне |
| Sentry → Issue | стек-трейс + breadcrumbs + replay |
| `journalctl -u docker` | если упал сам docker |

Подробнее по Loki/Grafana — следующий документ (`05_observability.md`).

## 4.8 Чек-лист

- [ ] Установить structlog + python-json-logger
- [ ] Создать `app/core/logging.py` с конфигурацией
- [ ] Создать `RequestContextMiddleware`
- [ ] Подключить middleware в `main.py`
- [ ] В nginx добавить `request_id` + JSON access_log
- [ ] В боте — `bind_contextvars` на старте каждого хендлера
- [ ] Заменить `logging.getLogger` → `structlog.get_logger` во всех файлах
- [ ] Перечислить все события из таблицы 4.2.4 и явно их emit'нуть
- [ ] Маскирование secrets — unit-тест
- [ ] Frontend: `lib/logger.ts` + проброс X-Request-ID в `api.ts`
- [ ] Документировать `LogEvent`-схему
