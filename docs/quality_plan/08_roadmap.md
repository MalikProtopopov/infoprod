# 08. Roadmap — 5 фаз внедрения

Дорожная карта от «0 тестов» до «98% coverage + полный observability stack».

## Фаза 1 — Foundation (неделя 1–2)

**Цель**: каркас на котором всё остальное держится. После этой фазы любой новый код пишется с тестами и логами по умолчанию.

### Задачи
- [ ] Создать `backend/requirements-dev.txt`, `pytest.ini`, `pyproject.toml`
- [ ] Установить `pytest`, `pytest-asyncio`, `pytest-cov`, `pytest-httpx`, `testcontainers`, `factory-boy`, `ruff`, `mypy`
- [ ] Создать `tests/conftest.py` с базовыми фикстурами (engine, session, api_client, admin_client, factories)
- [ ] Создать `tests/factories.py` для всех 9 моделей
- [ ] Написать 5 базовых smoke-тестов (login, healthz, tracking_link.create, payment.create, lead.update)
- [ ] Установить `vitest`, `@testing-library/react`, `MSW` во frontend
- [ ] Создать `admin/__tests__/setup.ts`, `mocks/server.ts`, `mocks/handlers.ts`
- [ ] Написать тесты на `Button`, `Input`, `api.ts` (минимум 10 тестов)
- [ ] Внедрить `structlog`, `RequestContextMiddleware`
- [ ] Подключить **Sentry** в backend и frontend (free tier)
- [ ] Настроить GitHub Actions: lint + test (без E2E пока)
- [ ] Branch protection на `main` (require status checks)
- [ ] Добавить `pre-commit` hooks
- [ ] Добавить `.codecov.yml` для tracking coverage

### Acceptance
- ✅ `pytest` запускается локально и в CI, 5 тестов проходят.
- ✅ `npm test` запускается локально и в CI, 10 тестов проходят.
- ✅ В Sentry прилетает тестовая ошибка (вручную раскоменченый `raise Exception` где-нибудь).
- ✅ Все логи backend в JSON, есть `request_id` в каждой строке.
- ✅ `git push --force main` запрещён без зелёного CI.

### Метрики
| Метрика | До | После |
|---------|----|----|
| Coverage backend | 0% | **≥10%** |
| Coverage frontend | 0% | **≥10%** |
| Время «увидеть ошибку в проде» | визуальный осмотр | мгновенно через Sentry |
| Время CI | — | < 4 мин (без E2E) |

---

## Фаза 2 — Backend coverage 80% (неделя 3–4)

**Цель**: основная масса unit + integration тестов backend. Все services и api endpoints покрыты.

### Задачи
- [ ] `tests/unit/services/test_tracking_links.py` (CRUD + slug-валидация + property-based) → 100%
- [ ] `tests/unit/services/test_subscriptions.py` (grant/revoke/extend/expire_due, frozen time) → 100%
- [ ] `tests/unit/services/test_telegram.py` (моки через pytest-httpx) → 95%
- [ ] `tests/unit/bot/test_handlers_start.py` (slug → product.code → fallback, first-touch, current_link) → 95%
- [ ] `tests/unit/bot/test_handlers_lead.py` (TTL, snapshot UTM, deactivated link) → 95%
- [ ] `tests/unit/bot/test_manager.py` (start/stop/sync с моком aiogram Bot) → 80%
- [ ] `tests/unit/api/test_auth.py` (login успех/ошибка/rate-limit, /me, logout) → 100%
- [ ] `tests/unit/api/test_payments.py` (создание + admin_id + tracking_link inherit + auto-paid lead) → 100%
- [ ] `tests/unit/api/test_tracking_links.py` (CRUD + QR + коллизии + deactivate) → 100%
- [ ] `tests/unit/api/test_stats.py` (sources с разными group_by и фильтрами) → 95%
- [ ] `tests/unit/api/test_leads.py` (status update + автотаймстампы) → 100%
- [ ] `tests/unit/core/test_security.py` (bcrypt, JWT, decode_token) → 100%
- [ ] `tests/integration/test_full_purchase_flow.py` → 1 сценарий end-to-end
- [ ] `tests/integration/test_expire_due_cron.py` → freezegun + APScheduler manual run

