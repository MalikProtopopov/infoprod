# Phase 1 — Атрибуция и базовый отчёт по источникам

**Срок**: 3–4 рабочих дня. Без этой фазы остальное не работает.

**Результат**: можно создавать трекинговые ссылки, видеть в админке таблицу `«Источники»` с метриками `clicks / unique / leads / payments / revenue` и базовыми конверсиями.

---

## Шаг 1.1 — Миграции БД (Alembic)

Создать 4 alembic revision'а в `backend/alembic/versions/`. Применять одной командой `alembic upgrade head` после деплоя.

### Миграция 001 — таблица `tracking_links`

Файл: `20260523_0010_tracking_links.py`

```sql
CREATE TABLE tracking_links (
  id            bigserial PRIMARY KEY,
  slug          text NOT NULL UNIQUE,
  product_id    bigint NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  bot_id        bigint NULL REFERENCES bots(id) ON DELETE SET NULL,
  utm_source    text NOT NULL,
  utm_medium    text NULL,
  utm_campaign  text NULL,
  utm_content   text NULL,
  notes         text NULL,
  is_active     boolean NOT NULL DEFAULT true,
  click_count   int NOT NULL DEFAULT 0,
  unique_users  int NOT NULL DEFAULT 0,
  created_by    bigint NULL REFERENCES admins(id) ON DELETE SET NULL,
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_tracking_links_product ON tracking_links(product_id);
CREATE INDEX idx_tracking_links_active  ON tracking_links(is_active, created_at DESC);
CREATE INDEX idx_tracking_links_source  ON tracking_links(utm_source);

ALTER TABLE tracking_links
  ADD CONSTRAINT slug_valid_format
  CHECK (slug ~ '^[A-Za-z0-9_-]{4,64}$');
```

### Миграция 002 — first-touch на `users`

Файл: `20260523_0020_users_first_touch.py`

```sql
ALTER TABLE users
  ADD COLUMN first_product_id          bigint NULL REFERENCES products(id) ON DELETE SET NULL,
  ADD COLUMN first_tracking_link_id    bigint NULL REFERENCES tracking_links(id) ON DELETE SET NULL,
  ADD COLUMN first_utm_source          text NULL,
  ADD COLUMN first_utm_medium          text NULL,
  ADD COLUMN first_utm_campaign        text NULL,
  ADD COLUMN first_bot_id              bigint NULL REFERENCES bots(id) ON DELETE SET NULL,
  ADD COLUMN current_tracking_link_id  bigint NULL REFERENCES tracking_links(id) ON DELETE SET NULL,
  ADD COLUMN current_link_set_at       timestamptz NULL;

CREATE INDEX idx_users_first_source  ON users(first_utm_source) WHERE first_utm_source IS NOT NULL;
CREATE INDEX idx_users_first_product ON users(first_product_id) WHERE first_product_id IS NOT NULL;
CREATE INDEX idx_users_first_seen    ON users(first_seen_at DESC);
```

### Миграция 003 — last-touch + status-timestamps на `leads`

Файл: `20260523_0030_leads_attribution.py`

```sql
ALTER TABLE leads
  ADD COLUMN tracking_link_id  bigint NULL REFERENCES tracking_links(id) ON DELETE SET NULL,
  ADD COLUMN utm_source        text NULL,
  ADD COLUMN utm_medium        text NULL,
  ADD COLUMN utm_campaign      text NULL,
  ADD COLUMN contacted_at      timestamptz NULL,
  ADD COLUMN paid_at           timestamptz NULL,
  ADD COLUMN closed_at         timestamptz NULL;

CREATE INDEX idx_leads_tracking_link ON leads(tracking_link_id) WHERE tracking_link_id IS NOT NULL;
CREATE INDEX idx_leads_status_created ON leads(status, created_at DESC);
CREATE INDEX idx_leads_source ON leads(utm_source) WHERE utm_source IS NOT NULL;
```

### Миграция 004 — атрибуция на `payments`

Файл: `20260523_0040_payments_attribution.py`

