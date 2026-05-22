# 05. Observability — Sentry, Loki/Grafana, Prometheus, OpenTelemetry

## 5.1 Архитектура

```
                          ┌──────────────────────────────┐
                          │     Grafana (UI)             │
                          │  /var/lib/grafana            │
                          └────┬─────────┬─────────┬─────┘
                               │         │         │
                  ┌────────────┴──┐  ┌───┴──────┐  ┌─┴──────────┐
                  │   Loki        │  │ Prom-    │  │  Tempo     │
                  │  (логи)       │  │ etheus   │  │  (трейсы)  │
                  └─────▲─────────┘  └────▲─────┘  └────▲───────┘
                        │                 │             │
                  ┌─────┴──────┐   ┌──────┴─────────┐  ┌┴────────────┐
                  │  Promtail  │   │  app /metrics  │  │  OTel SDK   │
                  │  (агент)   │   │  endpoint      │  │  в backend  │
                  └─────▲──────┘   └──────▲─────────┘  └─────────────┘
                        │                 │
                  ┌─────┴──────────────────┴──────┐
                  │  docker compose (backend,    │
                  │  admin, nginx, bot, cron)    │
                  └───────────────────────────────┘
                        │
                        ▼  ошибки + breadcrumbs
                  ┌───────────────┐
                  │    Sentry     │  (self-hosted или sentry.io)
                  └───────────────┘
```

## 5.2 Sentry — error tracking

Самое важное **первым**. Это даёт мгновенные алерты на 500-ки и unhandled exceptions.

### 5.2.1 Установка

Backend: `sentry-sdk[fastapi]==2.20.0`

```python
# app/main.py — самое начало lifespan / или модуль-импорт
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

sentry_sdk.init(
    dsn=os.environ.get("SENTRY_DSN"),
    environment=os.environ.get("ENV", "production"),
    release=os.environ.get("GIT_SHA", "unknown"),
    traces_sample_rate=0.1,        # 10% запросов с performance-трейсами
    profiles_sample_rate=0.05,     # профайлинг
    send_default_pii=False,        # НЕ слать IP, headers (PII)
    integrations=[
        FastApiIntegration(transaction_style="endpoint"),
        AsyncioIntegration(),
        SqlalchemyIntegration(),
    ],
    before_send=_scrub_pii,
)


def _scrub_pii(event, hint):
    # Удаляем потенциальные секреты из event
    if "request" in event and "headers" in event["request"]:
        for h in ("Authorization", "Cookie", "X-Api-Key"):
            event["request"]["headers"].pop(h, None)
    return event
```

Frontend (Next.js): `@sentry/nextjs==8.x`

```bash
npx @sentry/wizard@latest -i nextjs
```

Создаст `sentry.client.config.ts`, `sentry.server.config.ts`. В `sentry.client.config.ts`:

```ts
import * as Sentry from '@sentry/nextjs';

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  environment: process.env.NEXT_PUBLIC_ENV || 'production',
  tracesSampleRate: 0.1,
  replaysSessionSampleRate: 0,
  replaysOnErrorSampleRate: 1.0,   // полное replay при ошибке
  integrations: [
    Sentry.replayIntegration({ maskAllText: true, blockAllMedia: true }),
  ],
});
```

### 5.2.2 Что попадает в Sentry

- **Automatic**: все `unhandled exceptions`, любой 5xx ответ, console.error в браузере.
- **Manual**: `sentry_sdk.capture_message("custom event")` в особых местах.
- **Breadcrumbs**: предыдущие действия пользователя (последние клики, URL-навигация, fetch) — само ловится Sentry.

### 5.2.3 Алерты

В UI Sentry настроить:
- **Алерт #1**: Новая ошибка с уровнем `error` → Slack-канал `#infobizbot-alerts`.
- **Алерт #2**: Резкий рост (5×) errors per minute → Email.
- **Алерт #3**: Release health regression — на 20% больше ошибок чем предыдущий релиз → Slack.

## 5.3 Loki + Promtail + Grafana — централизованные логи

### 5.3.1 Добавить в `docker-compose.yml`

```yaml
  loki:
    image: grafana/loki:3.3.2
    restart: unless-stopped
    volumes:
      - ./observability/loki-config.yml:/etc/loki/local-config.yaml:ro
      - loki_data:/loki
    networks: [internal]

  promtail:
    image: grafana/promtail:3.3.2
    restart: unless-stopped
    volumes:
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
      - /var/run/docker.sock:/var/run/docker.sock
      - ./observability/promtail-config.yml:/etc/promtail/config.yml:ro
    command: -config.file=/etc/promtail/config.yml
    depends_on: [loki]
    networks: [internal]

  grafana:
    image: grafana/grafana:11.4.0
    restart: unless-stopped
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD}
      GF_USERS_ALLOW_SIGN_UP: "false"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./observability/grafana/provisioning:/etc/grafana/provisioning:ro
    networks: [internal]
    expose:
      - "3000"

volumes:
  loki_data:
  grafana_data:
```

