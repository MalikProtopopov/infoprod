# Quality plan: тесты, логи, observability

План покрытия проекта тестами (target **98%**), структурированными логами, метриками, трейсингом и error tracking. Документы предназначены для последовательного внедрения за **8–10 рабочих недель**.

## Индекс

| # | Файл | О чём |
|---|------|------|
| 00 | [overview.md](00_overview.md) | Текущее состояние, цели, KPI, выбранный стек |
| 01 | [backend_tests.md](01_backend_tests.md) | pytest, async, фикстуры, моки Telegram, coverage |
| 02 | [frontend_tests.md](02_frontend_tests.md) | Vitest, Testing Library, MSW, MockServer |
| 03 | [e2e_tests.md](03_e2e_tests.md) | Playwright + docker compose, golden flows |
| 04 | [logging.md](04_logging.md) | structlog, request_id, JSON-формат, schema |
| 05 | [observability.md](05_observability.md) | Sentry, Loki/Grafana, Prometheus, OpenTelemetry, healthchecks |
| 06 | [ci_cd.md](06_ci_cd.md) | GitHub Actions, pre-commit, security scan, branch protection |
| 07 | [audit_security.md](07_audit_security.md) | audit_log таблица, RBAC, security testing, secrets |
| 08 | [roadmap.md](08_roadmap.md) | Дорожная карта в 5 фаз с метриками успеха |
| 09 | [tooling.md](09_tooling.md) | Полный список инструментов, версии, готовые конфиги |

## Главные цели

1. **Обнаружить баг за 30 секунд** — структурированные логи + `request_id` сквозной.
2. **Понять контекст** — что делал юзер/админ/бот перед ошибкой, какие были параметры.
3. **Снизить регрессии** — 98% test coverage на критичных модулях.
4. **Алерты в реальном времени** — Sentry + Slack/Email при ошибках 5xx и unhandled exceptions.
5. **Метрики продукта и системы** — Grafana дашборды.
6. **Не сломать production** — CI блокирует merge при падении тестов или регрессии coverage.

## Стек (выбранные инструменты)

| Слой | Инструмент | Почему |
|------|-----------|--------|
| Python tests | **pytest 8** + pytest-asyncio + pytest-cov + httpx AsyncClient | Стандарт, лучшее async-API |
| Python моки | **pytest-httpx** + aiogram TestBot | Изоляция от Telegram |
| Python DB | **testcontainers-postgres** | Реальная PG в контейнере на каждый тест-ран |
| Python линт | **ruff** + **mypy** | Самый быстрый, типы |
| Frontend tests | **Vitest** + **@testing-library/react** + **MSW** | Современный jest-совместимый, mock service worker |
| E2E | **Playwright** | Лучший в классе, multi-browser, trace viewer |
| Логи | **structlog** (Python) + **pino** (Node) — JSON в stdout | Структурированно с самого начала |
| Сбор логов | **Loki** + Promtail + **Grafana** в docker compose | Self-hosted, copy-paste дашборды |
| Error tracking | **Sentry** (self-hosted или free tier) | Стек-трейсы, релизы, breadcrumbs |
| Метрики | **Prometheus** + Grafana | Стандарт |
| Трейсинг | **OpenTelemetry** → Tempo (Grafana stack) | Сквозной трейсинг запросов |
| CI | **GitHub Actions** | Бесплатно, нативно для PR |
| Pre-commit | **pre-commit** (ruff, mypy, eslint, prettier) | Лок перед коммитом |
| Security scan | **bandit** + **pip-audit** + **npm audit** + **Trivy** | OWASP, CVE |
| Mutation testing | **mutmut** (опционально на ключевых модулях) | Доказывает реальную силу тестов |

## Сроки

| Фаза | Что делается | Срок |
|------|-------------|------|
| 1. Foundation | pytest + Vitest, structlog, request_id, Sentry, CI | 2 нед |
| 2. Backend coverage 80% | Unit + integration по services/api/bot | 2 нед |
| 3. Frontend coverage 80% + E2E | Vitest + Playwright | 2 нед |
| 4. Observability stack | Loki/Grafana/Prometheus + OTel | 1 нед |
| 5. Polish → 98% | Mutation testing, edge cases, audit log, security scan | 2 нед |

**Итого: ~9 недель** до production-ready quality bar.