```sql
ALTER TABLE payments
  ADD COLUMN admin_id          bigint NULL REFERENCES admins(id) ON DELETE SET NULL,
  ADD COLUMN tracking_link_id  bigint NULL REFERENCES tracking_links(id) ON DELETE SET NULL;

CREATE INDEX idx_payments_admin         ON payments(admin_id)         WHERE admin_id IS NOT NULL;
CREATE INDEX idx_payments_tracking_link ON payments(tracking_link_id) WHERE tracking_link_id IS NOT NULL;
CREATE INDEX idx_payments_created       ON payments(created_at DESC);
```

**Acceptance:**
- `alembic upgrade head` проходит без ошибок.
- `\d tracking_links` показывает все колонки и индексы.
- `\d users`, `\d leads`, `\d payments` показывают новые колонки.

---

## Шаг 1.2 — SQLAlchemy-модели

### Новая модель `TrackingLink`

Файл: `backend/app/models/tracking_link.py`

```python
class TrackingLink(Base):
    __tablename__ = "tracking_links"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    bot_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("bots.id", ondelete="SET NULL"), nullable=True)
    utm_source: Mapped[str] = mapped_column(String(255), nullable=False)
    utm_medium: Mapped[str | None] = mapped_column(String(255), nullable=True)
    utm_campaign: Mapped[str | None] = mapped_column(String(255), nullable=True)
    utm_content: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    click_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unique_users: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("admins.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

### Расширения существующих моделей

В `User`:
```python
first_product_id, first_tracking_link_id, first_utm_source, first_utm_medium,
first_utm_campaign, first_bot_id, current_tracking_link_id, current_link_set_at
```

В `Lead`:
```python
tracking_link_id, utm_source, utm_medium, utm_campaign, contacted_at, paid_at, closed_at
```

В `Payment`:
```python
admin_id, tracking_link_id
```

Обязательно зарегистрировать модель в `app/models/__init__.py`.

---

## Шаг 1.3 — Сервис `tracking_links`

Файл: `backend/app/services/tracking_links.py`

```python
SLUG_CHARS = string.ascii_letters + string.digits   # 62 символа
SLUG_LENGTH = 8

class TrackingLinksService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ---- public ----
    async def create(self, *, product_id, utm_source, utm_medium=None,
                     utm_campaign=None, utm_content=None, bot_id=None,
                     notes=None, custom_slug=None, created_by=None) -> TrackingLink:
        slug = custom_slug or await self._generate_unique_slug()
        await self._validate_slug(slug)
        if await self._slug_exists(slug):
            raise ConflictError("Slug already taken")
        if await self._conflicts_with_product_code(slug):
            raise ConflictError("Slug conflicts with existing product.code")
        # INSERT, return
        ...

    async def find_by_slug(self, slug: str) -> TrackingLink | None: ...
    async def find_by_id(self, link_id: int) -> TrackingLink | None: ...

    async def increment_click_count(self, link_id: int) -> None: ...
    async def increment_unique_users(self, link_id: int) -> None: ...

    async def deactivate(self, link_id: int) -> None: ...
    async def list_for_product(self, product_id: int) -> list[TrackingLink]: ...
    async def list_all(self, *, is_active: bool | None = None,
                       limit: int = 100, offset: int = 0) -> list[TrackingLink]: ...

    async def get_metrics(self, link_id: int) -> dict:
        """clicks, unique_users, leads_count, payments_count, revenue"""
        ...

    # ---- helpers ----
    async def _generate_unique_slug(self, max_attempts=10) -> str:
        for _ in range(max_attempts):
            slug = "".join(secrets.choice(SLUG_CHARS) for _ in range(SLUG_LENGTH))
            if not await self._slug_exists(slug) and not await self._conflicts_with_product_code(slug):
                return slug
        raise GenerationError("Could not generate unique slug after 10 attempts")

    async def _slug_exists(self, slug: str) -> bool: ...
    async def _conflicts_with_product_code(self, slug: str) -> bool: ...
    async def _validate_slug(self, slug: str) -> None:
        if not re.match(r"^[A-Za-z0-9_-]{4,64}$", slug):
            raise ValueError("Invalid slug format")
