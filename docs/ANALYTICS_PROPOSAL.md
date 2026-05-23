# Аналитика и атрибуция — план + аудит данных

> Документ отвечает на два вопроса:
> 1. **Что у нас сейчас в БД** — что фиксируется, а что нет, и какие метрики можно вытащить уже сегодня без миграций.
> 2. **Как должна выглядеть аналитика** — концепт страницы «Эффективность» с time-series графиками, фильтрами и pareto-таблицей.
>
> Не реализация, только дизайн + reality-check.

---

## Часть 1. Что фиксируется сейчас (аудит моделей)

Прошёлся по 12 моделям в `backend/app/models/`. Картина по факту:

### 1.1 Timestamped events — золото для time-series ✅

Эти таблицы хранят **каждое событие отдельно с точным временем** — на их основе можно строить любые графики «по дням» без потери информации.

| Таблица | Ключевые поля | Что можно вытащить |
|---|---|---|
| `Lead` | `created_at`, `contacted_at`, `paid_at`, `closed_at` + `utm_source/medium/campaign` + `tracking_link_id` + `product_id` + `user_id` + `status` | Поток заявок по дням × источник × продукт; time-to-contact, time-to-pay; конверсии по utm |
| `Payment` | `created_at` + `amount` + `tracking_link_id` + `product_id` + `user_id` + `period_months` | Выручка по дням × источник × продукт; средний чек; LTV per user |
| `FunnelEntry` | `started_at`, `completed_at`, `cancelled_at` + `source` ('tracking_link'/'trigger'/'manual') + `source_ref` + `funnel_id` + `user_id` + `status` + `cancel_reason` | Входы в воронку по дням; конверсии воронок; причины отвала |
| `ScheduledMessage` | `scheduled_at`, `sent_at`, `cancelled_at` + `funnel_step_id` + `funnel_entry_id` + `error` + `attempts` | **Step-by-step конверсия воронки** — сколько юзеров дошли до шага N (по `sent_at IS NOT NULL`) |
| `Subscription` | `created_at`, `starts_at`, `ends_at` + `payment_id` + `product_id` + `user_id` + `status` | Активная база по дням × продукт × источник (через JOIN Payment → TrackingLink) |
| `User` | `first_seen_at` + **`first_utm_source/medium/campaign`** + `first_tracking_link_id` + `first_product_id` + `first_bot_id` | **First-touch attribution** — заморожен снапшот первого касания |

### 1.2 Counters без time-series — слепая зона ❌

Эти счётчики инкрементятся в БД, но **момент инкремента нигде не фиксируется**:

| Поле | Что теряем |
|---|---|
| `TrackingLink.click_count` | Когда были клики — неизвестно. Только итоговое число |
| `TrackingLink.unique_users` | То же — нет timeline кто и когда первый раз кликнул |
| `LeadMagnet.download_count` | Когда скачали и кто — неизвестно |
| `FunnelTrigger.use_count` | Когда сработал триггер и кто его написал — неизвестно |

**Следствие:** не получится построить графики
- «Клики по дням × utm» — упрётся в то что click_count это число «всего»
- «Скачивания лидмагнита X в декабре vs январе»
- «Топ-10 кодовых слов по неделям»
- CTR (клик→первое сообщение в боте) в динамике

Сейчас единственный способ узнать «кликов сегодня» — сравнить snapshot click_count со вчерашним. У нас snapshot'ов нет.

### 1.3 Что фиксируется частично