Доступ к Grafana — через nginx subpath `https://grammy.mediann.dev/grafana/` за basic auth (или Grafana admin login).

### 5.3.2 `observability/promtail-config.yml`

Promtail скрапит Docker-логи:

```yaml
server:
  http_listen_port: 9080
  log_level: warn

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: docker
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
        refresh_interval: 5s
    relabel_configs:
      - source_labels: ['__meta_docker_container_name']
        regex: '/(.*)'
        target_label: 'container'
      - source_labels: ['__meta_docker_container_label_com_docker_compose_service']
        target_label: 'service'
    pipeline_stages:
      - json:
          expressions:
            level: level
            event: event
            request_id: request_id
            user_id: user_id
            tg_user_id: tg_user_id
      - labels:
          level:
          event:
          request_id:
```

### 5.3.3 Дашборды Grafana

Заранее провижионим JSON-дашборды через `observability/grafana/provisioning/dashboards/`:

- **«Errors in last 1h»** — `{level="ERROR"} | json` — таблица последних ошибок с request_id.
- **«Request log by request_id»** — переменная `request_id`, фильтр `{request_id="$request_id"}` — собирает все строки для одного запроса включая nginx → backend → bot.
- **«Bot activity»** — `{event=~"bot\\..*"}` — все события бота за окно.
- **«Auth failures»** — `{event="auth.login_failure"}` за час, по IP.
- **«Slow requests»** — `{event="request.completed"} | json | duration_ms > 1000`.

## 5.4 Prometheus — метрики приложения

### 5.4.1 Backend: `/api/metrics` endpoint

Установить `prometheus-fastapi-instrumentator==7.0.0`:

```python
from prometheus_fastapi_instrumentator import Instrumentator

instrumentator = Instrumentator(
    should_group_status_codes=False,
    should_ignore_untemplated=True,
    excluded_handlers=["/api/metrics", "/api/healthz"],
)
instrumentator.instrument(app).expose(app, endpoint="/api/metrics")
```

Это даёт автоматически:
- `http_requests_total{method,status,handler}`
- `http_request_duration_seconds_bucket{...}` (histogram)
- `http_request_size_bytes`
- `http_response_size_bytes`

### 5.4.2 Кастомные метрики

```python
# app/core/metrics.py
from prometheus_client import Counter, Histogram, Gauge

leads_created_total = Counter("leads_created_total", "Total leads created", ["product_id", "has_attribution"])
payments_created_total = Counter("payments_created_total", "Total payments", ["product_id", "period_months"])
subscription_active_gauge = Gauge("subscriptions_active", "Active subscriptions count")
tg_api_calls_total = Counter("telegram_api_calls_total", "Telegram API", ["method", "status"])
tg_api_duration_seconds = Histogram("telegram_api_duration_seconds", "Telegram API duration", ["method"])
expire_due_processed = Counter("expire_due_processed_total", "Processed expired subs by cron")
```

Использовать в коде:
```python
leads_created_total.labels(
    product_id=str(product.id),
    has_attribution=bool(tracking_link),
).inc()
```

### 5.4.3 Prometheus config

```yaml
# observability/prometheus.yml
global:
  scrape_interval: 15s
scrape_configs:
  - job_name: backend
    static_configs:
      - targets: ['backend:8000']
    metrics_path: /api/metrics
  - job_name: nginx
    static_configs:
      - targets: ['nginx-exporter:9113']
  - job_name: postgres
    static_configs:
      - targets: ['postgres-exporter:9187']
```

Добавить в `docker-compose.yml`:
- `prom/prometheus:v3.0.1`
- `nginx/nginx-prometheus-exporter:1.4.0`
- `prometheuscommunity/postgres-exporter:v0.16.0`

### 5.4.4 Главный дашборд Grafana «Infobizbot Overview»

Панели:
- RPS (requests/sec) по endpoint
- Latency p50/p95/p99 по endpoint
- Error rate (4xx vs 5xx)
- Active subscriptions (gauge)
- Leads/payments rate (per minute)
- Telegram API errors rate
- DB connection pool usage
- Container CPU/RAM

## 5.5 OpenTelemetry — distributed tracing

Связывает nginx → backend → SQL → Telegram API в один trace.

### 5.5.1 Установить SDK

