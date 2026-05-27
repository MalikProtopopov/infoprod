# 07. Модульная архитектура с фичефлагами

> Цель: сделать функционал бота/админки **модульным** — чтобы для каждого клиента
> можно было включать/выключать фичи (воронки, лидмагниты, квизы, формы, аналитику…)
> через `.env`, при этом:
> - код выключенной фичи остаётся в репозитории, корректным и покрытым тестами
>   («выключено ≠ удалено»), чтобы над ней можно было продолжать работать;
> - выключение одной фичи не ломает остальные потоки;
> - один и тот же образ (backend + admin) обслуживает всех клиентов, конфиг — только в `.env`.

Документ — пошаговая инструкция к действию. Разбит на фазы; каждая фаза
самостоятельна и **по умолчанию ничего не меняет** (все флаги = `true`), поэтому
существующий деплой mediann/grammy не затрагивается, пока клиент явно не отключит фичу.

---

## 0. Краткая карта «как сейчас» (факты из анализа кода)

- **Backend**: FastAPI, все роутеры подключаются в `backend/app/main.py:100‑120` под префиксом `/api`.
- **RBAC**: `backend/app/api/deps.py` — `current_admin`, `require_role`, `require_perm`.
- **Scheduler**: `backend/app/workers/scheduler.py` — 2 джобы: `expire_due` (1ч, подписки) и `scheduled_messages` (30с, воронки).
- **Бот**: монолитный `backend/app/bot/handlers.py` (один `router`, клонируется на каждого бота в `build_dispatcher()`).
- **Config**: `backend/app/core/config.py` — `pydantic-settings`, флагов сейчас нет.
- **Frontend**: Next.js App Router; меню — массив `NAV_GROUPS` в `admin/app/(dash)/layout.tsx:153`; API‑клиент `admin/lib/api.ts`; механизма получения конфига с бэка сейчас нет.

---

## 1. Таксономия фич и граф зависимостей

### 1.1. Ядро (не отключается — `core`)
Эти модули — фундамент, на них висят все остальные. Флага не имеют.

| Модуль ядра | API | Таблицы |
|---|---|---|
| Auth / RBAC | `auth.py`, `audit_log.py` | `admins`, `audit_log` |
| Боты | `bots.py` | `bots` |
| Каналы | `channels.py` | `channels` |
| Продукты (каталог) | `products.py` | `products` |
| Пользователи | `users.py` | `users` |

### 1.2. Отключаемые модули и их зависимости (DAG)

`A → B` читается как «A требует B (B должен быть включён)».

```
                        ┌──────── core (catalog/users/bots/channels/auth) ────────┐
                        │                                                          │
   analytics ───────────┤                                                          │
   tracking_links ──────┤                                                          │
   leads ───────────────┤                                                          │
   monetization ────────┘   (payments + subscriptions + джоба expire_due)          │
                                                                                    │
   funnels ─────────────────────────────────────────────────────────────────────► core
      ▲   ▲   ▲   ▲
      │   │   │   └── funnel_triggers  → funnels
      │   │   └────── lead_magnets     → funnels
      │   └────────── quizzes          → funnels
      └────────────── forms            → funnels (+ создаёт leads)
```

**Ключевой вывод:** `funnels` — хаб доставки. `quizzes`, `forms`, `lead_magnets`,
`funnel_triggers` доставляются/запускаются через шаги воронки и воркер
`scheduled_messages`. Поэтому **выключение `funnels` обязано каскадно выключить их все**.

### 1.3. Реестр фич (single source of truth)