- **Funnel step-conversion** — через `ScheduledMessage.sent_at IS NOT NULL` можно сказать «сколько юзеров получили шаг N». Но **нет факта «открыл/прочитал сообщение»** (это и Telegram нам не отдаёт, кроме reactions/views для каналов) и **нет факта «кликнул кнопку шага»**.
- **Источник перехода в воронку** — `FunnelEntry.source` хранит 'tracking_link'/'trigger'/'manual' + `source_ref`. Можно JOIN'нуть с TrackingLink для utm. Но для триггеров utm нет в принципе (зашёл по кодовому слову — без меток).
- **Attribution models** — у нас сейчас mixed:
  - `User.first_utm_*` = **first-touch** (первое касание)
  - `Lead.utm_*` / `Lead.tracking_link_id` = **last-touch перед заявкой** (что было в `current_tracking_link_id` юзера на момент клика «Хочу»)
  - `Payment.tracking_link_id` = наследуется от последнего лида юзера для этого продукта
  - `Subscription` → `Payment` → `TrackingLink` (косвенно)

  Это **mismatch**, который надо явно показывать в UI: «по источнику привода (first-touch)» vs «по источнику оплаты (last-touch)». Разница для бизнеса принципиальна — Instagram может приводить, а покупки идут через ретаргет в Telegram.

---

## Часть 2. Что можно посчитать СЕЙЧАС, без миграций

Все эти метрики выводятся из существующих timestamped таблиц — нужны только новые API-эндпоинты и графики на фронте.

### 2.1 Lead funnel по дням × dimension

```sql
SELECT
  date_trunc('day', l.created_at) AS day,
  l.utm_source AS dim,
  count(*) AS leads,
  count(l.paid_at) AS paid_leads,
  avg(extract(epoch FROM l.paid_at - l.created_at)/3600) AS avg_hours_to_pay
FROM leads l
WHERE l.created_at BETWEEN $from AND $to
  AND ($product_id IS NULL OR l.product_id = $product_id)
GROUP BY 1, 2
```

Dimension может быть: `utm_source`, `utm_campaign`, `tracking_link_id`, `product_id`, или комбинация.

### 2.2 Revenue по дням × source

```sql
SELECT
  date_trunc('day', p.created_at) AS day,
  COALESCE(tl.utm_source, '— органика —') AS source,
  count(*) AS payments,
  sum(p.amount) AS revenue
FROM payments p
LEFT JOIN tracking_links tl ON tl.id = p.tracking_link_id
WHERE p.created_at BETWEEN $from AND $to
GROUP BY 1, 2
```

Готов для **stacked area chart** «выручка по источникам во времени».

### 2.3 Funnel step-conversion (на основе ScheduledMessage)

```sql
SELECT
  fs.order_idx,
  fs.message_text,
  count(DISTINCT sm.funnel_entry_id) FILTER (WHERE sm.sent_at IS NOT NULL) AS reached,
  count(DISTINCT sm.funnel_entry_id) FILTER (WHERE sm.cancelled_at IS NOT NULL) AS cancelled_here
FROM funnel_steps fs
LEFT JOIN scheduled_messages sm ON sm.funnel_step_id = fs.id
WHERE fs.funnel_id = $funnel_id
GROUP BY fs.id, fs.order_idx, fs.message_text
ORDER BY fs.order_idx
```

Дополнительно: какие юзеры сделали `Lead`/`Payment` после конкретного шага — JOIN `funnel_entries.user_id` с `leads.user_id` где `leads.created_at > scheduled_messages.sent_at` (если есть step ID самого «триггерного» шага).

**Получаем funnel-vis вида:**
```
Шаг 1 «Привет»        ████████████████ 1200 (100%)
Шаг 2 «Польза»        ███████████████  1180 (98%)
Шаг 3 «Кейс»          █████████████    1050 (87%)  ← upsell?
Шаг 4 «CTA»           █████████         720 (60%)
       ↓ заявки               180 (15% от старта)
       ↓ оплаты                95 ( 8% от старта)
```

### 2.4 LTV per first-touch source

```sql
SELECT
  u.first_utm_source,
  count(DISTINCT u.id) AS users,
  count(DISTINCT p.user_id) AS paying_users,
  sum(p.amount) AS total_revenue,
  sum(p.amount) / NULLIF(count(DISTINCT p.user_id), 0) AS revenue_per_payer
FROM users u
LEFT JOIN payments p ON p.user_id = u.id
WHERE u.first_seen_at BETWEEN $from AND $to
GROUP BY u.first_utm_source
ORDER BY total_revenue DESC
```

