**Mediann**

**Техническое задание**

Модуль атрибуции и аналитики

для платформы Infobizbot

*Версия 1.0 · Внутренний документ для разработки*

Май 2026

1\. Назначение модуля

Модуль атрибуции и аналитики добавляет к платформе Infobizbot три
ключевые возможности: генерацию трекинговых ссылок с UTM-параметрами для
использования в рекламе и маркетинговых каналах, сохранение источника
трафика для пользователя (first-touch) и для каждой заявки (last-touch),
отчёты для владельца платформы --- источники, воронка, продукты,
подписки, когорты.

Модуль не меняет существующий покупательский флоу --- он его обогащает
контекстом атрибуции. Сценарий клиента (приход через бот → заявка →
оплата → выдача доступа → автоотзыв по истечении) остаётся без
изменений.

1.1 Цели для владельца платформы

-   Понимать какие рекламные каналы реально приводят клиентов и какова
    их экономика (CAC, конверсии, выручка).

-   Видеть воронку «клик → старт → заявка → оплата» с разрезами по
    источнику, кампании, продукту и боту.

-   Сравнивать продукты между собой: какой даёт лучшую конверсию,
    средний чек, retention.

-   Следить за здоровьем подписочной базы: что и когда заканчивается,
    какой процент продлевается.

-   В перспективе --- оценивать когорты по месяцу прихода и источнику,
    считать LTV.

1.2 Принципиальные решения, зафиксированные на этапе проектирования

-   **Подход к ссылкам:** вариант B --- отдельная таблица tracking_links
    со slug. Не «UTM в payload».

-   **Атрибуция:** first-touch на уровне пользователя (сохраняется один
    раз и не перезаписывается), last-touch на уровне заявки и оплаты.

-   **Контекст «текущей ссылки»:** хранится в самой таблице users с TTL
    30 минут (без введения Redis).

-   **Логирование событий:** отдельная таблица events на старте не
    вводится. Все отчёты строятся поверх существующих таблиц с JOIN-ами.
    Events добавляется в Фазе 4 при необходимости считать
    micro-conversions.

-   **Slug формат:** 8 символов из набора \[A-Za-z0-9\], уникальность
    гарантируется в общем namespace с products.code (нельзя создать
    tracking_link с slug, совпадающим с существующим product.code, и
    наоборот).

2\. Резюме изменений

  -----------------------------------------------------------------------
  **Слой**          **Что добавляется**
  ----------------- -----------------------------------------------------
  База данных       1 новая таблица (tracking_links), 17 новых полей в
                    users / leads / payments

  Telegram-бот      Резолвер slug в /start, инкремент счётчиков ссылки,
                    сохранение first-touch при создании пользователя,
                    сохранение current_link для атрибуции последующего
                    lead

  Backend сервисы   Новый сервис tracking_links, расширение users /
                    leads, новые эндпоинты /api/stats/\*

  API               CRUD /api/tracking-links, новые эндпоинты
                    /api/stats/sources, /api/stats/funnel,
                    /api/stats/products

  Frontend          Секция «Ссылки и кампании» в карточке продукта с
  (админка)         модалкой-генератором, 3 новых страницы дашборда:
                    Источники, Воронка, Продуктовая аналитика. Расширение
                    главного дашборда

  Миграции          Бэкфил first-touch атрибуции для текущих
                    пользователей, проставление timestamps смены статусов
                    для существующих leads
  -----------------------------------------------------------------------

3\. Архитектурный подход

3.1 Поток данных от клика до атрибуции в оплате

Жизненный цикл атрибуции в системе выглядит так:

1.  Администратор создаёт tracking_link в админке: указывает продукт,
    источник, кампанию. Система генерирует уникальный slug и формирует
    URL t.me/\<bot\>?start=\<slug\>.

2.  Клиент видит ссылку (реклама, пост, сториз) и кликает по ней.

3.  Telegram открывает бот с командой /start \<slug\>. Бот резолвит slug
    в tracking_link, инкрементит click_count.

4.  Если пользователь новый --- создаётся запись в users с заполненными
    first_utm\_\*, first_product_id, first_tracking_link_id,
    first_bot_id. Инкрементируется unique_users у ссылки.

5.  В users.current_tracking_link_id сохраняется ID ссылки с
    current_link_set_at = now() --- это контекст «откуда пришёл сейчас»
    для последующих действий.

6.  Бот показывает карточку привязанного к ссылке продукта.

7.  Клиент жмёт «Оставить заявку». Создаётся lead с tracking_link_id =
    users.current_tracking_link_id, при условии что current_link_set_at
    не старше 30 минут.

8.  UTM-поля копируются в lead снапшотом --- даже если ссылка потом
    будет деактивирована или изменена, атрибуция заявки останется
    неизменной.