| ключ флага | человекочит. | зависит от | API‑роутеры | scheduler | бот: точки входа / хуки |
|---|---|---|---|---|---|
| `leads` | Заявки | core | `leads` | — | callback `lead:` |
| `monetization` | Платежи и подписки | core | `payments`, `subscriptions` | `expire_due` | `/my` |
| `tracking_links` | Трекинг‑ссылки | core | `tracking_links` | — | разбор slug в `/start` |
| `analytics` | Аналитика | core | `stats` (кроме `/overview` — он в ядре, см. §3.4) | — | — |
| `funnels` | Воронки | core | `funnels`, `funnel_entries`, `funnel_steps`, `funnel_step_media` | `scheduled_messages` | `funnel:start:`, авто‑старт по `tracking_link.funnel_id` и `product.default_funnel_id` |
| `funnel_triggers` | Кодовые слова | funnels | `funnel_triggers` | — | роутинг текста → воронка |
| `quizzes` | Квизы | funnels | `quizzes` | — | `quiz:start:`, `qa:` |
| `forms` | Формы | funnels, leads | `forms` | — | `form:start:`, `form:cancel:`, ввод текста формы |
| `lead_magnets` | Лидмагниты | funnels | `lead_magnets` | — | доставка в `scheduled_messages` (`step.lead_magnet_id`) |

> Сценарий клиента «без воронок и лидмагнитов»: ставим `FEATURE_FUNNELS=false` →
> резолвер каскадно гасит `funnel_triggers`, `quizzes`, `forms`, `lead_magnets`.
> Остаётся: каталог + заявки + платежи/подписки + трекинг + аналитика. Чистый
> «бот для продажи доступа в каналы».

---

## 2. Принцип «выключено ≠ удалено» (обязательно соблюдать)

1. **Схема БД всегда полная.** Флаги — runtime‑only. Миграции воронок/квизов и т.д.
   применяются всегда; таблицы не дропаются при отключении. Это:
   - сохраняет данные клиента при временном отключении;
   - делает повторное включение мгновенным;
   - позволяет разрабатывать фичу (она работает на стенде с включённым флагом),
     даже если у части клиентов выключена.
2. **Флаг гейтит только точки входа**, а не бизнес‑логику:
   - регистрацию роутеров (`include_router`),
   - регистрацию джоб scheduler,
   - диспатч/хуки/клавиатуры бота,
   - пункты меню, страницы **и отдельные секции композитных страниц** в админке (§4.5).
   Сервисы (`FunnelsService`, `QuizService`…) не разветвляются по флагу — они просто
   перестают вызываться, потому что нет точек входа.
3. **Тесты гоняются с полным набором фич** (всё включено) — существующее поведение
   не регрессирует. Дополнительно добавляем тесты «минимального» конфига (см. §7).
4. Кросс‑фичевые хуки (например, отмена активных `funnel_entries` при оплате —
   `subscriptions.py`) при выключенных воронках просто не находят данных и
   безопасно ничего не делают; вызовы оборачиваем `if features.funnels` для чистоты.

---

## 3. Дизайн механизма (backend)

### 3.1. Реестр фич — `backend/app/core/features.py` (новый файл)

```python
from __future__ import annotations
from dataclasses import dataclass, field

@dataclass(frozen=True)
class FeatureDef:
    key: str
    label: str
    depends_on: tuple[str, ...] = ()
    default: bool = True

# Порядок важен только для читабельности; зависимости резолвятся транзитивно.
FEATURE_REGISTRY: dict[str, FeatureDef] = {
    "leads":           FeatureDef("leads", "Заявки"),
    "monetization":    FeatureDef("monetization", "Платежи и подписки"),
    "tracking_links":  FeatureDef("tracking_links", "Трекинг-ссылки"),
    "analytics":       FeatureDef("analytics", "Аналитика"),
    "funnels":         FeatureDef("funnels", "Воронки"),
    "funnel_triggers": FeatureDef("funnel_triggers", "Кодовые слова", ("funnels",)),
    "quizzes":         FeatureDef("quizzes", "Квизы", ("funnels",)),
    "forms":           FeatureDef("forms", "Формы", ("funnels", "leads")),
    "lead_magnets":    FeatureDef("lead_magnets", "Лидмагниты", ("funnels",)),
}

def resolve(raw: dict[str, bool]) -> dict[str, bool]:
    """Применяет дефолты и каскад зависимостей.
    Фича эффективно включена ТОЛЬКО если включена сама И все её зависимости.
    Выключение зависимости каскадно гасит зависимые (итерируем до стабилизации).
    """
    eff = {k: raw.get(k, d.default) for k, d in FEATURE_REGISTRY.items()}
    changed = True
    while changed:
        changed = False
        for key, d in FEATURE_REGISTRY.items():
            if eff[key] and any(not eff[dep] for dep in d.depends_on):
                eff[key] = False
                changed = True
    return eff
```

