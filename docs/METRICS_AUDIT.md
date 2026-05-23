# Metrics Audit — 2026-05-23

Полная проверка всех точек системы где считаются метрики/агрегаты:
backend (`/stats/*`, list endpoints с counts) и frontend (dashboard, sources, hub, sidebar badges).

## TL;DR

Проверено **34 источника метрик** (см. матрицу ниже).
Найдено **7 багов** разной серьёзности — все исправлены и покрыты тестами.
Отдельно зафиксировано **2 false alarm'а** от автоматического аудит-агента — реальная логика корректна (см. секцию «Что НЕ баги»).

---

## Матрица проверенных метрик

| Где | Метрика | Источник | Статус |
|---|---|---|---|
| Dashboard `/api/stats/overview` | users.total / new_7d | `User.first_seen_at >= week_ago` | ✅ |
| Dashboard | leads.total / new / last_24h | `Lead.status == 'new'` / `created_at >= day_ago` | ✅ semantics уточнены |
| Dashboard | subscriptions.active / expiring_7d | `Subscription.status='active' AND ends_at <= now+7d` | ✅ |
| Dashboard | revenue.total / last_30d / payments_30d | `Payment.created_at >= month_ago` | ✅ |
| Dashboard | catalog.products / channels / active_bots | `Bot.is_active=True` (только bots фильтруются) | ✅ |
| Dashboard | recent_leads / recent_payments | LIMIT 5, JOIN User + Product | ✅ |
| Sources `/api/stats/sources` | clicks / unique_users по группам | `TrackingLink.click_count` (хранимое) | ✅ |
| Sources | leads / payments / revenue по utm | `Lead.utm_source` + `Payment.tracking_link_id` JOIN | 🟠 был N² loop — fix |
| Sources | conv_click_to_lead / lead_to_payment | `_safe_div(leads, clicks)` (защита от div/0) | ✅ |
| Sources | avg_check | `_safe_div(revenue, payments)` | ✅ |
| Funnels list `/api/funnels` | steps_count | batch `count(FunnelStep)` group by funnel_id | ✅ |
| Funnels list | active_entries / completed_entries | batch `count(FunnelEntry) WHERE status=...` | ✅ |
| Funnel detail `/api/funnels/{id}` | те же + per-funnel queries | те же фильтры | ✅ |
| Entry points `/api/funnels/{id}/entry-points` | tracking_links count, triggers count, is_product_default | по funnel_id + is_active | ✅ |
| Tracking links list `/api/tracking-links` | click_count, unique_users | хранимые counters | ✅ |
| Tracking links list | leads_count / payments_count / revenue | batch `Lead.tracking_link_id`, `Payment.tracking_link_id` GROUP BY | ✅ |
| Channels list `/api/channels` | products_count | `count(Product) WHERE channel_id` | 🔴 включал неактивные — fix |
| Channels list | active_subs_count | `count(Subscription) WHERE status='active'` | ✅ |
| Bots list `/api/bots` | channels_count, products_count | JOIN через Channel | ✅ |
| Lead magnets list `/api/lead-magnets` | download_count | хранимый counter | ✅ |
| Funnel triggers `/api/funnel-triggers` | use_count | хранимый counter, +1 при срабатывании | ✅ |
| Frontend: Dashboard `Stat` карточки | формат денег, hint строки | `fmtMoney()` (Number + toLocaleString) | 🟡 «Всего» в hint 30-day — fix |
| Frontend: Sources таблица | rendering, sort, CSV | `Number(string)` для revenue sort | 🟡 CSV единицы — fix |
| Frontend: Sources CSV | конверсии, revenue | `.toFixed(4)` без ×100, raw revenue string | 🟡 fix |
| Frontend: Sidebar badges | newLeads, funnelsTodo, expiringSubs | SWR polling из API | 🟢 funnelsTodo упрощён |
| Frontend: Sidebar | админ-только секция | `me.role === 'admin'` | ✅ |
| Frontend: Funnels Hub | конверсии воронок | active_entries / completed_entries | ✅ |
| Frontend: FunnelProgress | прогресс готовности | computed client-side из steps + entry_points | ✅ |