9.  Администратор фиксирует оплату --- payment наследует
    tracking_link_id от lead. Создаётся subscription, бот выдаёт
    invite-ссылку.

3.2 Логика резолва /start

Команда /start \<arg\> резолвится в боте по такому приоритету:

10. Поиск arg в tracking_links по slug. Если найдено и is_active = true
    --- используется этот контекст.

11. Иначе --- поиск arg в products.code (для прямого шеринга без
    атрибуции).

12. Если ничего не найдено --- показывается каталог активных продуктов с
    уведомлением «Ссылка устарела или недействительна».

Slug и product.code находятся в общем namespace --- при создании
tracking_link сервер проверяет, что slug не совпадает с существующим
product.code; и наоборот при создании / редактировании product.code. Это
даёт короткие URL без префиксов.

3.3 TTL контекста ссылки

Поле users.current_tracking_link_id обновляется на каждом /start с
валидной ссылкой. При создании заявки берётся это значение только если
current_link_set_at не старше 30 минут. Это решает три проблемы:

-   Если пользователь пришёл по ссылке месяц назад, потом сам зашёл в
    бот и оставил заявку --- заявка не будет ложно атрибутирована к
    старой ссылке.

-   Если пользователь возвращается по новой ссылке --- current_link
    перезаписывается, новая заявка атрибуцируется корректно.

-   Не нужно Redis или ин-мемори storage --- всё хранится в основной БД.

4\. Миграции базы данных

Все миграции применяются в порядке нумерации. Используется Alembic.
Структура каждой миграции описана ниже.

4.1 Миграция 001 --- таблица tracking_links