### 3.2. Settings — `backend/app/core/config.py`

Добавляем чтение per‑feature булевых переменных с префиксом `FEATURE_`.

```python
class Settings(BaseSettings):
    # ... существующие поля ...

    # сырые значения из env: FEATURE_FUNNELS, FEATURE_LEAD_MAGNETS, ...
    # pydantic-settings: вложенная модель или ручной парс из os.environ.
    # Простейший вариант — ручной парс в свойстве:
    @property
    def features(self) -> dict[str, bool]:
        import os
        from app.core.features import FEATURE_REGISTRY, resolve
        raw: dict[str, bool] = {}
        for key in FEATURE_REGISTRY:
            env = os.environ.get(f"FEATURE_{key.upper()}")
            if env is not None:
                raw[key] = env.strip().lower() in {"1", "true", "yes", "on"}
        return resolve(raw)
```

> Кэшировать (`functools.lru_cache` или вычислить один раз при старте в модуле
> `features`), чтобы не парсить env на каждый запрос. Рекоменд.: модуль‑синглтон
> `app/core/features.py::current_features()` с ленивым кэшем.

Формат `.env` (понятный клиенту):
```dotenv
# Полный набор (mediann) — можно вообще не указывать, дефолт = всё включено
# Минимальный (zaza): только продажа доступа
FEATURE_FUNNELS=false
FEATURE_LEAD_MAGNETS=false
FEATURE_QUIZZES=false
FEATURE_FORMS=false
FEATURE_FUNNEL_TRIGGERS=false
# analytics/tracking_links/leads/monetization оставляем включёнными
```

### 3.3. Эндпойнт для фронта — `GET /api/config/features`

Новый роутер `backend/app/api/config.py` (под `current_admin`, чтобы не светить наружу):

```python
@router.get("/config/features")
async def get_features(_: Admin = Depends(current_admin)) -> dict:
    feats = current_features()                      # {key: bool}
    return {
        "features": feats,
        "registry": [
            {"key": k, "label": d.label, "depends_on": list(d.depends_on)}
            for k, d in FEATURE_REGISTRY.items()
        ],
    }
```

### 3.4. Два уровня гейтинга бэкенда

**(а) Уровень роутера — `backend/app/main.py`.** Заменяем линейный список
`include_router` на реестр «фича → роутеры» и цикл:

```python
feats = current_features()

# Ядро — всегда:
for r in (auth_router, admin_router, bots_router, channels_router,
          products_router, users_router, audit_router,
          feature_requests_router, config_router, stats_overview_router):
    api.include_router(r)

FEATURE_ROUTERS = {
    "leads":          [leads_router],
    "monetization":   [payments_router, subscriptions_router],
    "tracking_links": [tracking_links_router],
    "analytics":      [stats_router],   # без /overview — он в ядре, см. ниже
    "funnels":        [funnels_router, funnel_entries_router, funnel_steps_router,
                       funnel_step_media_router],
    "funnel_triggers":[funnel_triggers_router],
    "quizzes":        [quizzes_router],
    "forms":          [forms_router],
    "lead_magnets":   [lead_magnets_router],
}
for key, routers in FEATURE_ROUTERS.items():
    if feats[key]:
        for r in routers:
            api.include_router(r)
```

**(б) Уровень эндпойнта — гард `require_feature` в `backend/app/api/deps.py`.**
Нужен там, где роутер нельзя выключить целиком (часть эндпойнтов — ядро):

```python
def require_feature(key: str):
    async def _check() -> None:
        if not current_features().get(key):
            raise HTTPException(status_code=404, detail="Feature disabled")
    return Depends(_check)
```
Применение: `@router.get(..., dependencies=[require_feature("analytics")])`.