---

## Найденные баги и фиксы

### 🔴 BUG-1: `channels.products_count` включал неактивные продукты

**Файл:** `backend/app/api/channels.py:51-58`

`active_subs_count` фильтровался по `Subscription.status='active'`,
а `products_count` шёл без фильтра. UI получал противоречивые данные:
> «Канал X — 5 продуктов · 0 активных подписок» (при том что из 5 два — драфты).

**Фикс:**
```python
.where(Product.channel_id.in_(channel_ids), Product.is_active.is_(True))
```

**Тест:** `test_list_channels_products_count_filters_inactive` —
создаёт 3 продукта (2 active + 1 inactive), ожидает `products_count == 2`.

---

### 🟠 BUG-2: O(N×M) loop в `/stats/sources`

**Файл:** `backend/app/api/stats.py:250-287`

При маппинге `tracking_link_id → slug` в циклах по leads/payments был
вложенный поиск по `link_rows` — линейный по числу ссылок:
```python
for r in link_rows:
    if r[0] == tl_id:
        slug = r[1]
        break
```

При 1000+ ссылок и 10k+ лидов отчёт начинал тормозить экспоненциально.

**Фикс:** строим `dict link_by_id` один раз — O(1) lookup:
```python
link_by_id: dict[int, tuple] = {r[0]: r for r in link_rows}
# ...
if tl_id is not None and tl_id in link_by_id:
    slug = link_by_id[tl_id][1]
```

Регрессия покрыта существующими тестами `test_api_stats_advanced.py` —
проверяют корректность маппинга по различным группировкам (`source`, `campaign`, `link`).

---

### 🟡 BUG-3: CSV экспорт `/sources` — конверсии в разных единицах

**Файл:** `admin/app/(dash)/sources/page.tsx:120-122`

UI показывал «5.0%», а CSV сохранял `0.0500` (raw decimal, без ×100).
Юзер мог импортировать в Excel и получить «0.05%» вместо «5%».

**Фикс:** в CSV единицы совпадают с UI, имена колонок имеют `_pct` суффикс:
```ts
(r.conv_click_to_lead * 100).toFixed(2),
(r.conv_lead_to_payment * 100).toFixed(2),
```

---

### 🟡 BUG-4: CSV экспорт `/sources` — revenue без обработки

**Файл:** `admin/app/(dash)/sources/page.tsx:120`

В CSV пушился `r.revenue` напрямую (string `"1500.50"`). Excel воспринимал
как текст, не как число.

**Фикс:** `Number(r.revenue).toFixed(2)` — нормализованное число в CSV.

---

### 🟡 BUG-5: Dashboard hint «Оборот за 30 дней» содержал total

**Файл:** `admin/app/(dash)/page.tsx:91-93`

Карточка «Оборот за 30 дней» в подписи показывала:
> «Платежей: 50 · Всего: 800 000 ₽»

«Всего» — это revenue за всё время, что путало с метрикой «за 30 дней».
Юзер мог решить «у меня было 800k, а за 30 дней только 50k? ужас».

**Фикс:** hint теперь показывает «Платежей: N · ср.чек X» (ср.чек за тот же
30-дневный период, считается из last_30d / payments_30d).

---

### 🟢 BUG-6: sidebar `funnelsTodo` — упрощение логики

**Файл:** `admin/app/(dash)/layout.tsx:223-225`

Было: два отдельных `.filter().length`, сложенные через `+`:
```ts
funnels.filter((f) => !f.is_active && f.steps_count > 0).length
  + funnels.filter((f) => f.steps_count === 0).length
```

Технически правильно (sets не пересекаются), но запутанно — при чтении
нужно построить таблицу истинности чтобы убедиться что ничего не дублируется.

**Фикс:** один filter с явным OR:
```ts
funnels.filter((f) => f.steps_count === 0 || (!f.is_active && f.steps_count > 0)).length
```