Это **first-touch attribution** — реально честный взгляд: «Instagram привёл 1000 юзеров, из них 50 заплатили хоть раз, в среднем по 5k».

### 2.5 Cohort: возвращаются ли юзеры

```sql
SELECT
  date_trunc('month', u.first_seen_at) AS cohort,
  date_trunc('month', p.created_at) AS pay_month,
  count(DISTINCT p.user_id) AS paying_users,
  sum(p.amount) AS revenue
FROM users u
JOIN payments p ON p.user_id = u.id
WHERE u.first_seen_at >= $from
GROUP BY 1, 2
```

→ Cohort heatmap «когорта × месяц оплаты».

### 2.6 Воронки по эффективности

```sql
SELECT
  f.id, f.name,
  count(fe.id) AS entered,
  count(*) FILTER (WHERE fe.status = 'completed') AS completed,
  count(*) FILTER (WHERE fe.status = 'cancelled') AS cancelled,
  count(p.id) AS resulting_payments,
  sum(p.amount) AS revenue_attributed
FROM funnels f
LEFT JOIN funnel_entries fe ON fe.funnel_id = f.id
LEFT JOIN payments p ON p.user_id = fe.user_id
                    AND p.product_id = f.product_id
                    AND p.created_at >= fe.started_at
                    AND p.created_at <= COALESCE(fe.completed_at, fe.cancelled_at, now())
WHERE fe.started_at BETWEEN $from AND $to
GROUP BY f.id, f.name
```

**Внимание:** атрибуция тут «оплата после входа в воронку и в её рамках» — допущение, не строгая causation. У юзера мог быть параллельный путь.

---

## Часть 3. Что НЕ посчитать сейчас (gap-analysis)

| Метрика | Почему нельзя | Что нужно для фикса |
|---|---|---|
| Клики по дням × utm | `click_count` — счётчик без timestamp | таблица `click_events(link_id, user_id, ts)` |
| CTR клик→/start (lag во времени) | то же | то же |
| Скачивания лидмагнита по дням | `download_count` — счётчик | таблица `lead_magnet_downloads(magnet_id, user_id, ts, funnel_step_id?)` |
| Использования триггеров по дням | `use_count` — счётчик | таблица `funnel_trigger_uses(trigger_id, user_id, ts)` |
| Open-rate / read-rate шага | Telegram такое не отдаёт ботам | (без vоркараунда не получить — Telegram API ограничение) |
| Click-rate кнопок в шаге | Кнопки сохраняются как JSON, при клике пока не логируются | таблица `funnel_button_clicks(step_id, user_id, button_idx, ts)` |
| Multi-touch attribution (Facebook→Insta→YT) | У нас фиксируется только first и last, промежуточных касаний нет | таблица `user_touchpoints(user_id, ts, source, link_id)` — каждый клик отдельной строкой |
| Bounce из бота (зашёл → молчит) | Есть `User.first_seen_at` и `User.last_seen_at`, но без явного «совершил действие» | можно вывести из существующих данных, нужен явный SQL |

### Особый случай: last-touch для оплаты

Сейчас `Payment.tracking_link_id` берётся из последнего `Lead.tracking_link_id` (см. `backend/app/api/payments.py:93-115`). Это **last-touch для заявки**, а не для оплаты. Между заявкой и оплатой юзер мог несколько раз вернуться и кликнуть другую ссылку — последний реальный клик мы не зафиксируем (нет click_events).

**Импликация для отчётов:** ярлык «оплата по источнику X» означает «оплата после заявки, оставленной по источнику X». Это допущение надо проговаривать в подписях.

---

## Часть 4. Концепт страницы «Эффективность» (`/analytics`)

Новый раздел в сайдбаре, группа «Аналитика». Текущий `/sources` остаётся как простая таблица за период; `/analytics` — графики и сравнения.

### Хедер — фильтры

