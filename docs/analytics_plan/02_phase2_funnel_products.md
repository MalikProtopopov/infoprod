# Phase 2 — Воронка и продуктовая аналитика

**Срок**: 2–3 рабочих дня. Запускается **после** Phase 1 — нужны накопленные `tracking_link_id`, UTM и timestamps на leads/payments.

**Результат**: видна полная воронка от клика до оплаты, понятно какие продукты дают лучшую конверсию и средний чек, на главном дашборде — окна 30д/90д + sparkline + топ‑источники.

---

## Шаг 2.1 — `GET /api/stats/funnel`

Файл: добавить в `backend/app/api/stats.py`.

### Параметры
- `from`, `to` — ISO datetime
- `tracking_link_id?` — конкретная ссылка
- `product_id?`
- `source?` — фильтр по `utm_source`
- `bot_id?`

### Шаги воронки

| Шаг | Откуда | Что считаем |
|-----|--------|-------------|
| 1. Клики | `SUM(tracking_links.click_count)` | по выбранным ссылкам в периоде |
| 2. /start выполнено | `COUNT(DISTINCT users.id)` с `first_seen_at` в периоде | если есть фильтр по источнику — `first_utm_source = ...` |
| 3. Заявка | `COUNT(leads.id)` | с фильтрами |
| 4. Оплата | `COUNT(payments.id)` | с фильтрами |

⚠️ **Тонкость**: для шага 1 `click_count` — глобальный счётчик ссылки, без разбивки по дням. Если нужно «клики за период» точно — потребуется events (Phase 4). На Phase 2 даём приближение: текущий `click_count` ссылок, активных в периоде.

Альтернатива: считать клики как `COUNT(DISTINCT users)` где `first_tracking_link_id IS NOT NULL` и `first_seen_at BETWEEN from AND to`. Тогда шаг 1 фактически = шаг 2, что бессмысленно.

**Решение**: оставить грубый `SUM(click_count)` ссылок, попавших в фильтр (без точной фильтрации по дате клика). В UI добавить tooltip «Точный учёт кликов по дате появится в Phase 4».

### Ответ

```json
{
  "steps": [
    { "name": "Клики",   "count": 1240, "drop_pct": null },
    { "name": "/start",  "count": 980,  "drop_pct": 0.21 },
    { "name": "Заявка", "count": 145,  "drop_pct": 0.85 },
    { "name": "Оплата", "count": 38,   "drop_pct": 0.74 }
  ]
}
```

`drop_pct` = `(prev.count - current.count) / prev.count`.

---

## Шаг 2.2 — `GET /api/stats/products`

Файл: добавить в `backend/app/api/stats.py`.

### Параметры
- `from`, `to`
- `is_active?` (default = true)

### Ответ

```json
{
  "rows": [
    {
      "product_id": 3,
      "code": "yoga12",
      "name": "Йога курс",
      "leads_count": 145,
      "payments_count": 38,
      "conv_lead_to_payment": 0.262,
      "avg_check": "12000.00",
      "revenue": "456000.00",
      "active_subs": 24,
      "by_period": {
        "3":  {"payments": 12, "revenue": "120000"},
        "6":  {"payments": 18, "revenue": "216000"},
        "12": {"payments": 8,  "revenue": "120000"}
      }
    }
  ]
}
```

### SQL-логика

CTE-стиль:

