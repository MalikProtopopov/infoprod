# 00. Анализ текущего состояния и цели

## 0.1 Аудит «как сейчас»

### Тесты
- **Backend**: 0 тестов. Нет `tests/` директории, нет `pytest.ini`, нет coverage-конфигурации.
- **Frontend**: 0 тестов. Нет Vitest/Jest, нет `__tests__/` директорий.
- **E2E**: 0. Только ручные smoke-тесты через curl после деплоя.
- **Coverage сейчас: 0% / 0% / 0%.**

### Логи
- **Backend**: `logging.basicConfig(level=INFO, format="%(asctime)s %(levelname)-7s %(name)s — %(message)s")` — обычный текст, без request_id, без structured payload.
- **Frontend**: только `console.error` в catch-блоках. Нет sourcemaps в проде.
- **Хранение**: только `docker compose logs` в памяти контейнера, теряется при restart.
- **Поиск/фильтр**: невозможен ни по чему — только `grep`.

### Error tracking
- **Нет**. Падения backend и frontend нигде не агрегируются.

### Метрики
- **Нет**. Latency, error rate, RPS — неизвестны. Только `docker stats` для CPU/memory.

### CI/CD
- **Нет CI**. Деплой — ручной rsync + docker compose build.
- Линтеров нет.
- Pre-commit hooks нет.
- Зависимости не сканируются на CVE.

### Контроль качества PR
- В репозитории нет описания процесса. Все коммиты пушатся в `main`.

## 0.2 Что это даёт нам сейчас

| Сценарий | Что происходит сейчас | Что должно быть |
|----------|----------------------|----------------|
| Юзер пишет «у меня баг X» | Нет request_id → невозможно найти его запросы | По времени + tg_user_id за 30 сек находим все его действия |
| Сервис упал ночью | Узнаём только когда заметим визуально | Pager Sentry / алерт в Slack |
| Регрессия после деплоя | Замечаем на проде | CI блокирует merge, тесты ломаются |
| «Раньше работало, теперь нет» | Бисектим вручную через git log | Можно сразу глянуть git blame + последние тесты |
| Долгий запрос в API | Не знаем какой и почему | p95 latency в Grafana, OTel-трейс показывает SQL и Telegram-вызов |
| Один пользователь съел весь rate-limit | Нет логов попыток | structured log с IP + user-agent + причиной 429 |
| Кто-то меняет данные | Не знаем кто и когда | audit_log по каждому write-эндпоинту |

## 0.3 Цели в цифрах (KPI)

| Метрика | Target |
|---------|--------|
| Backend coverage | **≥98%** на `app/services/`, `app/api/` |
| Frontend coverage | **≥98%** на `lib/`, **≥85%** на UI-компонентах |
| E2E coverage | **9 golden flows** (логин, добавление бота, продукта, канала, продажа, отзыв, продление, заявка, кампания) |
| Mean time to detect (MTTD) | < 1 минута (через Sentry + healthcheck) |
| Mean time to resolve (MTTR) | < 30 минут (структурированный лог + git blame + откат) |
| CI время | < 4 минут на PR |
| Время до 1-й строки логов от падения | < 2 секунд |
| Falsy negative rate в тестах | < 1% (mutation score ≥80% на критичных модулях) |
| % deploy с откатом | < 5% (CI ловит проблемы заранее) |

## 0.4 Гипотеза «что покрыть в первую очередь»

Высший приоритет — модули где **уже были баги в этом проекте**:

1. `bot/handlers.py` — мы трижды переписывали логику /start (slug-резолвер, first-touch, TTL) → unit + integration тесты.
2. `services/subscriptions.py` — grant/revoke/extend, нашли баг с «extend не выдаёт invite» → отдельный тест на каждый сценарий.
3. `api/payments.py` — каскад на subscription + Telegram side-effect → integration с моком Telegram.
4. `services/tracking_links.py` — slug-генератор и валидация коллизий → unit + property-based.
5. `bot/manager.py` — multi-bot polling, был баг с crashloop → тест с мок-бесконечным polling.

Низкий приоритет (но в 98% войдёт):
- Pydantic-схемы (валидация работает «бесплатно»)
- Простые getters в API (list_users и т.п.)
- Тривиальные миграции

## 0.5 Принципы написания тестов

1. **Один тест — одна проверка.** Не пихать 5 ассертов в одну функцию.
2. **AAA**: Arrange → Act → Assert. Никаких мутаций в Assert.
3. **Без сети к настоящему Telegram / Google / etc.** Только моки.
4. **Каждый тест начинает с чистой БД.** Fixture-rollback на каждый тест.
5. **Detrminism**: фиксируем `now()` через `freezegun`, фиксируем random через seed.
6. **Test names — это документация**. `test_grant_creates_subscription_and_sends_invite_link` лучше чем `test_grant_1`.
7. **Failing test перед фиксом бага**. Регрессионный тест должен падать на старом коде и проходить на новом.

## 0.6 Что вне скоупа этого плана

- **Load testing** (k6, Locust) — отдельный сюжет когда понадобится 1000 RPS.
- **Chaos engineering** (Chaos Mesh) — для multi-instance.
- **A/B-фреймворк** — отдельный продуктовый сюжет.
- **GDPR-аудит** — нужен с юристом, не разработчиками.
- **Backup/DR** — отдельный документ для production-операторов.

Эти темы упомянуты в `06_ci_cd.md` и `07_audit_security.md` тонко, но детально не разбираются.
