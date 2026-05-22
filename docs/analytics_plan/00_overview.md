# 00. Обзор модуля атрибуции и аналитики

## Что добавляем

1. **Трекинговые ссылки с UTM** — отдельная таблица `tracking_links`, генерация slug, deep-link `t.me/<bot>?start=<slug>`. Это альтернатива «UTM в URL» — короче, чище, легче считать.
2. **First-touch на пользователе** — при первом `/start` записываем источник в `users.first_utm_*`. Не перезаписываем никогда.
3. **Last-touch на заявке и оплате** — `leads.tracking_link_id` и копия UTM-полей снапшотом. Снапшот защищает от потери атрибуции при удалении/деактивации ссылки.
4. **Контекст «текущей ссылки»** на `users` с TTL 30 минут — между `/start` и нажатием «Оставить заявку».
5. **Отчёты**: источники, воронка клик→start→заявка→оплата, продуктовая аналитика, retention подписок.

## Принципиальные решения (из ТЗ)

- Подход к ссылкам: **отдельная таблица** `tracking_links` (вариант B), не «UTM в payload».
- Slug 8 символов `[A-Za-z0-9]`, генерируется автоматически, можно задать custom (за «Расширенные настройки»).
- **Slug + product.code в общем namespace** — нельзя создать `tracking_link.slug = 'yoga12'`, если есть `product.code = 'yoga12'`. И наоборот.
- TTL контекста = 30 минут. Хранится в `users.current_tracking_link_id` + `current_link_set_at`, без Redis.
- `events`-таблицу **на старте не вводим**. Все отчёты — JOIN-ами по существующим таблицам. Events добавится в Фазе 4 ради micro-conversions.
- Если у заявки `current_link` истёк (TTL) — UTM остаются NULL. Не наследуем из first-touch user. Это даёт чистое деление first-touch / last-touch.

## Поток данных (end-to-end)

```
1. Admin → POST /api/tracking-links  ─►  tracking_link с slug ABC123
2. Клиент видит ссылку в рекламе
3. Клиент кликает t.me/<bot>?start=ABC123
4. Bot.on_start():
   - resolve "ABC123" → tracking_link OR product.code (приоритет: tracking_link)
   - click_count += 1
   - upsert(user) → если новый: установить first_utm_*, first_product_id, first_tracking_link_id; unique_users += 1
   - SET users.current_tracking_link_id = ABC123.id, current_link_set_at = now()
   - show product card
5. Клиент нажимает «Оставить заявку»
6. Bot.cb_lead():
   - если now - current_link_set_at <= 30 минут:
       создаём lead с tracking_link_id + копией UTM-полей
   - иначе:
       lead.tracking_link_id = NULL, lead.utm_* = NULL
7. Admin → POST /api/payments
   - payment.tracking_link_id наследуется от lead (если есть)
8. Существующий поток выдачи доступа — без изменений
```

## Что в проекте УЖЕ есть на старте (не ломаем)

- ✅ Telegram-бот с handlers `start_with_code` (deep-link `t.me/<bot>?start=<code>` → product.code).
- ✅ Эндпоинт `GET /api/stats/overview` (базовые цифры) — расширяем.
- ✅ Дашборд `/` на Next.js — расширяем.
- ✅ Сущности `users`, `leads`, `payments`, `products`, `subscriptions` — добавляем колонки.

## Что меняется (резюме)

| Слой | Изменения |
|------|-----------|
| БД | 1 новая таблица + 17 новых колонок |
| Бот | резолвер /start расширяется, обогащение контекста |
| Backend сервисы | новый `tracking_links`, расширение `users` и `leads` |
| API | CRUD `/api/tracking-links` + 3 новых `/api/stats/*` |
| Админка | секция в карточке продукта + 3 новые страницы (`/sources`, `/funnel`, `/products-analytics`) |

## Дополнительные модули, не покрытые ТЗ напрямую (но взаимосвязанные)

- `payments.admin_id` — добавляется в миграции 004, но используется только когда появятся роли (Фаза 4).
- QR-коды — Фаза 1, эндпоинт `GET /api/tracking-links/{id}/qr.png`.
- Кастомные slug — Фаза 1, разрешены.

## Риски и митигация

| Риск | Митигация |
|------|-----------|
| Slug коллизия с product.code | check при создании в обе стороны (validator в сервисе) |
| Потеря атрибуции при удалении ссылки | UTM-поля копируются снапшотом в lead/payment |
| Битая ссылка в рекламе | fallback: показать каталог + текст «ссылка устарела» |
| TTL вылетел между /start и заявкой | сознательно: считаем «органикой», атрибуция NULL |
| Гонка: одновременный /start от одного user | `set_first_touch` делает `WHERE first_bot_id IS NULL` — защищает от перезаписи |
| Бэкфил перетрёт live данные | в скрипте `UPDATE ... WHERE first_product_id IS NULL` — идемпотентен |
| Slug-generator не найдёт уникальный за 10 попыток | при 62^8 пространстве — невозможно при разумных объёмах; raise после 10 попыток |

## Что NOT в скоупе

- Дедупликация Telegram-пользователя между разными ботами (один TG user = одна запись `users` пока).
- Hard-delete пользователя (не реализован в API, добавится отдельно).
- Multi-touch attribution (linear / time-decay). Только first и last.