### Acceptance
- ✅ Coverage backend `app/services/` = 100%, `app/api/` = 100%, `app/bot/` ≥ 90%.
- ✅ Mutation score ≥ 80% на `services/subscriptions.py` и `services/tracking_links.py` (через `mutmut`).
- ✅ В CI `pytest -n 4` < 90 секунд.
- ✅ Codecov показывает зелёный.

### Метрики
| Метрика | До | После |
|---------|----|----|
| Coverage backend | 10% | **≥80%** |
| Регрессии после деплоя | ?? | падающие тесты ловятся в CI |

---

## Фаза 3 — Frontend coverage 80% + E2E (неделя 5–6)

**Цель**: фронт покрыт, golden flows автоматизированы.

### Задачи
- [ ] Тесты всех `components/*` (Button, Card, Sheet, Input, Select, Pill, Stat, UserPicker, Sparkline...)
- [ ] Тесты `lib/api.ts` (все ветки)
- [ ] Тесты каждой страницы `app/(dash)/*`:
  - Логин/логаут
  - Bots: добавление, удаление с зависимыми каналами (409)
  - Channels: проверка кнопки disabled при отсутствии ботов
  - Products: создание / редактирование / коллизия code
  - Products/[id]: создание tracking_link, QR
  - Users: поиск, открытие карточки
  - Users/[id]: редактирование notes
  - Leads: фильтр статусов, открытие деталки
  - Payments: создание через UserPicker, валидация period с 0-ценами
  - Subscriptions: revoke + extend
  - Sources: фильтры, **regression test** на infinite loop
- [ ] Создать `e2e/` подпроект
- [ ] `docker-compose.test.yml` с mockoon
- [ ] `telegram-mock.json` со всеми нужными методами TG
- [ ] Playwright config + 10 spec-файлов
- [ ] Job `e2e` в CI после `unit + build`
- [ ] Регрессионный тест `2026_05_22_sources_infinite_loop.test.tsx`

### Acceptance
- ✅ Coverage frontend `lib/` = 100%, `components/` ≥ 90%, страницы ≥ 85%.
- ✅ Все 10 E2E-сценариев зелёные в Chrome + Firefox.
- ✅ Trace viewer открывается на падении.

### Метрики
| Метрика | До | После |
|---------|----|----|
| Coverage frontend | 10% | **≥80%** |
| E2E golden flows | 0 | 10 |
| Время CI с E2E | — | < 15 мин |

---

## Фаза 4 — Observability stack (неделя 7)

**Цель**: централизованные логи + метрики + трейсинг + дашборды.

### Задачи
- [ ] Добавить в `docker-compose.yml`:
  - `loki:3.3.2`
  - `promtail:3.3.2`
  - `grafana:11.4.0`
  - `prometheus:v3.0.1`
  - `nginx-prometheus-exporter`
  - `postgres-exporter`
  - `tempo:2.7.0` (для трейсов)
- [ ] Сконфигурировать `promtail-config.yml` для Docker logs
- [ ] Сконфигурировать `prometheus.yml` для скрапа
- [ ] Подключить `prometheus-fastapi-instrumentator` в backend → `/api/metrics`
- [ ] Кастомные метрики: `leads_created_total`, `payments_created_total`, `subscriptions_active`
- [ ] OpenTelemetry в backend → Tempo
- [ ] Provisioning Grafana:
  - Дашборд «Infobizbot Overview» (RPS, latency, error rate)
  - Дашборд «Logs» (поиск по request_id)
  - Дашборд «Bot activity» (события из логов)
  - Дашборд «Database» (Postgres exporter metrics)
- [ ] AlertManager + правила:
  - Error rate > 1%
  - p95 latency > 2s
  - `/health/deep` fail
  - TG API errors > 10/min
  - Polling crashloop > 3 раз/5 мин
- [ ] Алерты → Slack (или Email)
- [ ] Nginx subpath `/grafana/` за basic auth