```
opentelemetry-distro==0.50b0
opentelemetry-exporter-otlp==1.29.0
opentelemetry-instrumentation-fastapi==0.50b0
opentelemetry-instrumentation-sqlalchemy==0.50b0
opentelemetry-instrumentation-httpx==0.50b0
opentelemetry-instrumentation-asyncpg==0.50b0
```

### 5.5.2 Включить

```python
# app/core/tracing.py
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def setup_tracing(service_name: str, endpoint: str):
    resource = Resource.create({"service.name": service_name, "env": os.environ.get("ENV", "production")})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    trace.set_tracer_provider(provider)
```

После старта FastAPI:
```python
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

FastAPIInstrumentor.instrument_app(app)
SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
HTTPXClientInstrumentor().instrument()
```

### 5.5.3 Tempo (Grafana stack)

```yaml
  tempo:
    image: grafana/tempo:2.7.0
    command: -config.file=/etc/tempo.yaml
    volumes:
      - ./observability/tempo.yml:/etc/tempo.yaml:ro
    networks: [internal]
```

Backend → OTLP gRPC :4317 → Tempo → Grafana показывает waterfall:
```
nginx (100ms) ──► backend POST /api/payments (95ms)
                  ├── SQL: SELECT users (3ms)
                  ├── SQL: SELECT products (2ms)
                  ├── SQL: INSERT payments (5ms)
                  ├── grant_for_payment (50ms)
                  │   ├── SQL: SELECT subscription (4ms)
                  │   ├── HTTPS: api.telegram.org/createChatInviteLink (35ms)
                  │   └── HTTPS: api.telegram.org/sendMessage (10ms)
                  └── SQL: COMMIT (1ms)
```

Это — главное окно для отладки производительности.

## 5.6 Healthchecks

### 5.6.1 Shallow `/api/healthz` (есть)
Возвращает `{"ok": true}` — для load balancer / nginx.

### 5.6.2 Deep `/api/health/deep`

```python
@api.get("/health/deep")
async def deep_health(session=Depends(get_session)) -> dict:
    checks = {}
    # DB
    try:
        await session.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as e:
        checks["db"] = f"fail: {e}"
    # Active bots polling alive
    from app.bot import manager
    checks["bots_polling"] = len(manager._runners)
    # Scheduler
    from app.workers.scheduler import _scheduler
    checks["scheduler"] = "ok" if _scheduler and _scheduler.running else "fail"
    status = "ok" if all(v == "ok" or isinstance(v, int) for v in checks.values()) else "fail"
    return {"status": status, "checks": checks}
```

Для алертов: blackbox-exporter Prometheus раз в 30 сек → `/api/health/deep` → если `status=fail` → Sentry-алерт.

## 5.7 Алерты — список

| # | Условие | Куда | Cooldown |
|---|---------|------|----------|
| 1 | Любой 5xx | Sentry → Slack | per-issue dedup |
| 2 | error rate > 1% за 5 мин | Prometheus AlertManager → Slack | 10 мин |
| 3 | p95 latency > 2 sec за 5 мин | Prometheus | 10 мин |
| 4 | `/api/health/deep` fail | blackbox-exporter → Slack | 1 мин |
| 5 | Telegram API errors > 10/min | Prometheus | 5 мин |
| 6 | DB connections > 80% pool | Prometheus | 10 мин |
| 7 | disk usage > 85% | node-exporter | 1 час |
| 8 | сертификат истекает < 14 дней | blackbox-exporter SSL probe | daily |
| 9 | бот polling crashloop > 3 раза за 5 мин | structured logs (Loki query) + alertmanager | 5 мин |

## 5.8 Минимальный observability MVP (если делать сразу всё некогда)

1. **Sentry** — день 1. Free-tier даёт 5k events/мес.
2. **structlog + request_id** — день 2.
3. **Grafana + Loki + Promtail** — день 3 (готовые dashboards импортируем из dashboards.grafana.com).
4. **Prometheus + базовый instrumentator** — день 4.
5. **OpenTelemetry → Tempo** — неделя 2.

## 5.9 Чек-лист

- [ ] Sentry DSN в env, init в backend и frontend
- [ ] Алерты в Slack
- [ ] structlog + RequestContextMiddleware
- [ ] nginx → JSON access_log + `request_id`
- [ ] docker-compose: loki + promtail + grafana
- [ ] Готовые dashboards Grafana (импорт)
- [ ] prometheus-fastapi-instrumentator + `/api/metrics`
- [ ] Кастомные метрики (`leads_created`, `payments_created`, `subscriptions_active`)
- [ ] Prometheus + Postgres exporter + nginx exporter
- [ ] OpenTelemetry tracing → Tempo
- [ ] `/api/health/deep` + blackbox monitoring
- [ ] AlertManager с правилами из 5.7
- [ ] Документация: «Куда смотреть когда что-то случилось»
