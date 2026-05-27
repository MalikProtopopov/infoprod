# 08. Аудит качества рефакторинга (фичефлаги + гигиена кода)

> Проверка по запросу: крупные файлы, дублирование, циклические импорты, импорты
> внутри функций. Аудит охватывает изменения фичефлагов (фазы 1–6) и общее
> состояние проекта вокруг затронутых зон. Дата: 2026-05-26.

## Вердикт (TL;DR)

- **Фичефлаг-рефакторинг — чистый.** Новый модуль `app/core/features.py` зависит только
  от stdlib, не создаёт циклов, есть единый источник истины + каскад зависимостей,
  покрыт тестами (28 шт.). Гейтинг вынесен в тестируемую функцию `build_api_router()`.
- **Найдено и уже исправлено:** 2 импорта внутри функций, которые я сам же и добавил
  (`deps.py`, `scheduler.py`) — были не нужны, поднял на уровень модуля.
- **Циклических импортов на рантайме нет** (`import app.main` работает). Есть один
  *настоящий* цикл `handlers ↔ scheduled_messages ↔ manager`, который намеренно
  разорван локальными импортами — это корректно, трогать опасно.
- **Главные пред-существующие смелы** (не из этого рефактора, рекомендации ниже):
  очень крупные файлы (`stats.py` 1009, `handlers.py` 838, студия воронки 1076),
  ~много «ленивых» локальных импортов в API-эндпойнтах, дублирование фабрик в `conftest.py`.

---

## 1. Крупные файлы

### Backend (LOC, `backend/app`)
| Файл | LOC | Оценка |
|---|---:|---|
| `api/stats.py` | 1009 | ⚠️ Большой. 6 эндпойнтов с тяжёлыми SQL-агрегатами. Кандидат на разбиение: `stats/overview.py` (ядро) + `stats/analytics.py` (под флагом). Уже логически разделён на 2 роутера — осталось разнести по файлам. |
| `bot/handlers.py` | 838 | ⚠️ Монолит всех хендлеров. План §3.6 Шаг B предусматривает разбивку на `handlers/{core,funnels,quizzes,forms}.py` с подключением роутеров по флагам. Сейчас гейтинг сделан guard'ами (Шаг A) — приемлемо. |
| `api/funnels.py` | 593 | Терпимо (3 роутера в одном файле). |
| `workers/scheduled_messages.py` | 472 | Терпимо для воркера с медиа-логикой. |
| `services/step_flow.py` | 458 | Терпимо. |

### Frontend (LOC, `admin`)
| Файл | LOC | Оценка |
|---|---:|---|
| `app/(dash)/funnels/[id]/edit/page.tsx` | 1076 | ⚠️ Очень большой. Студия воронки: 5+ под-компонентов в одном файле (`StepEditor`, `StepKindSelector`, `QuizFormPicker`, …). Кандидат на вынос под-компонентов в `components/funnel-studio/`. |
| `app/(dash)/layout.tsx` | 593 | Терпимо (иконки занимают ~110 строк; можно вынести в `components/icons.tsx`). |
| `app/(dash)/quizzes/[id]/page.tsx` | 556 | Терпимо. |

**Вывод:** новых «огромных» файлов рефактор не создал. Самые крупные — пред-существующие
(`stats.py`, студия). Не блокеры, но первыми кандидатами на декомпозицию.

---

## 2. Циклические импорты

- **Рантайм-циклов нет:** `import app.main` и `import app.workers.scheduler` отрабатывают без ошибок.
- **Модели** (`models/channel.py`, `bot.py`, `product.py`) ссылаются друг на друга через
  `if TYPE_CHECKING:` — идиоматично и корректно, в рантайме импорта нет.
- **Один настоящий цикл, разорванный намеренно:**
  ```
  bot/manager.py ──(top)──▶ bot/handlers.py
  bot/handlers.py ──(LOCAL)──▶ workers/scheduled_messages.py   (handlers.py:505)
  workers/scheduled_messages.py ──(LOCAL)──▶ bot/manager.py    (scheduled_messages.py:331)
  ```
  Локальные импорты здесь **необходимы** — без них при загрузке модулей будет
  `ImportError`. Это корректный приём; выносить наверх нельзя.
- **`app/core/features.py` не участвует ни в каких циклах** — импортирует только
  `os`, `dataclasses`, `functools`. Поэтому все `from app.core.features import ...`
  безопасны на уровне модуля (что и подтвердило исправление в §5).

**Вывод:** циклов, требующих вмешательства, нет. Существующий цикл инкапсулирован.

---

## 3. Импорты внутри функций (69 шт. в `backend/app`)

Разбивка по природе:

| Категория | Кол-во | Оценка | Примеры |
|---|---:|---|---|
| Под `TYPE_CHECKING` (модели) | — | ✅ Идиоматично | `models/channel.py:12-13` |
| **Необходимые** (разрыв реального цикла) | ~3 | ✅ Оставить | `handlers.py:505` → scheduled_messages; `scheduled_messages.py:331` → manager |
| **Ленивые / «по привычке»** (цикла нет, можно поднять) | ~много | 🟡 Пред-существующий стиль | `stats.py:606-609`, `users.py:176-182` (`from app.models.* import ...` внутри эндпойнтов); `scheduled_messages.py:332-333` → services |
| **Мои, добавленные в рефакторе** | 2 | ✅ **Исправлено** | было: `deps.py` и `scheduler.py` импортировали `features` внутри функции |

Детали по «ленивым» (на будущее, низкий приоритет): импорты моделей внутри
эндпойнтов `stats.py`/`users.py`/`funnels.py` цикла не образуют (модели тянут только
`db.base`), поэтому их можно поднять на уровень модуля — это чисто косметика и
читаемость. Трогать массово в рамках фичефлагов не стал, чтобы не раздувать диф.