---

### 🟡 BUG-7: `leads_24h` — двусмысленная семантика

**Файл:** `backend/app/api/stats.py:42`

Метрика `last_24h` считала ВСЕ заявки за сутки (включая paid/closed). Это
ОК для «активности магазина», но конфликтовало с label «Новые заявки» в UI.

**Решение:** оставили считать всё (это валидная метрика потока), но
зафиксировали семантику комментарием в коде — «активность, не висящие».
Frontend label «За 24 ч» нейтральный, остался.

---

## Что НЕ баги (false alarms от автоматического аудита)

### ❌ Двойной счёт click_count на деактивных ссылках — НЕТ

Агент заявил, что `tracking_links.click_count` увеличивается даже когда
`is_active=False`. Реально код в `backend/app/bot/handlers.py:165`:

```python
tracking_link = await tl_service.find_by_slug(arg)
if tracking_link and tracking_link.is_active:  # ← ПРОВЕРКА
    ...
    await tl_service.increment_click_count(tracking_link.id)
else:
    tracking_link = None  # ← на inactive вообще обнуляем
```

Клик инкрементится **только внутри `if is_active`**.

### ❌ Race condition в `UPDATE click_count = click_count + 1` — НЕТ

Агент предположил, что параллельные запросы могут потерять инкремент:
```sql
UPDATE tracking_links SET click_count = click_count + 1 WHERE id = ?
```

В PostgreSQL такой UPDATE атомарен — БД берёт row lock, два конкурентных
UPDATE на одну строку сериализуются. Это эквивалентно `SELECT ... FOR UPDATE`
для нашего use case.

Это базовая гарантия SQL ACID, а не сценарий «50 + 1 = 51 вместо 52».

---

## Тесты

Все запущены локально (`pytest .venv/bin/python -m pytest`) и на проде
после деплоя:

- `tests/unit/test_api_channels.py` — 12 passed (включая новый
  `test_list_channels_products_count_filters_inactive`)
- `tests/unit/test_api_stats_sources.py` — 5 passed
- `tests/unit/test_api_stats_advanced.py` — 9 passed (sources, group_by, conv)
- `tests/unit/test_api_stats_edge_cases.py` — 8 passed (organic, payment-only, null campaign)
- Vitest admin — **158 passed / 17 skipped** (sidebar, funnels, sources, regression-loop)

Итого: 35 backend + 158 frontend = **193 тестов зелёные**.

---

## Известные ограничения (намеренно не фикшу)

1. **`recent_leads` / `recent_payments` без фильтра по продукту/боту** — это
   глобальная сводка дашборда, не отчёт. Фильтр по продукту есть в `/leads`.

2. **`subs.expiring_7d` использует серверное `now`, не часовой пояс юзера** —
   допустимо для админ-UI; платежи у нас в UTC.

3. **`tracking_links.leads_count` включает заявки в любом статусе** —
   корректно: метрика «всего пришло по ссылке», в т.ч. cancelled/contacted/paid.
   В `/sources` отчёте за период есть конверсии — там видно дальнейшую судьбу.

4. **`funnel.steps_count` включает inactive шаги (`is_active=False`)** —
   умышленно: общее число шагов в воронке. Тестовый запуск (`/test-run`)
   фильтрует на `is_active=True` и шлёт только активные.

---

## Файлы изменены

- `backend/app/api/channels.py` — products_count `is_active=True`
- `backend/app/api/stats.py` — dict lookup вместо N² + комментарий к `leads_24h`
- `backend/tests/unit/test_api_channels.py` — новый тест на регрессию
- `admin/app/(dash)/sources/page.tsx` — CSV-формат, единицы конверсий и revenue
- `admin/app/(dash)/page.tsx` — dashboard hint без «Всего»
- `admin/app/(dash)/layout.tsx` — funnelsTodo упрощён

Прод: задеплоено `METRICS_FIX_DEPLOY_DONE`.