**Важный кейс — `stats` (легко пропустить).** Эндпойнты в `stats.py`: `/overview`,
`/sources`, `/timeline`, `/funnels/{id}/conversion`, `/funnels/summary`, `/health`.
Главная админки (`/`) дёргает именно **`/overview`** — он **обязан работать всегда**,
иначе лендинг падает. Поэтому:
- `/stats/overview` → вынести в **ядро** (`stats_overview_router`, без флага); внутри он
  считает только метрики включённых фич (карточки воронок/лидов — лишь если фича есть);
- остальные (`/sources`, `/timeline`, `/funnels/*`, `/health`) → роутер `stats` под флагом `analytics`.

Выключенная фича → её эндпойнты дают `404` (роутер не зарегистрирован, либо `require_feature`).
Фронт их и не дёргает (меню/страницы скрыты, §4); `require_feature` — defense‑in‑depth
на случай прямого обращения к API.

### 3.5. Гейтинг scheduler — `backend/app/workers/scheduler.py`

В `start()` оборачиваем `add_job`:

```python
feats = current_features()
if feats["monetization"]:
    sch.add_job(_hourly_expire_due, IntervalTrigger(hours=1), id="expire_due", ...)
if feats["funnels"]:
    sch.add_job(_process_scheduled_messages, IntervalTrigger(seconds=30), id="scheduled_messages", ...)
```

### 3.6. Гейтинг бота — `backend/app/bot/handlers.py`

Бот монолитный, поэтому два шага:

**Шаг A (быстрый, обязательный) — защитить хуки авто‑старта и колбэки:**
- В `start_with_arg` (≈`handlers.py:250`) запуск воронки по `tracking_link.funnel_id`
  оборачиваем `if features["funnels"]: ...`.
- В `cb_lead` (≈`handlers.py:405`) запуск по `product.default_funnel_id` — то же.
- В `on_text_message` (≈`handlers.py:565`) роутинг кодовых слов — `if features["funnel_triggers"]: ...`,
  ветку активной формы — `if features["forms"]: ...`.
- Колбэки `cb_quiz_start`/`cb_quiz_answer` — `if features["quizzes"]`; `cb_form_*` — `if features["forms"]`;
  `cb_funnel_start` — `if features["funnels"]`. При выключенной фиче — мягко отвечаем
  `cb.answer("Недоступно")` или показываем каталог, без падений.
- Доставку лидмагнита в `scheduled_messages.py:432` — `if features["lead_magnets"] and step.lead_magnet_id:`.
- **Клавиатуры тоже гейтим, не только хендлеры.** Кнопку «Оставить заявку» в
  `_product_kb` (`handlers.py:145`) рендерим только при `features["leads"]` (иначе
  карточка продукта ведёт в недоступный колбэк). Разбор slug трекинг‑ссылки в
  `start_with_arg` (`handlers.py:~210`) — при `features["tracking_links"]`, иначе
  `/start <slug>` просто показывает каталог.

**Шаг B (чистый, желательный) — разнести хендлеры по роутерам бота:**
Сейчас всё в одном `router = Router(name="public")` (`handlers.py:40`), который
подключается в `build_dispatcher()` (`handlers.py:806‑808`) одним `dp.include_router(router)`.
Разбить `handlers.py` на `app/bot/handlers/{core,funnels,quizzes,forms}.py`, каждый со своим
`Router`. В `build_dispatcher()` подключать роутеры по флагам:
```python
dp.include_router(core_router)
if feats["funnels"]: dp.include_router(funnels_router)
if feats["quizzes"]: dp.include_router(quizzes_router)
if feats["forms"]:   dp.include_router(forms_router)
```
Это убирает `if`‑ы из тела хендлеров. Делать инкрементально (см. Фазу 5), не блокирует Шаг A.

> Помни про клонирование роутера на каждого бота (`build_dispatcher`) — флаги
> вычисляются один раз глобально, поэтому набор роутеров одинаков для всех ботов
> инстанса (это ок: фичи — свойство деплоя, не отдельного бота).

---

## 4. Дизайн механизма (frontend)

### 4.1. Получение флагов в runtime (НЕ build‑time)

Важно: флаги тянем с API в рантайме, **не** через `NEXT_PUBLIC_*`, иначе пришлось бы
собирать отдельный образ под каждого клиента. Один образ admin → все клиенты.