**Что исправил сейчас:**
- `app/api/deps.py` — `from app.core.features import is_enabled` поднят в шапку модуля
  (был внутри `require_feature`).
- `app/workers/scheduler.py` — то же (был внутри `start()`).
- Проверено: `import app.main` ок, 28 тестов фичефлагов зелёные.

---

## 4. Дублирование кода

| Место | Оценка |
|---|---|
| `backend/tests/conftest.py` — фабрики `_Make` и `_Committed` | 🟡 **~30 почти одинаковых методов** (15×2). Пред-существующее тест-дублирование. Можно свести к одной параметризованной реализации (`flush` vs `commit`). Не блокер. |
| Список фич в нескольких местах | 🟢 Контролируемо. Источник — `FEATURE_REGISTRY`. Бэкенд `FEATURE_ROUTERS` сверяется тестом `test_feature_routers_cover_registry_exactly` (drift невозможен). |
| Фронт: ключи фич в `layout.tsx` (`ROUTE_FEATURE` + `feature:` в `NAV_GROUPS`) и в `isOn(...)` по страницам | 🟡 Сейчас **совпадают 1-в-1** с реестром (9 ключей), но **не покрыты тестом на drift**. Риск: переименование ключа на бэке молча рассинхронит фронт. Рекомендация ниже (P2). |
| Guard-паттерн `if not is_enabled(...)` в боте | 🟢 Повторение оправдано — разные точки входа, выносить незачем. |
| `(magnets ǀǀ [])` в студии | 🟢 Защищённое чтение, ок. |

---

## 5. Оценка собственно фичефлаг-кода

- ✅ **Единый источник истины** — `FEATURE_REGISTRY` + `resolve()`; и бэкенд, и фронт
  читают отрезолвленный набор из `/config/features`.
- ✅ **Каскад зависимостей** в одном месте (`resolve()`), покрыт unit-тестами.
- ✅ **Тестируемость** — регистрация роутеров вынесена в `build_api_router(features)`
  (чистая функция), а не делается «по месту» при импорте.
- ✅ **Без циклов** — `features.py` на stdlib.
- ✅ **Обратная совместимость** — `useFeatures().isOn` оптимистичен (старый бэк без
  `/config/features` → всё включено, без падений и мигания меню).
- ✅ **«Выключено ≠ удалено»** соблюдён — гейтятся только точки входа, схема БД полная,
  тесты гоняются на полном наборе фич.
- ⚠️ Исправленные 2 локальных импорта (см. §3).

---

## 6. Рекомендации (приоритизированные)

**P1 — стоит сделать до мёржа (дёшево, повышает надёжность):**
- [x] Поднять 2 локальных импорта `features` (`deps.py`, `scheduler.py`).
- [x] Drift-guard ключей фич: типизированный `FeatureKey` + `FEATURE_KEYS` +
  централизованный `ROUTE_FEATURE` (`admin/lib/features.ts`) + тесты
  (`admin/__tests__/lib/features.test.ts`, `backend/.../test_features.py::test_registry_matches_canonical_keys`).

**P2:**
- [x] `stats.py` (1009) → пакет `app/api/stats/`: `overview.py` (ядро) + `analytics.py` (под `analytics`) + `__init__.py` (реэкспорт). 49 stats-тестов зелёные.
- [x] `bot/handlers.py` (838) → пакет `app/bot/handlers/`: `common.py` + роутеры `core/leads/funnels/quizzes/forms`. `build_dispatcher()` подключает по флагам (`enabled_routers()`), guard'ы сохранены, back-compat реэкспорт. Тесты-monkeypatch переписаны на сабмодули.

**P3 — техдолг:**
- [x] Под-компоненты студии воронки (`SectionHeader`, `StepKindSelector`, `QuizFormPicker`) вынесены в `components/funnel-studio/` (page 1076 → 960 LOC).
- [x] `conftest.py`: `_Make`/`_Committed` сведены к одной спецификации `_FACTORY_DEPS` + `_FactoryHelper` (~200 строк дублирования удалено).
- [x] Подняты «ленивые» импорты моделей в `stats/analytics.py`, `users.py`, `funnels.py` (cycle-breaking сервис-импорты оставлены локальными).

---

## 8. Статус реализации (2026-05-26)

Все пункты §6 реализованы на ветке `feature/modular-feature-flags`. Проверка:

| Слой | Результат |
|---|---|
| Backend, полный прогон | **514 passed**, 1 xfail (старый flaky), 1 pre-existing fail (`test_funnel_detail_includes_media` — падает и на базе, не связан) |
| Frontend `tsc --noEmit` | чисто (кроме pre-existing `Card.test.tsx`) |
| Frontend vitest | **163 passed** |

Самый рискованный пункт (split `handlers.py`, трогает живой бот) сделан в «безопасной»
форме: guard'ы сохранены, роутеры подключаются по флагам, поведение идентично; перед
деплоем на прод желательна ручная проверка бота на стенде.

---

## 7. Как воспроизвести проверки

```bash
# Крупнейшие файлы
find backend/app -name '*.py' | xargs wc -l | sort -rn | head
find admin/app admin/components admin/lib -name '*.tsx' -o -name '*.ts' | xargs wc -l | sort -rn | head

# Импорты внутри функций (indented import/from)
grep -rnE '^[[:space:]]+(import |from app\.)' backend/app --include='*.py' | grep -v TYPE_CHECKING

# Циклов нет на рантайме
python -c "import app.main; print('ok')"   # из backend/

# Тесты фичефлагов
TESTCONTAINERS_RYUK_DISABLED=true python -m pytest tests/unit/test_features.py \
  tests/unit/test_feature_gating.py tests/unit/test_bot_feature_gating.py -q --no-cov
```