```sql
WITH leads_agg AS (
  SELECT product_id, COUNT(*) AS leads_count
  FROM leads
  WHERE created_at BETWEEN $1 AND $2
  GROUP BY product_id
),
payments_agg AS (
  SELECT product_id, COUNT(*) AS payments_count, SUM(amount) AS revenue,
         AVG(amount) AS avg_check
  FROM payments
  WHERE created_at BETWEEN $1 AND $2
  GROUP BY product_id
),
period_split AS (
  SELECT product_id, period_months,
         COUNT(*) AS payments, SUM(amount) AS revenue
  FROM payments
  WHERE created_at BETWEEN $1 AND $2
  GROUP BY product_id, period_months
),
active_subs AS (
  SELECT product_id, COUNT(*) AS active_subs
  FROM subscriptions
  WHERE status = 'active'
  GROUP BY product_id
)
SELECT p.id, p.code, p.name,
       COALESCE(l.leads_count, 0)    AS leads_count,
       COALESCE(pa.payments_count, 0) AS payments_count,
       COALESCE(pa.revenue, 0)       AS revenue,
       COALESCE(pa.avg_check, 0)     AS avg_check,
       COALESCE(as_.active_subs, 0)  AS active_subs
FROM products p
LEFT JOIN leads_agg     l   ON l.product_id  = p.id
LEFT JOIN payments_agg  pa  ON pa.product_id = p.id
LEFT JOIN active_subs   as_ ON as_.product_id = p.id
WHERE p.is_active = true
ORDER BY revenue DESC NULLS LAST;
```

`by_period` собирается отдельным запросом и мерджится в Python (или PostgreSQL `jsonb_object_agg`).

---

## Шаг 2.3 — Расширение `GET /api/stats/overview`

Сейчас возвращает базовые цифры — `users / leads / subscriptions / revenue / catalog / recent_*`.

Добавляем:

```json
{
  "users":         {"total": 3, "new_7d": 1, "new_30d": 3, "new_90d": 3},
  "leads":         {"total": 2, "new": 2, "last_24h": 0, "last_30d": 2, "last_90d": 2},
  "subscriptions": {"active": 1, "expiring_7d": 0, "expiring_14d": 0, "expiring_30d": 0},
  "revenue":       {"total": "120000.00", "last_30d": "120000.00", "last_90d": "120000.00",
                    "payments_30d": 1, "payments_90d": 1},
  "catalog":       {"products": 2, "channels": 2, "active_bots": 1},
  "top_sources_30d": [
    {"source": "instagram", "revenue": "60000", "payments": 5}
  ],
  "sparklines": {
    "users":    [/* 30 чисел: новые юзеры по дням */],
    "leads":    [/* 30 */],
    "payments": [/* 30 */],
    "revenue":  [/* 30 */]
  }
}
```

### Реализация sparklines

```sql
SELECT date_trunc('day', first_seen_at)::date AS day, COUNT(*)
FROM users
WHERE first_seen_at >= now() - interval '30 days'
GROUP BY 1
ORDER BY 1;
```

Затем в Python заполнить пропущенные дни нулями (массив фиксированной длины = 30).

### Топ‑3 источника

```sql
SELECT utm_source, SUM(amount) AS revenue, COUNT(*) AS payments
FROM payments
JOIN leads ON leads.id = (
  SELECT id FROM leads l
  WHERE l.user_id = payments.user_id AND l.product_id = payments.product_id
  ORDER BY l.created_at DESC LIMIT 1
)
WHERE payments.created_at >= now() - interval '30 days'
  AND leads.utm_source IS NOT NULL
GROUP BY utm_source
ORDER BY revenue DESC
LIMIT 3;
```

⚠️ Лучше — после Phase 4 — `payments.tracking_link_id` будет проставляться напрямую при создании платежа, без JOIN-а на lead. На Phase 2 — используем lead.utm_source.

---

## Шаг 2.4 — Frontend: страница `/funnel`

Новый пункт меню «Воронка».

### Структура

- Фильтры сверху: период (preset + custom), продукт (multi-select), источник (combobox по существующим `utm_source` из `tracking_links`), кампания (combobox), бот.
- Визуализация: 4 горизонтальных бара с убывающей шириной (`width = step.count / max(steps)`). Под каждым — абсолютное число и процент дроп‑оффа.
- Tooltip с tooltip-объяснением что считается на каждом шаге.

### Реализация баров (без библиотеки графиков)

