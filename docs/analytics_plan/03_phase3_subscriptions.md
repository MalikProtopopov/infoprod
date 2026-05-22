# Phase 3 — Подписки и retention

**Срок**: 2–3 рабочих дня. Запускается через **2–4 недели** после Phase 2 — нужны истёкшие подписки и попытки продлений для значимых цифр.

**Результат**: ясная картина здоровья подписочной базы (что и когда истекает, кто продлевается), готова инфраструктура для когортной матрицы.

---

## Шаг 3.1 — `GET /api/stats/subscriptions`

Новый эндпоинт.

### Что возвращаем

```json
{
  "snapshot": {
    "active":  124,
    "expired_30d_no_renewal": 18,
    "revoked_30d": 3,
    "expiring": {
      "next_7d":  12,
      "next_14d": 25,
      "next_30d": 48
    }
  },
  "renewal_rate": {
    "window_days": 30,
    "expired_in_period": 30,
    "renewed_within_30d": 12,
    "rate": 0.40
  },
  "by_product": [
    {
      "product_id": 3, "name": "Йога курс",
      "active": 24, "expired_30d": 5, "renewed_30d": 3, "rate": 0.60
    }
  ],
  "by_source_30d": [
    {"source": "instagram", "active": 12, "rate": 0.42}
  ]
}
```

### SQL для `renewal_rate`

Подписка считается «продлённой», если у того же `user_id` + `channel_id` есть `subscription` (или `payment`) с `created_at` в течение 30 дней после `expired.ends_at`.

```sql
WITH expired_in_period AS (
  SELECT s.id, s.user_id, s.channel_id, s.ends_at
  FROM subscriptions s
  WHERE s.status = 'expired'
    AND s.ends_at BETWEEN $from AND $to
),
renewed AS (
  SELECT DISTINCT e.id
  FROM expired_in_period e
  JOIN payments p
    ON p.user_id = e.user_id
   AND p.created_at BETWEEN e.ends_at AND e.ends_at + interval '30 days'
)
SELECT
  (SELECT COUNT(*) FROM expired_in_period)             AS expired_count,
  (SELECT COUNT(*) FROM renewed)                       AS renewed_count;
```

---

## Шаг 3.2 — Frontend: страница `/subscriptions-analytics`

Новый пункт меню «Подписки — аналитика» (или отдельная вкладка на существующей `/subscriptions`).

### Структура

**Блок 1 — Snapshot**
- 4 stat-карточки: Активные / Истекают за 7д / Истекают за 14д / Истекают за 30д
- Цветовые акценты: indigo / amber / amber / amber

**Блок 2 — Renewal rate**
- Большая цифра процента (например `40%`)
- Под ней: «Из 30 истёкших за период — продлились 12»
- Sparkline: rate по неделям за последние 12 недель

**Блок 3 — По продуктам**
- Таблица: продукт / активных / истекло / продлилось / rate (прогресс-бар)

**Блок 4 — По источникам**
- Таблица: utm_source / активных / rate
- Какие источники приводят самых «живучих» клиентов

### Фильтры
- Период (для расчётов rate)
- Продукт
- Источник

---

## Шаг 3.3 — Опционально: страница `/retention` (когортная матрица)

⚠️ **Когортная матрица будет давать значимые цифры через 2–3 квартала**. Инфраструктуру можно подготовить сейчас.

### Что показываем

Матрица: строки = когорта (месяц `users.first_seen_at`), столбцы = месяц после acquisition.

Значение в ячейке = доля пользователей когорты, у которых была активная подписка в этот месяц после acquisition.

| Cohort | M0 | M1 | M2 | M3 | … |
|--------|----|----|----|----|---|
| 2026-04 (N=128) | 100% | 24% | 18% | 14% | … |
| 2026-05 (N=215) | 100% | 28% | 22% | – | … |

### SQL (упрощённо)

```sql
WITH cohorts AS (
  SELECT id AS user_id,
         date_trunc('month', first_seen_at) AS cohort_month
  FROM users
),
activity AS (
  -- пользователь был активен в M_n если у него была активная подписка
  -- в любой день месяца N после cohort_month
  SELECT u.user_id, u.cohort_month,
         EXTRACT(YEAR FROM age(date_trunc('month', s.starts_at), u.cohort_month)) * 12
         + EXTRACT(MONTH FROM age(date_trunc('month', s.starts_at), u.cohort_month)) AS months_after
  FROM cohorts u
  JOIN subscriptions s ON s.user_id = u.user_id
)
SELECT cohort_month, months_after, COUNT(DISTINCT user_id)
FROM activity
GROUP BY 1, 2;
```

Из результата собрать матрицу в Python.

### Визуализация в UI

Тепловая карта (без `recharts` — обычные `<div>` с background `gradient-primary` и opacity = value).

```tsx
<div className="grid grid-cols-13 gap-1">
  {/* первая колонка = label когорты */}
  {cohorts.map((c) => (
    <Fragment key={c.month}>
      <div className="text-xs">{c.label}</div>
      {c.cells.map((v) => (
        <div className="h-8 rounded text-[10px] text-center"
             style={{ background: `rgba(99,102,241,${v})` }}>
          {(v * 100).toFixed(0)}
        </div>
      ))}
    </Fragment>
  ))}
</div>
```

---

## Шаг 3.4 — Подсветка истечений в существующей `/subscriptions`

В текущей таблице на `/subscriptions` (страница «Подписки»):
- Колонка «До» — подсветить amber для дат в течение 7 дней, red — просроченных.
- Добавить кнопку «Истекают за 7 дней» в фильтр (рядом с табами).

Лёгкое улучшение, не требует нового API.

---

## Чек-лист Phase 3

- [ ] `GET /api/stats/subscriptions` с snapshot, renewal_rate, by_product, by_source
- [ ] SQL для renewal_rate (с JOIN на payments в окне 30д после ends_at)
- [ ] Frontend: страница `/subscriptions-analytics`
- [ ] Подсветка истечений на `/subscriptions`
- [ ] (Опционально) Страница `/retention` с когортной матрицей
- [ ] (Опционально) Тепловая карта для retention без зависимостей
- [ ] Пункт меню «Подписки — аналитика»
- [ ] Acceptance-тесты

---

## Заметка по будущему

Когда `payments.admin_id` начнёт заполняться (Phase 4) — добавить разрез retention по менеджеру: какие менеджеры приводят клиентов, которые дольше остаются.