```

**Также добавить валидацию обратной коллизии в `services/products.py`** — при создании/изменении `product.code` проверить `tracking_links.slug`.

---

## Шаг 1.4 — Расширение сервиса `users`

В `backend/app/services/users.py` (или прямо в bot handlers, если сервиса нет) добавить:

```python
async def set_first_touch(session, *, user_id, bot_id, product_id=None, tracking_link=None):
    """Идемпотентно проставляет first-touch. Защищён условием WHERE first_bot_id IS NULL."""
    fields = {"first_bot_id": bot_id}
    if product_id is not None:
        fields["first_product_id"] = product_id
    if tracking_link is not None:
        fields.update({
            "first_tracking_link_id": tracking_link.id,
            "first_utm_source":   tracking_link.utm_source,
            "first_utm_medium":   tracking_link.utm_medium,
            "first_utm_campaign": tracking_link.utm_campaign,
        })
    await session.execute(
        update(User).where(User.id == user_id, User.first_bot_id.is_(None)).values(**fields)
    )

async def set_current_link(session, user_id: int, tracking_link_id: int):
    await session.execute(
        update(User)
        .where(User.id == user_id)
        .values(current_tracking_link_id=tracking_link_id, current_link_set_at=datetime.now(timezone.utc))
    )
```

---

## Шаг 1.5 — Обновлённый бот-хендлер `/start`

Файл: `backend/app/bot/handlers.py` — переписать `start_with_code` и/или объединить с `start_plain`.

```python
@router.message(CommandStart(deep_link=True))
async def start_with_arg(message: Message, command: CommandObject):
    arg = (command.args or "").strip()
    bot_id = await _resolve_bot_id_from_context(message.bot)

    async with SessionLocal() as session:
        tl_service = TrackingLinksService(session)

        tracking_link = None
        product = None

        # Шаг 1: резолв slug (приоритет) → product.code (fallback)
        if arg:
            tracking_link = await tl_service.find_by_slug(arg)
            if tracking_link and tracking_link.is_active:
                product = await session.get(Product, tracking_link.product_id)
                await tl_service.increment_click_count(tracking_link.id)
            else:
                tracking_link = None
                product = (await session.execute(
                    select(Product).where(Product.code == arg, Product.is_active.is_(True))
                )).scalar_one_or_none()

        # Шаг 2: upsert user
        user, is_new = await _upsert_user(session, message)

        # Шаг 3: first-touch (только если user новый)
        if is_new:
            await set_first_touch(
                session,
                user_id=user.id, bot_id=bot_id,
                product_id=product.id if product else None,
                tracking_link=tracking_link,
            )
            if tracking_link:
                await tl_service.increment_unique_users(tracking_link.id)

        # Шаг 4: current_link с TTL-маркером
        if tracking_link:
            await set_current_link(session, user.id, tracking_link.id)

        await session.commit()

    # Шаг 5: показать карточку или каталог
    if product:
        await _show_product_card(message, product)
    else:
        if arg:
            await message.answer(LINK_EXPIRED_OR_INVALID)
        await _show_catalog(message)
```

**Также в `_upsert_user`** — вернуть кортеж `(user, is_new: bool)`. Сейчас возвращается только user — добавить флаг.

### Обработчик `«Оставить заявку»`

```python
@router.callback_query(F.data.startswith("lead:"))
async def cb_lead(callback: CallbackQuery):
    product_id = int(callback.data.split(":", 1)[1])
    async with SessionLocal() as session:
        user = (await session.execute(
            select(User).where(User.telegram_user_id == callback.from_user.id)
        )).scalar_one_or_none()
        if not user:
            await callback.answer("Сессия истекла, нажмите /start")
            return

        # TTL 30 минут
        tracking_link = None
        if user.current_tracking_link_id and user.current_link_set_at:
            age = (datetime.now(timezone.utc) - user.current_link_set_at).total_seconds()
            if age < 30 * 60:
                tracking_link = await session.get(TrackingLink, user.current_tracking_link_id)

        lead = Lead(
            user_id=user.id,
            product_id=product_id,
            tracking_link_id=tracking_link.id if tracking_link else None,
            utm_source=tracking_link.utm_source if tracking_link else None,
            utm_medium=tracking_link.utm_medium if tracking_link else None,
            utm_campaign=tracking_link.utm_campaign if tracking_link else None,
        )
        session.add(lead)
        await session.commit()

    await callback.message.answer(LEAD_SENT)
    await callback.answer()