```tsx
<div className="space-y-2">
  {steps.map((s, i) => (
    <div key={s.name}>
      <div className="flex justify-between text-sm mb-1">
        <span>{s.name}</span>
        <span className="font-medium">{s.count.toLocaleString()}</span>
      </div>
      <div className="h-9 bg-zinc-100/60 rounded-xl overflow-hidden">
        <div
          className="h-full gradient-primary"
          style={{ width: `${(s.count / steps[0].count) * 100}%` }}
        />
      </div>
      {i > 0 && (
        <div className="text-[11px] text-zinc-500 mt-1">
          Прошли {((1 - s.drop_pct) * 100).toFixed(1)}%
          · Отвалилось {(s.drop_pct * 100).toFixed(1)}%
        </div>
      )}
    </div>
  ))}
</div>
```

### Под воронкой
Таблица «Детализация по дням» — построить через `/api/stats/funnel?from=&to=` для каждого дня выбранного периода. Или принять `granularity=day` параметр на бэкенде.

---

## Шаг 2.5 — Frontend: страница `/products-analytics`

Новый пункт меню «Аналитика продуктов».

Таблица с колонками:
- Название и код
- Заявок за период
- Оплат за период
- Конв. заявка → оплата (с прогресс-баром визуально)
- Средний чек
- Выручка
- Активных подписок сейчас
- Разрез по периодам — 3 sub-колонки или раскрывающаяся секция (`<details>` на toggle)

Фильтры: период, только активные продукты (`is_active=true`) — по умолчанию.

Сортировка по любой числовой колонке (выручка по умолчанию).

---

## Шаг 2.6 — Расширение главного дашборда

В `admin/app/(dash)/page.tsx`:

### KPI-плитки
Сейчас одно значение. Добавить переключатель окна **7д / 30д / 90д** на каждой плитке (или общий переключатель сверху). Под цифрой — sparkline.

### Sparkline (без библиотеки)

```tsx
function Sparkline({ data }: { data: number[] }) {
  const max = Math.max(...data, 1);
  const points = data
    .map((v, i) => `${(i / (data.length - 1)) * 100},${100 - (v / max) * 100}`)
    .join(' ');
  return (
    <svg viewBox="0 0 100 30" className="w-full h-8 mt-2" preserveAspectRatio="none">
      <polyline
        fill="none"
        stroke="url(#sparkGradient)"
        strokeWidth="1.5"
        points={points}
      />
      <defs>
        <linearGradient id="sparkGradient" x1="0" x2="1">
          <stop offset="0%"   stopColor="#4f46e5" />
          <stop offset="100%" stopColor="#a855f7" />
        </linearGradient>
      </defs>
    </svg>
  );
}
```

### Блок «Топ-3 источника» за 30д
Карточка с тремя строками: `utm_source` + revenue + payments. Линк на `/sources` с пред-выставленным фильтром.

### Блок «Активные подписки»
Сейчас: «Активные подписки: N · Истекают за 7 дней: M». Расширить: показать 7д / 14д / 30д истечений как мини-стек (3 числа подряд с подписями).

---

## Чек-лист Phase 2

- [ ] `GET /api/stats/funnel` с фильтрами и расчётом drop_pct
- [ ] `GET /api/stats/products` с разрезом by_period
- [ ] Расширение `GET /api/stats/overview` (30д/90д, sparklines, top_sources)
- [ ] SQL для sparkline на каждую метрику
- [ ] SQL для top_sources_30d
- [ ] Frontend: страница `/funnel` с визуализацией баров
- [ ] Frontend: страница `/products-analytics` с таблицей и by_period
- [ ] Frontend: расширение KPI-плиток главного дашборда (переключатель окна)
- [ ] Frontend: компонент `Sparkline` (без зависимостей)
- [ ] Frontend: блок «Топ-3 источника» на главном
- [ ] Frontend: блок «Активные подписки» с разбивкой по 7/14/30
- [ ] Добавление пунктов меню «Воронка», «Аналитика продуктов» в layout
- [ ] Acceptance-тесты