```
┌──────────────────────────────────────────────────────────────────────┐
│ Период: [7д] [30д] [90д] [Custom: 01.04 – 23.05]   Сравнение с пред. │
│ Продукт: [Все ▾]   Атрибуция: ⦿ Last-touch  ○ First-touch            │
│ Разрез: ⦿ Источник  ○ Кампания  ○ Воронка  ○ Лидмагнит  ○ Ссылка     │
└──────────────────────────────────────────────────────────────────────┘
```

«Атрибуция» — toggle между двумя моделями, важно для интеллектуальной честности отчёта.

### Блок 1 — Funnel-метрики Big Numbers

```
┌── Большие числа за период (с дельтой к предыдущему) ──┐
│  Уник.юзеров   Заявок    Оплат     Выручка   Ср.чек   │
│    1 240        180       95       380k       4k      │
│    +12% ▲      +5% ▲     -8% ▼    +3% ▲     +12% ▲   │
└────────────────────────────────────────────────────────┘
```

### Блок 2 — Stacked area: лиды/оплаты во времени

```
┌─ Лиды и оплаты по дням × источник ──────────────────────┐
│   ╱╲                                                     │
│  ╱  ╲___      ▓▓ instagram                              │
│ ╱       ╲     ▓▓ youtube                                │
│ ─────────     ▓▓ органика                               │
│ apr 1   may 23                                           │
└──────────────────────────────────────────────────────────┘
```

Toggle между «Лиды» / «Оплаты» / «Выручка».

### Блок 3 — Pareto-таблица топ-источников

```
┌─ Топ-источники за период ─────────────────────────────────────────┐
│ Источник    Кампания     Лидов  Оплат   CVR     Revenue    Δ      │
│ instagram   spring_promo  450    35    7.8%   140 000    +25% ▲  │
│ instagram   bio_link      280    18    6.4%    72 000     +5% ▲  │
│ youtube     review_v2     180    25   13.9%   100 000      ─     │
│ органика    —             330    17    5.2%    68 000    -10% ▼  │
└────────────────────────────────────────────────────────────────────┘
```

Сортируется по revenue/cvr/leads. Клик по строке — drill-down в `/sources?group_by=link` с пред-фильтром.

### Блок 4 — Эффективность воронок

```
┌─ Воронки за период ────────────────────────────────────┐
│ Welcome 7d         вход 1200 → завершили 800 → опл 100 │
│                    [спарклайн «оплаты по дням»]        │
│                    Конверсия: 8.3%   Revenue: 400k     │
│                                                         │
│ Black friday       вход  280 → завершили 220 → опл 45  │
│                    Конверсия: 16%    Revenue: 180k     │
└─────────────────────────────────────────────────────────┘
```

Клик по воронке → отдельная страница `/analytics/funnels/{id}` с step-by-step конверсией (использует §2.3 выше).

### Блок 5 — Лидмагниты (ОГРАНИЧЕНО)

Пока есть только counters → можно показать **только итоговые числа за всё время**, не динамику:

```
┌─ Топ-лидмагниты (всего) ────────────────────────┐
│ Чек-лист «10 ошибок»        download_count 1450 │
│ Гайд «План на 30 дней»        635 │
│ Видео-урок интро              280 │
└──────────────────────────────────────────────────┘
⚠️ Динамика по дням недоступна. Нужна таблица lead_magnet_downloads.
```

Этот блок — мотивация для Phase B.

---

## Часть 5. Рекомендации в порядке value/effort

### Phase A — без миграций (1 день)

- `GET /api/stats/timeline?from&to&granularity=day&dimension=source|campaign|funnel|product&product_id=X&attribution=last|first`
- `GET /api/stats/funnels/{id}/conversion` — на основе `ScheduledMessage`
- `GET /api/stats/funnels/summary?from&to` — топ воронок
- Страница `/analytics` с блоками 1–4
- Recharts (stacked area, line, bar) + наша Pareto-таблица

**Делает ~85% того что бизнес обычно хочет.** Без новых таблиц.

### Phase B — событийная фиксация (1 день миграции + 0.5 день UI)