```

### Новый текст

В `texts.py`:
```python
LINK_EXPIRED_OR_INVALID = "Эта ссылка устарела или недоступна. Посмотрите наш каталог ниже."
```

---

## Шаг 1.6 — API: CRUD `/api/tracking-links`

Файл: `backend/app/api/tracking_links.py` + регистрация в `app/main.py`.

| Метод | Путь | Назначение |
|------|------|------------|
| GET | `/api/tracking-links` | список с метриками. Query: `product_id?`, `is_active?`, `limit`, `offset` |
| POST | `/api/tracking-links` | создание; если `custom_slug` не задан — генерируется |
| GET | `/api/tracking-links/{id}` | детали + метрики (с разбивкой по дням за 30/90 дней) |
| PATCH | `/api/tracking-links/{id}` | только `notes`, `is_active`. UTM-поля менять нельзя |
| DELETE | `/api/tracking-links/{id}` | soft-delete (`is_active=false`). Hard только если нет leads/payments — иначе 409 |
| GET | `/api/tracking-links/{id}/qr.png` | возвращает PNG 512×512 |

### Pydantic-схемы (`schemas/tracking_link.py`)

```python
class TrackingLinkCreate(BaseModel):
    product_id: int
    utm_source: str = Field(min_length=1, max_length=255)
    utm_medium: str | None = None
    utm_campaign: str | None = None
    utm_content: str | None = None
    bot_id: int | None = None
    notes: str | None = None
    custom_slug: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{4,64}$")

class TrackingLinkUpdate(BaseModel):
    notes: str | None = None
    is_active: bool | None = None

class TrackingLinkOut(BaseModel):
    id: int
    slug: str
    url: str
    product: dict  # {id, code, name}
    bot: dict | None
    utm_source: str
    utm_medium: str | None
    utm_campaign: str | None
    utm_content: str | None
    notes: str | None
    is_active: bool
    click_count: int
    unique_users: int
    created_at: datetime
    # рассчитываемые поля
    leads_count: int = 0
    payments_count: int = 0
    revenue: str = "0"  # Decimal как строка для JSON
```

### Пример успешного POST
Request:
```json
{
  "product_id": 3,
  "utm_source": "instagram",
  "utm_medium": "reels",
  "utm_campaign": "spring_2026"
}
```
Response 201:
```json
{
  "id": 17,
  "slug": "ig5kx2A1",
  "url": "https://t.me/zazacosmbot?start=ig5kx2A1",
  "product": {"id": 3, "code": "yoga12", "name": "Йога курс"},
  "utm_source": "instagram",
  "utm_medium": "reels",
  "utm_campaign": "spring_2026",
  "is_active": true,
  "click_count": 0,
  "unique_users": 0,
  ...
}
```

### QR-код

```python
# requirements.txt: добавить qrcode[pil]==7.4.2
import qrcode
from io import BytesIO

@router.get("/{link_id}/qr.png", response_class=Response)
async def qr_png(link_id: int, session=Depends(get_session)):
    link = await session.get(TrackingLink, link_id)
    if not link:
        raise HTTPException(404)
    # url нужно собрать из bot.username
    bot = await session.get(BotModel, link.bot_id) if link.bot_id else None
    bot_username = bot.username if bot else "_"
    url = f"https://t.me/{bot_username}?start={link.slug}"
    img = qrcode.make(url, box_size=10, border=2)
    buf = BytesIO(); img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")