`admin/lib/features.ts` (новый): хук/контекст поверх SWR.
```ts
export type Features = Record<string, boolean>;
export function useFeatures() {
  const { data } = useSWR<{features: Features}>('/config/features', fetcher,
    { revalidateOnFocus: false, dedupingInterval: 60_000 });
  return data?.features ?? {};
}
```
Положить в React‑контекст на уровне `(dash)/layout.tsx`, чтобы не дёргать на каждой странице.

### 4.2. Гейтинг меню — `admin/app/(dash)/layout.tsx`

Расширяем типы `NavItem`/`NavGroup` ключом фичи и фильтруем (рядом с существующим `adminOnly`):
```ts
type NavItem  = { href: string; label: string; icon: ReactNode; feature?: string; badge?: ... };
type NavGroup = { key: string; label?: string; adminOnly?: boolean; feature?: string; items: NavItem[] };

// в NAV_GROUPS проставить feature:
// группа 'funnels' → каждому пункту: { ..., feature: 'funnels' | 'lead_magnets' | 'quizzes' | 'forms' | 'funnel_triggers' }
// 'analytics' → feature: 'analytics'; 'sales' → 'leads'/'monetization'

const visibleGroups = NAV_GROUPS
  .filter(g => (!g.adminOnly || isAdmin) && (!g.feature || feats[g.feature]))
  .map(g => ({ ...g, items: g.items.filter(i => !i.feature || feats[i.feature]) }))
  .filter(g => g.items.length > 0);
```

### 4.3. Гейтинг страниц (defense‑in‑depth для прямых URL)

Хук `useFeatureGuard('funnels')`: если выключено — `router.replace('/')`. Повесить на
страницы фич: `funnels/*`, `lead-magnets`, `quizzes/*`, `forms/*`, `funnel-triggers`,
`payments`, `subscriptions`, `sources`, `analytics`.

### 4.4. Гейтинг кросс‑фичевого UI (самое тонкое — из анализа фронта)

В студии воронки (`admin/app/(dash)/funnels/[id]/edit/page.tsx`) встроены пикеры
квиза/формы/лидмагнита (`QuickLeadMagnetUpload`, выбор `quiz_id`/`form_id`,
тип шага `kind`). Их рендер обернуть в `feats`:
```ts
{feats.quizzes && <StepKindOption value="quiz" .../>}
{feats.forms   && <StepKindOption value="form" .../>}
{feats.lead_magnets && <QuickLeadMagnetUpload .../>}
```
Аналогично — фильтры по воронкам/продуктам на `sources` (`feats.funnels`). Главная (`/`)
ходит в ядровый `/stats/overview` и **обязана корректно рендериться при любом подмножестве
фич** — показываем только карточки включённых (воронки/лиды/подписки скрываем по `feats`).

### 4.5. Композитные страницы — гейтинг на уровне СЕКЦИЙ (ответ на «а если на одной странице разные модули?»)

Главный нюанс модульности: одна страница часто собирает секции из **разных** модулей.
Гейтить такую страницу целиком нельзя — она ядровая и должна оставаться. Поэтому
правило: **сайдбар гейтим на уровне групп/пунктов (§4.2), а композитную страницу —
на уровне каждой секции**, тем же `feats` из контекста.

**Инвентарь композитных мест (куда обязательно проставить секционный гейтинг):**

| Страница | Модуль самой страницы | Секции и их модули |
|---|---|---|
| `/` (дашборд) | core (всегда) | карточки: Заявки → `leads`; Платежи/Подписки → `monetization`; Воронки → `funnels` |
| `/users/[id]` | core (`users`) | «Подписки», «Платежи» → `monetization`; «Заявки» → `leads`; «История ответов» (`/users/{id}/submissions`) → `quizzes`/`forms` |
| `/products/[id]` | core | трекинг‑ссылки → `tracking_links`; выбор default‑воронки → `funnels` |
| `/leads/[id]` | `leads` | атрибуция (utm/ссылка) → `tracking_links`; форм‑шаг → `funnels`/`forms` |
| `/sources` | `analytics` | фильтр по воронкам → `funnels` |
| `/funnels/[id]/edit` (студия) | `funnels` | типы шага quiz/form/лидмагнит → `quizzes`/`forms`/`lead_magnets` (см. §4.4) |