- Миграция Alembic: `click_events`, `lead_magnet_downloads`, `funnel_trigger_uses`
- `click_count` / `unique_users` / `download_count` / `use_count` — оставляем как cache колонку (триггер или вычисляем at read), но первичный источник — events
- Бот при `/start <slug>` пишет `click_event` параллельно с инкрементом
- Лидмагнит при отправке пишет `lead_magnet_download` параллельно

После Phase B становится доступно:
- Клики по дням × utm
- CTR клик→первое сообщение в боте
- Скачивания лидмагнита по дням
- Корреляция «прикрепили магнит к шагу N → скачивания выросли»

### Phase C — продвинуто (отложить, когда понадобится)

- `funnel_button_clicks` — для CR кнопок
- `user_touchpoints` — multi-touch attribution
- Materialized view `daily_metrics` — когда live `GROUP BY date_trunc` начнёт упираться (>1M строк или большие периоды)
- ML-attribution (Markov, Shapley) — когда multi-touch появится

---

## Часть 6. Открытые вопросы

1. **Какая модель атрибуции по умолчанию?** Last-touch удобнее для performance-маркетинга («куда лить»), first-touch — для бренда («откуда узнают»). Предлагаю **toggle с дефолтом last-touch + подсказкой о разнице**.

2. **Сравнение периодов** — «vs предыдущий период такой же длины» или «vs тот же период прошлого года»? Первое проще и обычно полезнее, второе — для сезонного бизнеса.

3. **Drill-down или новая страница?** При клике на «Instagram» в таблице — фильтровать тут же или открывать `/sources?utm_source=instagram`? Я бы делал inline-фильтр (без потери контекста), а Sources оставить для CSV-экспорта.

4. **Сегментация по продукту обязательна?** Если у бизнеса 1 продукт — фильтр не нужен, страница проще. Если 5+ продуктов разной ценовой категории — фильтр обязателен и его выбор сильно меняет картину.

5. **Realtime или batch?** Сейчас все live-запросы — это OK для текущего объёма. Если будут хотеть «сколько лидов сегодня в реалтайме» — добавить SWR refresh каждые 30s достаточно. ClickHouse / Materialize пока преждевременно.

---

## Часть 7. Что добавить в backlog после прочтения

- [ ] `/api/stats/timeline` endpoint (Phase A)
- [ ] `/api/stats/funnels/{id}/conversion` endpoint (Phase A)
- [ ] Страница `/analytics` + 4 блока (Phase A)
- [ ] Миграция `click_events`, `lead_magnet_downloads`, `funnel_trigger_uses` (Phase B)
- [ ] Доп. event-logging в боте (Phase B)
- [ ] Документ-проверка: attribution-toggle действительно меняет цифры в UI

---

## Часть 8. Критичные нюансы текущей реализации (must-know перед стартом)

Это места в существующем коде, которые **тихо ломают честность аналитики**,
если их не учесть в SQL запросах и подписях графиков. Не баги — просто
особенности, о которых не знаешь, пока не сядешь писать отчёт.

### 8.1 `current_tracking_link` имеет TTL 30 минут

`backend/app/bot/handlers.py:CURRENT_LINK_TTL` — если юзер кликнул ссылку,
а потом выждал >30 минут перед «Хочу» — Lead создастся **без `tracking_link_id`**
(будет null → попадёт в «органику»).

**Следствие:** часть атрибутированных оплат «съест» органика. Если у тебя
длинный цикл размышления (юзер думает день-два после клика) — last-touch
атрибуция будет систематически занижать вклад источников.

**Что сделать:** в подписях writeл «last-touch с TTL 30 мин» и предложить
toggle на first-touch (где TTL не действует — `User.first_utm_*` живёт вечно).

### 8.2 `Payment.tracking_link_id` наследуется от ПОСЛЕДНЕГО лида

`backend/app/api/payments.py:93-115` — при создании платежа берётся последний
`Lead` юзера **для того же продукта** с непустым `tracking_link_id`.

**Что это значит:**
- Если у юзера 3 лида на один продукт (вернулся 3 раза по разным ссылкам) —
  оплата атрибутируется на источник последнего лида.