```

---

## Шаг 1.7 — API: `/api/stats/sources`

Файл: расширить существующий `backend/app/api/stats.py`.

**Параметры**: `from`, `to` (ISO datetime), `product_id?`, `bot_id?`, `group_by` (`source` | `campaign` | `link`).

**Запрос (SQL-логика)**: JOIN на `tracking_links`, `leads`, `payments`. Группируем по выбранному измерению, суммируем clicks, считаем distinct users (по `first_tracking_link_id`), считаем leads, payments, sum(amount).

**Ответ** — см. ТЗ §7.2.

Конверсии:
- `conv_click_to_lead = leads / clicks` (защита от 0)
- `conv_lead_to_payment = payments / leads`
- `avg_check = revenue / payments`

Параллельно собираем `totals` блок.

---

## Шаг 1.8 — Frontend: секция «Ссылки и кампании» в карточке продукта

В `admin/app/(dash)/products/page.tsx` (или новой `[id]/page.tsx`) добавить таб/секцию.

### Блок «Прямая ссылка»
- Read-only input с `https://t.me/<bot>?start=<product.code>`
- Кнопка «Скопировать» с toast
- Подсказка «Без отслеживания источника»

### Блок «Трекинговые ссылки»

Таблица:
| Slug | Источник | Кампания | Клики | Заявки | Оплат | Выручка | Действия |

Действия: «Копировать URL» / «QR» (открыть `/api/tracking-links/{id}/qr.png`) / «Деактивировать»

Кнопка `«+ Создать ссылку с источником»` → открывает **Sheet** (drawer справа, у нас уже есть компонент).

### Sheet «Новая ссылка»

| Поле | Тип |
|------|-----|
| Источник (utm_source) | combobox с автодополнением из существующих |
| Канал/способ (utm_medium) | dropdown (`reels`, `post`, `story`, `story_ads`, `video`, `email`, `другое`) |
| Кампания (utm_campaign) | text |
| Notes | textarea |
| Бот | dropdown (если ботов >1; иначе скрыт) |
| Custom slug | text — за «Расширенные настройки» |

После создания: показать финальный URL крупно, кнопки «Скопировать» / «QR» / «Создать ещё» / «Закрыть».

---

## Шаг 1.9 — Frontend: страница `/sources`

Новый раздел в навигации (после «Обзор» или перед «Заявки»).

**Структура**:
- Фильтры: период (`today / 7д / 30д / 90д / custom`), продукт (multi-select), бот (если >1)
- Toggle группировки: `по источнику / по кампании / по ссылке`
- Таблица (см. колонки в ТЗ §8.3)
- Сортировка по любой колонке (click handler в headers)
- Кнопка «Экспорт CSV» (server-side `Content-Type: text/csv`)

**Использует**: SWR на `/api/stats/sources?from=&to=&group_by=&product_id=&bot_id=`.

---

## Чек-лист Phase 1

- [ ] Миграция 001 — `tracking_links`
- [ ] Миграция 002 — first-touch на `users`
- [ ] Миграция 003 — last-touch + timestamps на `leads`
- [ ] Миграция 004 — `admin_id`, `tracking_link_id` на `payments`
- [ ] SQLAlchemy-модель `TrackingLink`
- [ ] Расширение моделей `User`, `Lead`, `Payment`
- [ ] Сервис `TrackingLinksService` с slug-генератором и валидаторами коллизий
- [ ] Расширение `_upsert_user` (возврат `is_new`)
- [ ] Функции `set_first_touch`, `set_current_link`
- [ ] Обновлённый бот-хендлер `start_with_arg` (slug→product.code приоритет)
- [ ] Обновлённый хендлер `cb_lead` (TTL 30 мин)
- [ ] Текст `LINK_EXPIRED_OR_INVALID`
- [ ] Валидация коллизии product.code ↔ tracking_link.slug на стороне products API
- [ ] CRUD `/api/tracking-links`
- [ ] Эндпоинт QR-кода
- [ ] `/api/stats/sources` с фильтрами и группировкой
- [ ] Frontend: секция в карточке продукта + Sheet-генератор
- [ ] Frontend: страница `/sources`
- [ ] Бэкфил (см. `05_backfill.md`)
- [ ] Acceptance-тесты (см. `06_testing.md`)
- [ ] Деплой через `docker compose build && up -d`