**Фронт — секцию оборачиваем флагом из контекста:**
```tsx
{feats.monetization && <PaymentsSection .../>}
{feats.monetization && <SubscriptionsSection .../>}
{feats.leads && <LeadsSection .../>}
{(feats.quizzes || feats.forms) && <SubmissionsTimeline userId={id} />}
```
Секции, которые тянут данные **отдельным запросом** (`/users/{id}/submissions`,
`/tracking-links?...`), при выключенном модуле просто **не запрашиваем** — условие по
`feats` ставим ДО `useSWR`, чтобы не словить лишний 404 (роутер выключен → `require_feature`).

**Контракт композитных эндпойнтов (бэк):** `GET /users/{id}` отдаёт `leads`/`payments`/
`subscriptions` одним payload‑ом (`users.py:98‑123`) — это **единственное оправданное
место, где ядровый эндпойнт смотрит на флаги**:
- *рекомендуется* — не считать секции выключенных модулей (меньше запросов, нет «мёртвых» данных в ответе);
- *обязательно* — фронт читает поля защищённо (`data.payments ?? []`) и **не падает**, если
  ключ отсутствует/пуст. Тогда поведение одинаково и при omit на бэке, и при пустом массиве.

> Бот‑аналог композита — карточка продукта: ядровый текст + кнопка `leads` + авто‑старт
> `funnels`. Разобран в §3.6 (гейтим и клавиатуру, не только хендлер).

---

## 5. Рефакторинг структуры (опционально, инкрементально)

Сейчас раскладка слоевая (`api/`, `models/`, `services/` плоско). Полный переход на
вертикальные слайсы (`app/features/<name>/{api,models,services,bot}.py`) — большой и
рискованный рефактор импортов. **Рекомендация: не делать big‑bang.**

- **Фаза A (этот документ, Фазы 1‑6 ниже):** даём флаги без переноса файлов. Быстро, безопасно.
- **Фаза B (потом, по одной фиче):** заводим `app/features/funnels/` и постепенно
  переносим туда `api/funnels.py`, `models/funnel*.py`, `services/funnels.py`,
  `services/step_flow.py`, воркер `scheduled_messages.py`, бот‑роутер воронок.
  Каждый перенос — механический (правка импортов) + зелёные тесты. Начинать с самой
  когезивной фичи — `funnels`, затем `quizzes`/`forms`/`lead_magnets`.

Перенос НЕ обязателен для получения управляемой модульности — флаги работают и на
текущей раскладке. Делать его только когда захочется чище разделить ответственность.

---

## 6. Управление по клиентам

- **Фаза 1 (MVP, этот план):** источник истины — `.env` на сервере клиента. Меняешь
  переменные `FEATURE_*`, перезапускаешь `docker compose up -d`. Разные серверы
  (mediann/zaza) — разные `.env`.
- **Фаза 2 (опционально, на будущее):** таблица `feature_flags` в БД + страница
  «Настройки» в админке (только роль `admin`), переопределяющая env. Резолвер тогда:
  `effective = resolve(env_defaults ⊕ db_overrides)`. Это даёт включение/выключение
  без редеплоя. Эндпойнт `/config/features` уже отдаёт актуальные — фронту менять ничего.

---

## 7. Тестирование

1. `backend/tests/unit/test_features.py`:
   - `resolve({"funnels": False})` гасит `quizzes/forms/lead_magnets/funnel_triggers`;
   - `resolve({"quizzes": True, "funnels": False})` → `quizzes=False` (нельзя без хаба);
   - дефолт без env → всё `True`.
2. `backend/tests/integration/test_feature_gating.py` (через `TestClient`, env‑override):
   - с `FEATURE_FUNNELS=false`: `GET /api/funnels` → 404; `GET /api/products` → 200;
   - scheduler не регистрирует джобу `scheduled_messages` (проверка через флаг/мок `add_job`);
   - `GET /api/config/features` отдаёт ожидаемый эффективный набор.