- Если все 3 лида были органикой — оплата = органика, даже если изначально
  был трафик-источник.
- Если у юзера лиды по разным продуктам, оплата идёт по своему продукту —
  чужие лиды не путают.

**Что сделать:** в SQL для revenue-by-source **не** делать `JOIN users.first_utm_*`
для last-touch — это смешает модели. Использовать ровно `Payment.tracking_link_id`.

### 8.3 Триггеры (кодовые слова) приходят без UTM

`FunnelEntry.source='trigger'` + `source_ref=trigger_id` — пути utm нет
в принципе. Юзер написал «КЛУБ» — мы не знаем откуда он узнал это слово.

**Следствие:** триггеры в отчёте по источникам всегда будут «органикой».
Если основной канал привода — кодовые слова в постах → нужно отдельное
измерение «эффективность триггеров» (счётчик `use_count` за период,
но без time-series пока — см. слепую зону §1.2).

**Что сделать сейчас:** косвенно мерить — `FunnelEntry where source='trigger'`
+ JOIN последующих Payment. Группировать по `trigger_id`, не по utm.

### 8.4 ScheduledMessage: `sent_at IS NULL` ≠ «юзер не увидел»

В шаг-конверсии (§2.3) фильтр `sent_at IS NOT NULL` означает «бот успешно
отправил». Но `sent_at IS NULL` может означать **3 разные вещи**:

1. **Время ещё не пришло** (`scheduled_at > now()`) — нормально, ждём
2. **Юзер отключил уведомления** (`User.notifications_enabled=False`) —
   воркер пропускает отправку
3. **Telegram отверг сообщение** (`error IS NOT NULL`, `attempts > 0`) —
   обычно потому что юзер заблокировал бота или удалил аккаунт
4. **Воронка cancel'нулась раньше** (`cancelled_at IS NOT NULL`)

**Что сделать:** в честной step-conversion разделить:
```sql
COUNT(*) FILTER (WHERE sent_at IS NOT NULL)               AS delivered,
COUNT(*) FILTER (WHERE sent_at IS NULL AND scheduled_at > now())  AS pending,
COUNT(*) FILTER (WHERE cancelled_at IS NOT NULL)          AS cancelled_step,
COUNT(*) FILTER (WHERE error IS NOT NULL)                 AS failed_delivery
```

Особенно важно: если 30% юзеров отключили уведомления (`notifications_enabled=False`),
твоя «конверсия шагов» будет искажена — это не отвал, это unreachable audience.

### 8.5 `cancel_on_payment=True` — entries обрезаются автоматически

`Funnel.cancel_on_payment=True` (default) — при оплате воронка для этого
юзера принудительно отменяется (`FunnelEntry.status='cancelled'`,
`cancel_reason='paid'`).

**Следствие:** если просто посчитать `COUNT(*) WHERE status='completed'` /
`COUNT(*)` — заниженная конверсия. Юзер купил на 3-м шаге из 7 — воронка
не «completed», она «cancelled by payment». Это **успех**, не отвал.

**Что сделать в SQL:**
```sql
-- "Успешный" исход воронки = completed ИЛИ cancelled-by-payment
COUNT(*) FILTER (
  WHERE status = 'completed'
     OR (status = 'cancelled' AND cancel_reason = 'paid')
) AS successful_outcomes
```

Без этого правила топ-воронки в отчёте будут перевёрнуты — те что лучше
конвертируют в оплату будут выглядеть как «худшие по completion rate».

### 8.6 Тестовые прогоны попадают в данные

`backend/app/api/funnels.py:test_run` создаёт реальный `FunnelEntry`
с `source='manual'`, `source_ref=admin.id`, и виртуального юзера с
**отрицательным `telegram_user_id`** (`-admin.id`) если у админа нет
своего TG-аккаунта в системе.

**Следствие:** если ты гонял тест 50 раз — 50 fake entries в твоей
аналитике. Тестовый юзер с отрицательным id ещё и в `User` сидит.