### Acceptance
- ✅ Можно открыть https://grammy.mediann.dev/grafana/ и видеть RPS/errors/latency в реальном времени.
- ✅ Поиск по `request_id` находит все строки одного запроса через nginx + backend + bot.
- ✅ В Tempo есть распределённые трейсы FastAPI + SQL + Telegram API.
- ✅ Тестовая ошибка в Sentry триггерит Slack-алерт за 30 сек.

### Метрики
| Метрика | До | После |
|---------|----|----|
| MTTD (mean time to detect) | > часов | **< 1 минуты** |
| Возможность ретроспективы | нет | да (Loki хранит 7д) |
| Видимость прод-нагрузки | docker stats | полный Grafana stack |

---

## Фаза 5 — Polish и 98% (неделя 8–9)

**Цель**: добить покрытие до 98%, добавить audit_log, RBAC, security hardening.

### Задачи
- [ ] Покрыть оставшиеся edge-cases: ошибки БД, ошибки TG API, race conditions
- [ ] Mutation testing на ключевых модулях `mutmut run --paths-to-mutate=app/services/`
- [ ] Property-based тесты для всех валидаторов (slug, code, password)
- [ ] Backend coverage до 98% (отчёт codecov)
- [ ] Frontend coverage до 98%
- [ ] Миграция `audit_log` + сервис + декоратор `@audit`
- [ ] Применить `@audit` на все mutating endpoints
- [ ] UI: страница `/audit` (только super_admin)
- [ ] Миграция: роли `super_admin` / `admin` / `operator`
- [ ] Декоратор `require_role` + применение
- [ ] Security testing:
  - `bandit -lll` чисто
  - `pip-audit --strict` чисто
  - `npm audit --audit-level=high` чисто
  - Trivy scan образов чисто
  - OWASP ZAP baseline на staging
- [ ] CSP в режиме Report-Only → анализ нарушений → enforcement
- [ ] Gitleaks в CI
- [ ] CodeQL еженедельно
- [ ] Docs: `docs/runbooks/` с playbook'ами:
  - «БД отвалилась — что делать»
  - «Бот перестал отвечать — что делать»
  - «Sentry alert на 5xx — что делать»
- [ ] Документация по ротации секретов и backup

### Acceptance
- ✅ Coverage 98% + 98%, заблокировано CI.
- ✅ Mutation score ≥ 80% на критичных модулях.
- ✅ Любая mutating-операция оставляет след в `audit_log`.
- ✅ Все 3 роли работают, permission-тесты в E2E.
- ✅ securityheaders.com показывает grade A+.
- ✅ Runbooks написаны и проверены drill'ом.

### Метрики финальные
| Метрика | Target | Достигнуто |
|---------|--------|-----------|
| Coverage backend | ≥98% | ✅ |
| Coverage frontend | ≥98% | ✅ |
| E2E flows | 10 | ✅ |
| MTTD | <1 мин | ✅ |
| MTTR | <30 мин | ✅ |
| CI время | <15 мин | ✅ |
| Mutation score | ≥80% | ✅ |
| Security grade | A+ | ✅ |
| Audit trail | 100% mutating | ✅ |

---

## Сводка

| Фаза | Длительность | Прирост ценности |
|------|--------------|------------------|
| 1. Foundation | 2 нед | каркас + Sentry + структурные логи |
| 2. Backend tests | 2 нед | 80% coverage, регрессии ловятся в CI |
| 3. Frontend + E2E | 2 нед | UI не ломается, golden flows зелёные |
| 4. Observability | 1 нед | видимость прода в реальном времени |
| 5. Polish | 2 нед | 98% + RBAC + audit + security |

**Итого: ~9 рабочих недель** при работе одного разработчика full-time. Можно ускорить вдвое если параллелить (backend + frontend + observability разными людьми).

## Что после Phase 5

- **Load testing** (k6): нагрузка 100 RPS, 1000 одновременных коннектов
- **Chaos engineering**: убийство случайного контейнера
- **Multi-region failover**
- **GDPR compliance audit** с юристом
- **SOC2-like documentation**

Эти темы не покрыты этим планом — они для более зрелой стадии продукта.