3. Бот‑смоук с минимальным конфигом: `/start` показывает каталог, не падает без воронок.
4. **CI/тестовый конфиг — всё включено** (никаких `FEATURE_*` в тестовом env), чтобы
   существующие тесты не регрессировали. Минимальный конфиг проверяется отдельными
   параметризованными тестами из п.2‑3.
5. **Сброс кэша флагов в тестах (важно).** `current_features()` и `get_settings()`
   кэшируются — тесты, меняющие `FEATURE_*` через `monkeypatch.setenv`, обязаны чистить
   кэш (`current_features.cache_clear()` / пересоздавать settings). Лучше — фикстура в
   `backend/tests/conftest.py` (рядом с существующими `conftest.py`/`factories.py`).
6. **Не забыть `tests/property/` (hypothesis) и `e2e/` (Playwright).** E2E‑прогон
   фиксируем на полном наборе фич; для минимального конфига — отдельный e2e‑сценарий
   (или хотя бы smoke), чтобы проверить, что скрытие меню/страниц не ломает навигацию.

---

## 8. ПОШАГОВЫЙ ПЛАН ВНЕДРЕНИЯ (чек‑лист)

Каждая фаза — отдельный PR, по умолчанию поведение не меняется (всё включено).

### Фаза 1 — Реестр и резолвер (бэкенд, без гейтинга)
- [ ] Создать `backend/app/core/features.py`: `FeatureDef`, `FEATURE_REGISTRY`, `resolve()`, ленивый `current_features()` с кэшем.
- [ ] В `config.py` добавить чтение `FEATURE_*` (или вынести целиком в `features.py`, читая `os.environ`).
- [ ] Юнит‑тест `test_features.py` (каскад зависимостей).
- **Acceptance:** тесты зелёные; импорт `current_features()` возвращает всё `True` без env.

### Фаза 2 — Эндпойнт конфигурации
- [ ] `backend/app/api/config.py`: `GET /config/features` под `current_admin`.
- [ ] Подключить `config_router` в `main.py` (в ядре, всегда).
- **Acceptance:** `curl https://backend.<host>/config/features` (с кукой) отдаёт `{features, registry}`.

### Фаза 3 — Гейтинг бэкенда
- [ ] `main.py`: заменить список `include_router` на `FEATURE_ROUTERS` + цикл по `feats` (§3.4а).
- [ ] Добавить гард `require_feature` в `deps.py` (§3.4б).
- [ ] Вынести `/stats/overview` в ядровый роутер; остальные stats‑эндпойнты — под флагом `analytics` (§3.4, кейс stats).
- [ ] `scheduler.py`: обернуть обе джобы во флаги (§3.5).
- [ ] Интеграционные тесты гейтинга (§7.2).
- **Acceptance:** с `FEATURE_FUNNELS=false` — `/api/funnels`→404, `/api/products`→200, джоба `scheduled_messages` не стартует.

### Фаза 4 — Гейтинг бота (Шаг A — хуки)
- [ ] Защитить авто‑старт воронок и колбэки квиз/форм/лидмагнитов во флаги (§3.6 Шаг A).
- [ ] Бот‑смоук с минимальным конфигом (§7.3).
- **Acceptance:** при выключенных воронках `/start` и каталог работают; колбэки выключенных фич отвечают мягко, без ошибок в логах.

### Фаза 5 — Фронтенд
- [ ] `admin/lib/features.ts` + контекст в `(dash)/layout.tsx`.
- [ ] Проставить `feature` в `NAV_GROUPS`, отфильтровать меню (§4.2).
- [ ] `useFeatureGuard` на страницах фич (§4.3).
- [ ] Скрыть кросс‑фичевый UI в студии воронки / sources / дашборде (§4.4).
- [ ] **Секционный гейтинг композитных страниц** (`/`, `users/[id]`, `products/[id]`, `leads/[id]`, `sources`, студия) + защищённое чтение полей (§4.5).
- **Acceptance:** при выключенных воронках в меню нет групп «Воронки»; прямой переход на `/funnels` редиректит на `/`; студия не предлагает шаги quiz/form/лидмагнит.