**Что сделать:** во все SQL аналитики добавить:
```sql
WHERE fe.source != 'manual'
  AND u.telegram_user_id > 0
```

Можно также в `User` ввести колонку `is_test BOOL DEFAULT FALSE` и
ставить True для test-юзеров — будет чище. Но это миграция.

### 8.7 Подписки могут перекрываться по продукту

У одного юзера может быть несколько `Subscription` на один продукт
(продление, перевыпуск). При «активная база по продуктам» наивный
`COUNT(DISTINCT subscription_id)` будет дублировать.

**Что сделать:** считать по `DISTINCT user_id + product_id WHERE status='active'`
или явно показывать «активные подписки» vs «активных пользователей».

### 8.8 `notifications_enabled` влияет на ВСЁ что шлёт бот

`User.notifications_enabled=False` блокирует:
- Сообщения воронки (ScheduledMessage пропускается воркером)
- Лидмагниты (если их шлёт бот сам)
- Любые push-уведомления

**Следствие:** при анализе «эффективность воронки X для аудитории Y» надо
понимать сколько в Y юзеров с отключёнными уведомлениями — иначе сравниваешь
с маркетинговой воронкой яблоки vs половинку яблока.

### 8.9 `Lead.status` имеет 4 значения, не 2

Не «открыта / закрыта». Возможные значения по коду:
- `new` — только что создана
- `contacted` — админ кликнул «связались»
- `paid` — автоматически выставляется когда `Payment` приходит на тот же
  user+product (см. `payments.py`)
- `closed` — админ вручную закрыл (отказ, спам и т.п.)

**Импликация для отчётов:** «конверсия Lead→Payment» НЕ должна считаться
как `paid_leads / total_leads`. Должна быть `paid_leads / (paid_leads + new + contacted)`
— исключая `closed` (это явный «не покупатель», не отвал воронки).

### 8.10 Часовые пояса

Все timestamps в БД — UTC (`DateTime(timezone=True)`). Группировка
`date_trunc('day', created_at)` режет по **UTC-полуночи**, а не по
московской полуночи.

**Следствие:** «лиды за вторник» включают события с 03:00 МСК вторника
до 03:00 МСК среды. Может вводить в заблуждение когда смотришь на
паттерны «утро/вечер».

**Что сделать:** в SQL делать `date_trunc('day', created_at AT TIME ZONE 'Europe/Moscow')`,
ИЛИ позволять админу выбрать TZ в настройках профиля, ИЛИ хотя бы
писать в подписях графика «время UTC».

---

## Часть 9. Что измерить на проде ДО реализации

Все красивые планы аналитики бесполезны если данные не дают сигнала.
Перед тем как пилить страницу `/analytics`, прогнать эти SQL на проде
и решить — есть ли что показывать.

### 9.1 Какая доля лидов вообще атрибутирована

```sql
SELECT
  COUNT(*) AS total,
  COUNT(*) FILTER (WHERE tracking_link_id IS NOT NULL) AS attributed,
  ROUND(100.0 * COUNT(*) FILTER (WHERE tracking_link_id IS NOT NULL) / NULLIF(COUNT(*),0), 1) AS pct
FROM leads
WHERE created_at >= now() - interval '30 days';
```

**Решение:** если `pct < 10%` — отчёт по utm бесполезен, надо сначала
запустить трафик через tracked-ссылки. Показать на дашборде warning.

### 9.2 Распределение источников

```sql
SELECT
  COALESCE(utm_source, '— органика —') AS source,
  COUNT(*) AS leads
FROM leads
WHERE created_at >= now() - interval '30 days'
GROUP BY 1
ORDER BY 2 DESC;
```

**Решение:** если 1 источник = 95% — Pareto-таблица не нужна, показать
один big-number. Если 5+ источников с >5% каждый — Pareto оправдан.

### 9.3 Сколько лидов на юзера

```sql
SELECT
  leads_per_user,
  COUNT(*) AS users
FROM (
  SELECT user_id, COUNT(*) AS leads_per_user FROM leads GROUP BY user_id
) t
GROUP BY 1 ORDER BY 1;
```