> CREATE TABLE tracking_links (
>
> id bigserial PRIMARY KEY,
>
> slug text NOT NULL UNIQUE,
>
> product_id bigint NOT NULL REFERENCES products(id) ON DELETE CASCADE,
>
> bot_id bigint NULL REFERENCES bots(id) ON DELETE SET NULL,
>
> utm_source text NOT NULL,
>
> utm_medium text NULL,
>
> utm_campaign text NULL,
>
> utm_content text NULL,
>
> notes text NULL,
>
> is_active boolean NOT NULL DEFAULT true,
>
> click_count int NOT NULL DEFAULT 0,
>
> unique_users int NOT NULL DEFAULT 0,
>
> created_by bigint NULL REFERENCES admins(id) ON DELETE SET NULL,
>
> created_at timestamptz NOT NULL DEFAULT now()
>
> );
>
> CREATE INDEX idx_tracking_links_product ON tracking_links(product_id);
>
> CREATE INDEX idx_tracking_links_active ON tracking_links(is_active,
> created_at DESC);
>
> CREATE INDEX idx_tracking_links_source ON tracking_links(utm_source);
>
> ALTER TABLE tracking_links
>
> ADD CONSTRAINT slug_valid_format
>
> CHECK (slug \~ \'\^\[A-Za-z0-9\_-\]{4,64}\$\');

Длина slug --- от 4 до 64 символов (ограничение Telegram start payload).
Допустимые символы: латинские буквы, цифры, подчёркивание, дефис.

4.2 Миграция 002 --- first-touch атрибуция на users

> ALTER TABLE users
>
> ADD COLUMN first_product_id bigint NULL REFERENCES products(id) ON
> DELETE SET NULL,
>
> ADD COLUMN first_tracking_link_id bigint NULL REFERENCES
> tracking_links(id) ON DELETE SET NULL,
>
> ADD COLUMN first_utm_source text NULL,
>
> ADD COLUMN first_utm_medium text NULL,
>
> ADD COLUMN first_utm_campaign text NULL,
>
> ADD COLUMN first_bot_id bigint NULL REFERENCES bots(id) ON DELETE SET
> NULL,
>
> ADD COLUMN current_tracking_link_id bigint NULL REFERENCES
> tracking_links(id) ON DELETE SET NULL,
>
> ADD COLUMN current_link_set_at timestamptz NULL;
>
> CREATE INDEX idx_users_first_source ON users(first_utm_source)
>
> WHERE first_utm_source IS NOT NULL;
>
> CREATE INDEX idx_users_first_product ON users(first_product_id)
>
> WHERE first_product_id IS NOT NULL;
>
> CREATE INDEX idx_users_first_seen ON users(first_seen_at DESC);

Поля first\_\* заполняются один раз при создании пользователя и не
перезаписываются. Поля current\_\* обновляются на каждом /start с
валидной ссылкой.

4.3 Миграция 003 --- last-touch атрибуция и таймстампы статусов на leads

> ALTER TABLE leads
>
> ADD COLUMN tracking_link_id bigint NULL REFERENCES tracking_links(id)
> ON DELETE SET NULL,
>
> ADD COLUMN utm_source text NULL,
>
> ADD COLUMN utm_medium text NULL,
>
> ADD COLUMN utm_campaign text NULL,
>
> ADD COLUMN contacted_at timestamptz NULL,
>
> ADD COLUMN paid_at timestamptz NULL,
>
> ADD COLUMN closed_at timestamptz NULL;
>
> CREATE INDEX idx_leads_tracking_link ON leads(tracking_link_id)
>
> WHERE tracking_link_id IS NOT NULL;
>
> CREATE INDEX idx_leads_status_created ON leads(status, created_at
> DESC);
>
> CREATE INDEX idx_leads_source ON leads(utm_source)
>
> WHERE utm_source IS NOT NULL;

UTM-поля копируются снапшотом при создании заявки --- это защита от
потери атрибуции при деактивации или удалении ссылки. Таймстампы
контакта / оплаты / закрытия проставляются при первом переходе в
соответствующий статус.

4.4 Миграция 004 --- атрибуция на payments

> ALTER TABLE payments
>
> ADD COLUMN admin_id bigint NULL REFERENCES admins(id) ON DELETE SET
> NULL,
>
> ADD COLUMN tracking_link_id bigint NULL REFERENCES tracking_links(id)
> ON DELETE SET NULL;
>
> CREATE INDEX idx_payments_admin ON payments(admin_id)
>
> WHERE admin_id IS NOT NULL;
>
> CREATE INDEX idx_payments_tracking_link ON payments(tracking_link_id)
>
> WHERE tracking_link_id IS NOT NULL;
>
> CREATE INDEX idx_payments_created ON payments(created_at DESC);

Поле admin_id --- кто из администраторов провёл платёж. Нужно для KPI
менеджеров на Фазе 3, когда появятся роли в admins. На старте может
оставаться NULL --- заполняется новыми платежами автоматически.

5\. Изменения в Telegram-боте

Изменения в файле backend/app/bot/handlers.py. Резолвер /start
расширяется, добавляется обогащение контекста при создании lead.

5.1 Обработка команды /start

> \@router.message(CommandStart(deep_link=True))
>
> async def start_with_arg(message: Message, command: CommandObject,
> bot_id: int):
>
> arg = command.args.strip() if command.args else None
>
> \# Шаг 1: резолвим аргумент
>
> tracking_link = None
>
> product = None
>
> if arg:
>
> tracking_link = await tracking_links_service.find_by_slug(arg)
>
> if tracking_link and tracking_link.is_active:
>
> product = await products_service.find_by_id(tracking_link.product_id)
>
> await tracking_links_service.increment_click_count(tracking_link.id)
>
> else:
>
> tracking_link = None
>
> product = await products_service.find_by_code(arg)
>
> \# Шаг 2: upsert пользователя
>
> tg_user = message.from_user
>
> user, is_new = await users_service.upsert(
>
> tg_user_id=tg_user.id,
>
> username=tg_user.username,
>
> first_name=tg_user.first_name,
>
> last_name=tg_user.last_name,
>
> language_code=tg_user.language_code,
>
> )
>
> \# Шаг 3: first-touch (только при создании user)
>
> if is_new:
>
> await users_service.set_first_touch(
>
> user_id=user.id,
>
> bot_id=bot_id,
>
> product_id=product.id if product else None,
>
> tracking_link=tracking_link,
>
> )
>
> if tracking_link:
>
> await tracking_links_service.increment_unique_users(tracking_link.id)
>
> \# Шаг 4: текущий контекст ссылки (для последующего lead)
>
> if tracking_link:
>
> await users_service.set_current_link(user.id, tracking_link.id)
>
> \# Шаг 5: показать карточку или каталог
>
> if product:
>
> await show_product_card(message, product)
>
> else:
>
> if arg:
>
> await message.answer(LINK_EXPIRED_OR_INVALID)
>
> await show_catalog(message, bot_id)

5.2 Обработка callback «Оставить заявку»

> \@router.callback_query(F.data.startswith(\"lead:\"))
>
> async def cb_lead(callback: CallbackQuery):
>
> product_id = int(callback.data.split(\":\")\[1\])
>
> user = await users_service.find_by_tg_id(callback.from_user.id)
>
> if not user:
>
> await callback.answer(\"Сессия истекла, нажмите /start\")
>
> return
>
> \# Берём current_tracking_link если контекст свежий
>
> tracking_link = None
>
> if user.current_tracking_link_id and user.current_link_set_at:
>
> age_seconds = (datetime.utcnow() -
> user.current_link_set_at).total_seconds()
>
> if age_seconds \< 30 \* 60: \# TTL 30 минут
>
> tracking_link = await tracking_links_service.find_by_id(
>
> user.current_tracking_link_id
>
> )
>
> \# Создаём заявку со снапшотом UTM
>
> lead = await leads_service.create(
>
> user_id=user.id,
>
> product_id=product_id,
>
> tracking_link_id=tracking_link.id if tracking_link else None,
>
> utm_source=tracking_link.utm_source if tracking_link else None,
>
> utm_medium=tracking_link.utm_medium if tracking_link else None,
>
> utm_campaign=tracking_link.utm_campaign if tracking_link else None,
>
> )
>
> await callback.message.answer(LEAD_SENT)
>
> await callback.answer()

5.3 Новые тексты для бота

-   LINK_EXPIRED_OR_INVALID --- отправляется когда /start \<arg\> не
    резолвится ни в активную трекинговую ссылку, ни в product.code.
    Пример: «Эта ссылка устарела или недоступна. Посмотрите наш каталог
    ниже».

6\. Сервисный слой

6.1 Новый сервис tracking_links

Файл: backend/app/services/tracking_links.py

> SLUG_CHARS = string.ascii_letters + string.digits
>
> SLUG_LENGTH = 8
>
> class TrackingLinksService:
>
> async def create(
>
> self, \*, product_id, utm_source, utm_medium=None, utm_campaign=None,
>
> utm_content=None, bot_id=None, notes=None, custom_slug=None,
> created_by=None
>
> ) -\> TrackingLink:
>
> slug = custom_slug or await self.\_generate_unique_slug()
>
> if not re.match(r\"\^\[A-Za-z0-9\_-\]{4,64}\$\", slug):
>
> raise ValueError(\"Invalid slug format\")
>
> if await self.\_slug_exists(slug):
>
> raise ConflictError(f\"Slug \'{slug}\' already taken\")
>
> if await self.\_slug_conflicts_with_product_code(slug):
>
> raise ConflictError(f\"Slug \'{slug}\' conflicts with existing product
> code\")
>
> \# INSERT \...
>
> return link
>
> async def \_generate_unique_slug(self, max_attempts=10) -\> str:
>
> for \_ in range(max_attempts):
>
> slug = \"\".join(secrets.choice(SLUG_CHARS) for \_ in
> range(SLUG_LENGTH))
>
> if not await self.\_slug_exists(slug):
>
> if not await self.\_slug_conflicts_with_product_code(slug):
>
> return slug
>
> raise GenerationError(\"Could not generate unique slug after 10
> attempts\")
>
> async def find_by_slug(self, slug: str) -\> Optional\[TrackingLink\]:
>
> \# SELECT \... WHERE slug = \$1
>
> async def find_by_id(self, link_id: int) -\> Optional\[TrackingLink\]:
>
> \# SELECT \... WHERE id = \$1
>
> async def increment_click_count(self, link_id: int):
>
> \# UPDATE tracking_links SET click_count = click_count + 1 WHERE id =
> \$1
>
> async def increment_unique_users(self, link_id: int):
>
> \# UPDATE tracking_links SET unique_users = unique_users + 1 WHERE id
> = \$1
>
> async def deactivate(self, link_id: int):
>
> \# UPDATE tracking_links SET is_active = false WHERE id = \$1
>
> async def list_for_product(self, product_id: int) -\>
> List\[TrackingLink\]:
>
> \# SELECT \... WHERE product_id = \$1 ORDER BY created_at DESC
>
> async def get_metrics(self, link_id: int) -\> dict:
>
> \"\"\"
>
> Возвращает: clicks, unique_users, leads_count, payments_count,
> revenue.
>
> Считается JOIN-ом на leads и payments.
>
> \"\"\"

6.2 Расширение сервиса users

Файл: backend/app/services/users.py --- добавляются методы
set_first_touch и set_current_link.

> async def set_first_touch(
>
> self, \*, user_id, bot_id, product_id=None, tracking_link=None
>
> ):
>
> fields = {\"first_bot_id\": bot_id}
>
> if product_id is not None:
>
> fields\[\"first_product_id\"\] = product_id
>
> if tracking_link is not None:
>
> fields.update({
>
> \"first_tracking_link_id\": tracking_link.id,
>
> \"first_utm_source\": tracking_link.utm_source,
>
> \"first_utm_medium\": tracking_link.utm_medium,
>
> \"first_utm_campaign\": tracking_link.utm_campaign,
>
> })
>
> \# UPDATE users SET \... WHERE id = user_id AND first_bot_id IS NULL
>
> \# (защита от перезаписи если установка уже была)
>
> async def set_current_link(self, user_id: int, tracking_link_id: int):
>
> \# UPDATE users
>
> \# SET current_tracking_link_id = \$1, current_link_set_at = now()
>
> \# WHERE id = \$2

6.3 Расширение сервиса leads

Метод update_status дополняется проставлением таймстампа смены статуса:

> async def update_status(self, lead_id: int, new_status: str, admin_id:
> int):
>
> lead = await self.find_by_id(lead_id)
>
> if not lead:
>
> raise NotFoundError()
>
> timestamp_field = {
>
> \"contacted\": \"contacted_at\",
>
> \"paid\": \"paid_at\",
>
> \"closed\": \"closed_at\",
>
> }.get(new_status)
>
> fields = {\"status\": new_status}
>
> \# Проставляем timestamp только при первом переходе в этот статус
>
> if timestamp_field and getattr(lead, timestamp_field) is None:
>
> fields\[timestamp_field\] = datetime.utcnow()
>
> \# UPDATE leads SET \... WHERE id = lead_id

7\. API-эндпоинты

7.1 CRUD трекинговых ссылок

  -----------------------------------------------------------------------
  **Endpoint**                 **Назначение**
  ---------------------------- ------------------------------------------
  GET /api/tracking-links      Список ссылок с метриками. Параметры:
                               product_id, is_active, limit, offset

  POST /api/tracking-links     Создание ссылки. Если custom_slug не задан
                               --- генерируется автоматически

  GET /api/tracking-links/{id} Детали ссылки + расширенные метрики
                               (динамика по дням за 30/90 дней)

  PATCH                        Обновление: notes, is_active. UTM-поля
  /api/tracking-links/{id}     изменению не подлежат --- для целостности
                               атрибуции

  DELETE                       Soft delete (is_active = false). Hard
  /api/tracking-links/{id}     delete возможен только если у ссылки нет
                               привязанных leads и payments --- иначе 409
  -----------------------------------------------------------------------

Пример POST /api/tracking-links

Request body:

> {
>
> \"product_id\": 3,
>
> \"utm_source\": \"instagram\",
>
> \"utm_medium\": \"reels\",
>
> \"utm_campaign\": \"spring_2026\",
>
> \"utm_content\": null,
>
> \"bot_id\": 1,
>
> \"notes\": \"Тест нового CTA\",
>
> \"custom_slug\": null
>
> }

Response 201 Created:

> {
>
> \"id\": 17,
>
> \"slug\": \"ig5kx2\",
>
> \"url\": \"https://t.me/zazacosmbot?start=ig5kx2\",
>
> \"product\": { \"id\": 3, \"code\": \"yoga12\", \"name\": \"Йога
> курс\" },
>
> \"bot\": { \"id\": 1, \"username\": \"zazacosmbot\" },
>
> \"utm_source\": \"instagram\",
>
> \"utm_medium\": \"reels\",
>
> \"utm_campaign\": \"spring_2026\",
>
> \"is_active\": true,
>
> \"click_count\": 0,
>
> \"unique_users\": 0,
>
> \"created_at\": \"2026-05-22T12:00:00Z\"
>
> }

7.2 Аналитические эндпоинты

GET /api/stats/sources

Агрегированный отчёт по источникам. Параметры: from, to, product_id,
bot_id, group_by (source \| campaign \| link).

Response:

> {
>
> \"rows\": \[
>
> {
>
> \"source\": \"instagram\",
>
> \"medium\": \"reels\",
>
> \"campaign\": \"spring_2026\",
>
> \"clicks\": 1240,
>
> \"unique_users\": 980,
>
> \"leads\": 145,
>
> \"payments\": 38,
>
> \"revenue\": 456000,
>
> \"conv_click_to_lead\": 0.117,
>
> \"conv_lead_to_payment\": 0.262,
>
> \"avg_check\": 12000
>
> }
>
> \],
>
> \"totals\": {
>
> \"clicks\": 1240, \"unique_users\": 980,
>
> \"leads\": 145, \"payments\": 38, \"revenue\": 456000
>
> }
>
> }

GET /api/stats/funnel

Воронка: клики ссылок → /start выполнено → заявка → оплата. Параметры:
from, to, tracking_link_id, product_id, source, bot_id.

> {
>
> \"steps\": \[
>
> { \"name\": \"Клики\", \"count\": 1240, \"drop_pct\": null },
>
> { \"name\": \"/start\", \"count\": 980, \"drop_pct\": 0.21 },
>
> { \"name\": \"Заявка\", \"count\": 145, \"drop_pct\": 0.85 },
>
> { \"name\": \"Оплата\", \"count\": 38, \"drop_pct\": 0.74 }
>
> \]
>
> }

GET /api/stats/products

Продуктовая аналитика --- таблица всех активных продуктов с метриками за
период.

Расширение GET /api/stats/overview

Существующий эндпоинт расширяется новыми блоками: окна 30д и 90д (сейчас
только 7д), топ-3 источника по выручке, sparkline-данные по каждой
метрике (массив значений по дням).

8\. Изменения в админ-панели

8.1 Карточка продукта --- секция «Ссылки и кампании»

В существующую страницу /products/\[id\] добавляется новая секция с
двумя блоками.

Блок «Прямая ссылка»

-   Текстовое поле read-only с URL:
    https://t.me/\<bot\>?start=\<product.code\>

-   Кнопка «Скопировать» --- копирует ссылку в буфер обмена с
    toast-подтверждением.

-   Подсказка: «Используйте эту ссылку для прямого шеринга. Без
    отслеживания источника».

Блок «Трекинговые ссылки»

Таблица всех созданных tracking_links для этого продукта:

  ----------------------------------------------------------------------------------------------------------
  **Slug**   **Источник**   **Кампания**     **Клики**   **Заявки**   **Оплат**   **Выручка** **Действия**
  ---------- -------------- -------------- ----------- ------------ ----------- ------------- --------------
  ig5kx2     instagram      spring_2026          1 240          145          38     456 000 ₽ Копир · QR · ✕

  ----------------------------------------------------------------------------------------------------------

Кнопка «Создать ссылку с источником» сверху таблицы --- открывает
модалку.

8.2 Модалка создания ссылки

  ----------------------------------------------------------------------------------
  **Поле**              **Тип**        **Обязательное**  **Примечание**
  --------------------- ------------- ------------------ ---------------------------
  Источник (utm_source) Combobox              Да         Автодополнение по ранее
                                                         использованным значениям +
                                                         возможность ввести новый.
                                                         Примеры: instagram,
                                                         youtube, tg_chat_marketing

  Канал/способ          Dropdown             Нет         Предустановленные: reels,
  (utm_medium)                                           post, story, story_ads,
                                                         video, email, другое

  Кампания              Text                 Нет         Свободный текст:
  (utm_campaign)                                         spring_2026, black_friday,
                                                         launch_day_1

  Notes                 Textarea             Нет         Внутренняя заметка для себя

  Бот                   Dropdown        Если ботов \>1   Если в системе один
                                                         активный бот --- поле
                                                         скрыто, используется он по
                                                         умолчанию

  Custom slug           Text                 Нет         Скрыто за «Расширенные
  (advanced)                                             настройки». Валидация:
                                                         \[A-Za-z0-9\_-\]{4,64},
                                                         уникальность
  ----------------------------------------------------------------------------------

После нажатия «Сгенерировать»:

-   Модалка показывает финальный URL крупно.

-   Кнопка «Скопировать ссылку» с toast-уведомлением.

-   Кнопка «Скачать QR-код» --- генерирует PNG 512×512 для
    офлайн-материалов.

-   Кнопка «Создать ещё одну» --- сбрасывает форму.

-   Кнопка «Закрыть» --- возврат к карточке продукта; новая ссылка
    появляется в таблице.

8.3 Новая страница /sources --- Источники

Главный отчёт владельца платформы --- отвечает на вопрос «куда заливать
деньги, какие площадки приводят клиентов».

Структура страницы

-   Фильтры сверху: период (Today / 7д / 30д / 90д / Custom), продукт
    (multi-select), бот (если \>1).

-   Переключатель группировки: По источнику / По кампании / По ссылке.

-   Таблица с метриками (см. колонки ниже).

-   Сортировка по любой числовой колонке.

-   Кнопка «Экспорт в CSV».

Колонки таблицы

-   Источник / Кампания / Ссылка (в зависимости от группировки)

-   Клики --- всего кликов по ссылкам этой группы

-   Уник. --- уникальные пользователи (по first_tracking_link_id)

-   Заявки --- leads.tracking_link_id попадает в группу

-   Оплаты --- payments.tracking_link_id попадает в группу

-   Выручка --- sum(payments.amount)

-   Конв. клик → заявка --- leads / clicks

-   Конв. заявка → оплата --- payments / leads

-   Средний чек --- revenue / payments

8.4 Новая страница /funnel --- Воронка

Визуализация полного покупательского пути с дроп-офами на каждом шаге.

Структура

-   Фильтры: период, продукт, источник (combobox по существующим),
    кампания, бот.

-   Визуализация воронки: горизонтальные бары с убывающей шириной, на
    каждом шаге --- абсолютное число и процент от предыдущего шага.

-   Под воронкой --- таблица с детализацией по дням.

Шаги воронки

13. Кликов --- sum click_count по выбранным ссылкам в периоде. (Если
    фильтр по источнику не задан --- суммируются все ссылки.)

14. /start выполнено --- count distinct users по first_seen_at в
    периоде. Дроп = клики, кто не нажал /start.

15. Заявка --- count leads в периоде с соответствующими фильтрами.

16. Оплата --- count payments в периоде.

8.5 Новая страница /products-analytics --- Продуктовая аналитика

Таблица всех активных продуктов с метриками:

-   Название и код продукта

-   Заявок за период

-   Оплат за период

-   Конверсия заявка → оплата

-   Средний чек

-   Выручка

-   Активных подписок сейчас

Разрез по периодам (3 / 6 / 12 мес): какой период продаётся лучше, какой
даёт больший средний чек.

8.6 Расширение главного дашборда

-   KPI-плитки: добавить окна 30д и 90д (сейчас только Total и 7д).

-   Sparkline под каждой KPI-плиткой --- динамика по дням за выбранное
    окно.

-   Блок «Топ-3 источника» по выручке за 30д --- рядом с существующими
    блоками.

-   Блок «Активные подписки сейчас» --- total + истекают в 7д, 14д, 30д.

9\. Бэкфил исторических данных

После применения миграций запускается одноразовый скрипт
backfill_attribution(). Он восстанавливает first-touch атрибуцию
насколько это возможно из имеющихся данных. Для production-запуска ---
выполняется однократно во время деплоя.

> async def backfill_attribution(db):
>
> \# 1. first_product_id --- из самой ранней связи (lead или payment)
>
> await db.execute(\"\"\"
>
> UPDATE users u
>
> SET first_product_id = sub.product_id
>
> FROM (
>
> SELECT user_id, product_id
>
> FROM (
>
> SELECT user_id, product_id, created_at,
>
> ROW_NUMBER() OVER (
>
> PARTITION BY user_id ORDER BY created_at ASC
>
> ) AS rn
>
> FROM (
>
> SELECT user_id, product_id, created_at FROM leads
>
> UNION ALL
>
> SELECT user_id, product_id, created_at FROM payments
>
> ) all_touches
>
> ) ranked
>
> WHERE rn = 1
>
> ) sub
>
> WHERE u.id = sub.user_id AND u.first_product_id IS NULL
>
> \"\"\")
>
> \# 2. first_bot_id --- если бот в системе один активный, проставляем
> его всем
>
> active_bots = await db.fetch(\"SELECT id FROM bots WHERE is_active =
> true\")
>
> if len(active_bots) == 1:
>
> await db.execute(
>
> \"UPDATE users SET first_bot_id = \$1 WHERE first_bot_id IS NULL\",
>
> active_bots\[0\]\[\"id\"\]
>
> )
>
> \# 3. first_utm\_\* остаются NULL --- исторические источники
> неизвестны
>
> \# 4. Таймстампы перехода leads в новые статусы
>
> await db.execute(\"\"\"
>
> UPDATE leads SET contacted_at = created_at
>
> WHERE status IN (\'contacted\', \'paid\', \'closed\') AND contacted_at
> IS NULL
>
> \"\"\")
>
> await db.execute(\"\"\"
>
> UPDATE leads SET paid_at = created_at
>
> WHERE status IN (\'paid\', \'closed\') AND paid_at IS NULL
>
> \"\"\")
>
> await db.execute(\"\"\"
>
> UPDATE leads SET closed_at = created_at
>
> WHERE status = \'closed\' AND closed_at IS NULL
>
> \"\"\")

На текущем состоянии БД (3 user, 2 lead, 1 payment) бэкфил заполнит
first_product_id у одного пользователя (того, у кого есть оплата) и
проставит first_bot_id у всех (поскольку активный бот один).

10\. Фазы реализации

Модуль разделён на четыре фазы для последовательного запуска и контроля
сложности.

Фаза 1 --- Атрибуция и базовый отчёт по источникам

Срок: 3-4 рабочих дня. Это minimum viable analytics --- без него отчёты
не работают.

-   Миграции 001-004

-   Сервис tracking_links + API CRUD

-   Изменения в /start handler: резолвер slug, инкремент счётчиков

-   Сохранение first_touch на users (новых)

-   Сохранение current_link и атрибуция lead

-   Бэкфил исторических данных

-   Frontend: секция «Ссылки и кампании» в карточке продукта +
    модалка-генератор

-   Frontend: страница /sources с базовой таблицей и фильтрами

Результат: можно создавать трекинговые ссылки и видеть приток по
источникам.

Фаза 2 --- Воронка и продуктовая аналитика

Срок: 2-3 рабочих дня.

-   API /api/stats/funnel + UI-страница /funnel

-   API /api/stats/products + UI-страница /products-analytics

-   Расширение KPI-плиток главного дашборда (30д, 90д)

-   Sparkline-графики и топ-источники на главном

Результат: видна полная воронка от клика до оплаты, понятно какие
продукты работают лучше.

Фаза 3 --- Подписки и retention

Срок: 2-3 рабочих дня.

-   UI: страница /subscriptions-analytics --- истекающие, недавно
    истёкшие

-   Расчёт renewal_rate (продлились в течение N дней после expires_at)

-   Опционально: страница /retention с когортной матрицей

Когортная матрица будет давать значимые данные через 2-3 квартала
накопления, но инфраструктуру стоит готовить сейчас.

Фаза 4 --- Events и менеджеры (откладывается до необходимости)

Срок: 3-4 рабочих дня. Запускается когда понадобится считать
micro-conversions (просмотр карточки vs нажатие на заявку) или KPI
менеджеров.

-   Таблица events + сервис emit_event()

-   Логирование событий в ключевых точках бота и backend

-   Воронка дополняется промежуточным шагом «просмотр карточки»

-   При появлении ролей в admins --- admin_id в payments при создании,
    страница /managers с KPI

11\. Тестовые сценарии

Минимальный набор сценариев для приёмки модуля. Каждый запускается на
чистой БД с подготовленными фикстурами.

11.1 Создание ссылки и переход по ней

17. Создать tracking_link в админке для продукта P с
    utm_source=\'test_source\'

18. Скопировать сгенерированный URL

19. Перейти по нему в Telegram с нового аккаунта

20. Проверить: tracking_link.click_count = 1, unique_users = 1

21. Проверить: users.first_utm_source = \'test_source\',
    first_tracking_link_id заполнен

22. Нажать «Оставить заявку»

23. Проверить: leads.tracking_link_id корректный, utm_source =
    \'test_source\'

11.2 TTL контекста ссылки

24. Пользователь приходит по ссылке, current_link_set_at = T

25. Эмулировать прошествие 31 минуты (обновить current_link_set_at назад
    в БД)

26. Пользователь нажимает «Оставить заявку»

27. Проверить: leads.tracking_link_id = NULL (TTL истёк), UTM-поля =
    NULL

11.3 Возврат по другой ссылке

28. Пользователь U1 пришёл по ссылке L1 (instagram)

29. Через час U1 переходит по другой ссылке L2 (youtube)

30. Проверить: users.first_utm_source = \'instagram\' (не изменился)

31. Проверить: users.current_tracking_link_id = L2.id (обновился)

32. U1 оставляет заявку

33. Проверить: lead.tracking_link_id = L2.id, lead.utm_source =
    \'youtube\'

11.4 Деактивация ссылки

34. Tracking_link L переводится в is_active = false

35. Новый пользователь делает /start \<L.slug\>

36. Проверить: ссылка не резолвится, отрабатывает fallback на
    products.code или отображается каталог с уведомлением «Ссылка
    устарела»

37. Существующие leads и payments с tracking_link_id = L.id остаются
    валидными --- атрибуция сохранена

11.5 Коллизия slug с product.code

38. В системе есть продукт с code=\'yoga12\'

39. Попытка создать tracking_link с custom_slug=\'yoga12\'

40. Проверить: API возвращает 409 Conflict, ссылка не создаётся

11.6 Бэкфил

41. Запуск миграции на БД с 3 users, 2 leads, 1 payment

42. Проверить: у пользователя с оплатой first_product_id заполнен (=
    product из payment)

43. Проверить: у всех users first_bot_id = единственный активный бот

44. Проверить: leads.paid_at заполнен для статусов \'paid\' и \'closed\'

12\. Открытые вопросы и решения по умолчанию

12.1 QR-коды

Генерация: на бэкенде через python-qrcode + Pillow. Эндпоинт GET
/api/tracking-links/{id}/qr.png возвращает PNG 512×512. Это
универсальнее, чем JS-генерация в браузере --- можно открыть прямую
ссылку, шарить через мессенджер.

12.2 Кастомные slug

Разрешать пользователю задавать собственный slug при создании (за
«Расширенные настройки» в модалке). Полезно для шеринга («yogasale»
вместо «kx9p3a»), но требует проверки уникальности и формата. Решение
принято: разрешать.

12.3 Атрибуция без TTL

Если пользователь оставил заявку без current_link (TTL истёк или его не
было) --- нужно ли наследовать UTM из users.first_utm\_\*? Решение: нет,
leads остаются с NULL в UTM. Это даёт чистое разделение first-touch (на
user) и last-touch (на lead). В отчётах last-touch разрез будет включать
категорию «органика / нет ссылки».

12.4 Удаление пользователя

На момент написания ТЗ --- функция удаления пользователя в API
отсутствует. При появлении: связанные tracking_link_id остаются у ссылки
(метрики click_count и unique_users уже зафиксированы и не
пересчитываются).

12.5 Events-таблица сейчас или потом

Отложено до Фазы 4. На фазах 1-3 все отчёты строятся поверх таблиц users
/ leads / payments / subscriptions / tracking_links с JOIN-ами. Events
нужны когда захочется считать micro-conversions (просмотр карточки vs
нажатие на заявку) --- это требует логирования внутрибовых действий, что
не выводится из текущих таблиц.

12.6 Атрибуция между разными ботами

Если в системе будет несколько ботов, и пользователь придёт по ссылке к
боту B1, а потом самостоятельно начнёт диалог с ботом B2 --- это разные
user-записи в текущей схеме (один Telegram-пользователь = одна запись
users). При появлении мульти-ботовой логики потребуется решать отдельно:
дедуплицировать users по telegram_user_id или нет.

*--- Конец документа ---*