### Фаза 6 — Документация и деплой клиентов
- [ ] Дописать `.env.example` секцией `FEATURE_*` с пояснениями и примерами (mediann=всё, zaza=минимум).
- [ ] Обновить `README.md` и этот файл при отклонениях.
- [ ] Применить `.env` на zaza (минимальный набор), на mediann — оставить дефолт.
- **Acceptance:** zaza показывает только каталог/заявки/платежи/аналитику; mediann — без изменений.

### Фаза B (опционально, позже) — вертикальные слайсы
- [ ] Перенести `funnels` в `app/features/funnels/`, затем quizzes/forms/lead_magnets — по одной фиче, с зелёными тестами (§5).

### Фаза 2‑DB (опционально, позже) — рантайм‑тоглы в админке
- [ ] Таблица `feature_flags` + страница «Настройки» (роль admin) + слияние env⊕db в резолвере (§6).

---

## 9. Риски и важные нюансы

1. **Не дропать таблицы выключенных фич.** Схема всегда полная (миграции применяются всегда). Иначе потеря данных и ломка повторного включения.
2. **Тесты — с полным набором фич.** Минимальный конфиг — только в отдельных таргетных тестах. Иначе спрячем регрессии.
3. **Кросс‑фичевые FK безопасны при выключении**: `product.default_funnel_id`, `tracking_link.funnel_id` остаются в схеме; код, что их читает, оборачиваем `if feats["funnels"]`, иначе просто игнорируем значение.
4. **Бот: флаги — свойство инстанса/деплоя, не отдельного бота.** Все боты одного сервера используют один набор фич. Если в будущем нужно «на бот» — это Фаза 2‑DB с привязкой к `bot_id` (большая работа, пока вне рамок).
5. **Флаги в рантайме фронта, не в сборке.** Не вносить `FEATURE_*` в `NEXT_PUBLIC_*` — иначе теряем «один образ на всех».
6. **`scheduled_messages` уже отправленных сообщений.** При выключении `funnels` воркер не стартует — запланированные, но не отправленные шаги «зависнут» (останутся в БД). При повторном включении догонят (или нужно вручную отменить). Описать поведение клиенту.
7. **Эндпойнт `/config/features` под аутентификацией** — не раскрывать состав фич публично.
8. **Резолвер — единственное место каскада.** И бэкенд (роутеры/scheduler/бот), и фронт (меню/страницы) читают уже отрезолвленный набор из одного источника (`/config/features`), чтобы не было рассинхрона.
9. **Главная дашборда не должна зависеть от выключаемой аналитики.** `/stats/overview` держим в ядре; глубокую аналитику гейтим через `require_feature("analytics")`. Иначе отключение аналитики ломает лендинг `/`.
10. **Кнопки/клавиатуры, ведущие в выключенную фичу, скрывать вместе с хендлерами.** Напр. при выключенном `leads` карточка продукта в боте остаётся без CTA «Оставить заявку» — для чисто информационного каталога это ок, но поведение надо подтвердить с клиентом.
11. **Сид/демо‑данные выключенных фич безвредны.** Схема полная, поэтому сидер (`seeddata/`) может создавать воронки/квизы даже при выключенных фичах — они просто не доставляются (нет точек входа). Отдельно чистить не нужно.
12. **Композитные страницы гейтим по секциям, а не целиком.** Ядровые страницы (`/`, `users/[id]`, `products/[id]`) показывают данные нескольких модулей одновременно — каждую секцию скрываем своим флагом, фронт читает поля защищённо, чтобы не падать при отсутствии ключа. Это прямой ответ на вопрос «что если на одной странице модули из разных фич» (§4.5).

---

## 10. Примеры `.env`

**mediann (полный):** ничего не добавляем — дефолт всё включено.

**zaza (минимум — продажа доступа):**
```dotenv
FEATURE_FUNNELS=false
FEATURE_LEAD_MAGNETS=false
FEATURE_QUIZZES=false
FEATURE_FORMS=false
FEATURE_FUNNEL_TRIGGERS=false
# leads / monetization / tracking_links / analytics — включены по умолчанию
```
Эффективный набор после `resolve()`: `leads, monetization, tracking_links, analytics`.
Воронки и всё, что от них зависит, — выключены каскадно.