**Решение:** если >70% юзеров имеют ровно 1 лид — last-touch ≈ first-touch,
toggle избыточен. Если есть длинный хвост (юзеры с 5+ лидами) — toggle
действительно нужен.

### 9.4 Сколько ScheduledMessage в БД и какое состояние

```sql
SELECT
  COUNT(*) AS total,
  COUNT(*) FILTER (WHERE sent_at IS NOT NULL) AS sent,
  COUNT(*) FILTER (WHERE cancelled_at IS NOT NULL) AS cancelled,
  COUNT(*) FILTER (WHERE error IS NOT NULL) AS errored,
  COUNT(*) FILTER (WHERE sent_at IS NULL AND scheduled_at > now()) AS pending
FROM scheduled_messages;
```

**Решение:** если errored >5% → bot отваливается часто, step-conversion
будет неточной. Сначала фиксить bot-доставку, потом аналитику.

### 9.5 Сколько активных воронок и средняя глубина

```sql
SELECT
  f.id, f.name,
  COUNT(DISTINCT fs.id) AS steps,
  COUNT(DISTINCT fe.id) FILTER (WHERE fe.status = 'active') AS active_entries
FROM funnels f
LEFT JOIN funnel_steps fs ON fs.funnel_id = f.id
LEFT JOIN funnel_entries fe ON fe.funnel_id = f.id
WHERE f.is_active = true
GROUP BY f.id, f.name
ORDER BY active_entries DESC;
```

**Решение:** если у тебя 1 воронка из 3 шагов — funnel-step-conversion
блок (§4 страницы) можно сделать проще (3 столбика). Если 10 воронок
по 8 шагов — нужен полноценный funnel-visualization.

### 9.6 Доля юзеров с отключёнными уведомлениями

```sql
SELECT
  notifications_enabled,
  COUNT(*) AS users,
  ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER(), 1) AS pct
FROM users
GROUP BY notifications_enabled;
```

**Решение:** если >20% с `False` — в step-conversion обязательно
разделять «доставлено / не доставлено», иначе цифры будут вводить.

### 9.7 Тестовые данные

```sql
SELECT COUNT(*) FROM funnel_entries WHERE source = 'manual';
SELECT COUNT(*) FROM users WHERE telegram_user_id < 0;
```

**Решение:** перед запуском Phase A добавить в SQL аналитики
исключение тестовых данных (см. §8.6). Иначе твои показатели будут
шумными от собственного тестирования.

---

## Часть 10. Индексы которые понадобятся под Phase A

Чтобы `GROUP BY date_trunc(...) + utm_source` не упирался в seq scan
по большим таблицам — добавить (одной миграцией Alembic в начале Phase A):

```sql
-- Lead timeline by utm
CREATE INDEX IF NOT EXISTS ix_leads_created_at_utm
  ON leads (created_at, utm_source);

-- Lead timeline by tracking link
CREATE INDEX IF NOT EXISTS ix_leads_created_at_link
  ON leads (created_at, tracking_link_id);

-- Payment timeline by link
CREATE INDEX IF NOT EXISTS ix_payments_created_at_link
  ON payments (created_at, tracking_link_id);

-- Step conversion
CREATE INDEX IF NOT EXISTS ix_scheduled_messages_step_sent
  ON scheduled_messages (funnel_step_id, sent_at);

-- Funnel entry timeline
CREATE INDEX IF NOT EXISTS ix_funnel_entries_funnel_started
  ON funnel_entries (funnel_id, started_at);

-- First-touch attribution (для users)
CREATE INDEX IF NOT EXISTS ix_users_first_utm_source
  ON users (first_utm_source) WHERE first_utm_source IS NOT NULL;
```

При <100k строк в Lead/Payment они не нужны — Postgres делает seq scan
быстро. При росте до ~1M — без индексов запросы за месяц начнут идти 1+ сек,
а на год — десятки секунд. Можно добавить лениво, по факту проблемы.

