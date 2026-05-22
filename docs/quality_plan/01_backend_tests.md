# 01. Backend — стратегия тестирования

## 1.1 Стек

| Инструмент | Версия | Назначение |
|-----------|-------|-----------|
| **pytest** | 8.3+ | Test runner |
| **pytest-asyncio** | 0.24+ | Async-фикстуры и тесты |
| **pytest-cov** | 5.0+ | Coverage report |
| **pytest-xdist** | 3.6+ | Параллельные тесты |
| **httpx** | (уже есть) | AsyncClient для API |
| **pytest-httpx** | 0.32+ | Мокать HTTP-вызовы (Telegram API) |
| **testcontainers-postgres** | 4.7+ | Реальный Postgres в Docker на каждый ран |
| **alembic** | (уже есть) | Применять миграции на тестовую БД |
| **factory-boy** | 3.3+ | Фабрики ORM-объектов |
| **freezegun** | 1.5+ | Замораживать `datetime.now()` |
| **hypothesis** | 6+ | Property-based testing для slug-генератора и валидаторов |
| **mutmut** | 2.5+ | Mutation testing (опционально) |
| **ruff** | 0.7+ | Линт + format |
| **mypy** | 1.13+ | Static type checks |
| **bandit** | 1.7+ | Security scan |

Добавить в `backend/requirements-dev.txt`:

```
pytest==8.3.4
pytest-asyncio==0.24.0
pytest-cov==6.0.0
pytest-xdist==3.6.1
pytest-httpx==0.34.0
testcontainers[postgres]==4.9.0
factory-boy==3.3.1
freezegun==1.5.1
hypothesis==6.122.3
mutmut==2.5.1
ruff==0.8.4
mypy==1.13.0
bandit==1.8.0
```

## 1.2 Структура тестов

```
backend/
├── app/                       # production code
├── tests/
│   ├── conftest.py            # глобальные фикстуры
│   ├── factories.py           # factory-boy для всех моделей
│   ├── unit/
│   │   ├── services/
│   │   │   ├── test_tracking_links.py
│   │   │   ├── test_subscriptions.py
│   │   │   └── test_telegram.py
│   │   ├── bot/
│   │   │   ├── test_handlers_start.py
│   │   │   ├── test_handlers_lead.py
│   │   │   └── test_manager.py
│   │   ├── api/               # тесты роутов с реальной БД
│   │   │   ├── test_auth.py
│   │   │   ├── test_tracking_links.py
│   │   │   ├── test_payments.py
│   │   │   └── test_stats.py
│   │   ├── core/
│   │   │   └── test_security.py
│   │   └── workers/
│   │       └── test_scheduler.py
│   ├── integration/
│   │   ├── test_full_purchase_flow.py
│   │   ├── test_attribution_e2e.py
│   │   └── test_expire_due_cron.py
│   ├── property/              # hypothesis
│   │   └── test_slug_generator.py
│   └── fixtures/
│       └── telegram_responses.py   # JSON-фикстуры ответов TG API
├── pytest.ini
└── pyproject.toml
```

## 1.3 `pytest.ini`

```ini
[pytest]
testpaths = tests
asyncio_mode = auto
addopts =
    -ra
    --strict-markers
    --strict-config
    --cov=app
    --cov-report=term-missing:skip-covered
    --cov-report=html:htmlcov
    --cov-report=xml:coverage.xml
    --cov-branch
    --no-cov-on-fail
markers =
    slow: тесты дольше 1 секунды
    integration: требуют контейнер с БД
    telegram: используют моки Telegram
filterwarnings =
    error
    ignore::DeprecationWarning:aiogram.*
```

## 1.4 Минимальный `conftest.py`

```python
# backend/tests/conftest.py
import asyncio
import os
from pathlib import Path

import pytest
import pytest_asyncio
from alembic.config import Config
from alembic import command
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer


# -------- одна Postgres-контейнер на сессию тестов --------
@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg


@pytest_asyncio.fixture(scope="session")
async def engine(postgres_container):
    raw_url = postgres_container.get_connection_url().replace("postgresql+psycopg2", "postgresql+asyncpg")
    os.environ["DATABASE_URL"] = raw_url
    # Применяем миграции на пустую тестовую БД
    cfg = Config(str(Path(__file__).parent.parent / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", raw_url)
    command.upgrade(cfg, "head")

    from app.db.session import engine as app_engine
    yield app_engine
    await app_engine.dispose()


# -------- свежая сессия с откатом на каждый тест --------
@pytest_asyncio.fixture
async def session(engine):
    """Свежая транзакция, откатывается после теста."""
    async with engine.connect() as conn:
        trans = await conn.begin()
        TestSession = async_sessionmaker(bind=conn, expire_on_commit=False)
        session = TestSession()
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()


# -------- AsyncClient для API-тестов --------
@pytest_asyncio.fixture
async def api_client(engine):
    """httpx AsyncClient против FastAPI ASGI без сети."""
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# -------- JWT-cookie уже залогиненного админа --------
@pytest_asyncio.fixture
async def admin_client(api_client, session):
    """Клиент с куки админа."""
    from app.core.security import hash_password, create_access_token
    from app.models.admin import Admin
    admin = Admin(username="testadmin", password_hash=hash_password("testpass"))
    session.add(admin)
    await session.commit()

    token = create_access_token("testadmin")
    api_client.cookies.set("access_token", token)
    yield api_client


# -------- moked Telegram --------
@pytest.fixture
def mock_telegram(httpx_mock):
    """httpx_mock уже подключён pytest-httpx — перехватывает все исходящие к api.telegram.org."""
    httpx_mock.add_response(
        url__regex=r"https://api\.telegram\.org/bot.+/getMe",
        json={"ok": True, "result": {"id": 12345, "is_bot": True, "username": "testbot", "first_name": "Test"}},
    )
    httpx_mock.add_response(
        url__regex=r"https://api\.telegram\.org/bot.+/createChatInviteLink",
        json={"ok": True, "result": {"invite_link": "https://t.me/+abc123"}},
    )
    httpx_mock.add_response(
        url__regex=r"https://api\.telegram\.org/bot.+/sendMessage",
        json={"ok": True, "result": {"message_id": 1}},
    )
    httpx_mock.add_response(
        url__regex=r"https://api\.telegram\.org/bot.+/banChatMember",
        json={"ok": True, "result": True},
    )
    httpx_mock.add_response(
        url__regex=r"https://api\.telegram\.org/bot.+/unbanChatMember",
        json={"ok": True, "result": True},
    )
    return httpx_mock


# -------- фабрики --------
@pytest.fixture
def factories(session):
    """factories.UserFactory(...) делает INSERT в текущую сессию."""
    from tests.factories import (
        AdminFactory, BotFactory, ChannelFactory, ProductFactory,
        UserFactory, LeadFactory, PaymentFactory, SubscriptionFactory,
        TrackingLinkFactory,
    )
    for f in (AdminFactory, BotFactory, ChannelFactory, ProductFactory,
              UserFactory, LeadFactory, PaymentFactory, SubscriptionFactory,
              TrackingLinkFactory):
        f._meta.sqlalchemy_session = session
    return type("F", (), dict(
        Admin=AdminFactory, Bot=BotFactory, Channel=ChannelFactory,
        Product=ProductFactory, User=UserFactory, Lead=LeadFactory,
        Payment=PaymentFactory, Subscription=SubscriptionFactory,
        TrackingLink=TrackingLinkFactory,
    ))
```

## 1.5 Factory Boy — `tests/factories.py`

```python
import factory
from factory.alchemy import SQLAlchemyModelFactory

from app.models import Admin, Bot, Channel, Product, User, Lead, Payment, Subscription, TrackingLink


class AdminFactory(SQLAlchemyModelFactory):
    class Meta:
        model = Admin
        sqlalchemy_session_persistence = "flush"
    username = factory.Sequence(lambda n: f"admin{n}")
    password_hash = "$2b$12$dummyhash"


class BotFactory(SQLAlchemyModelFactory):
    class Meta:
        model = Bot
        sqlalchemy_session_persistence = "flush"
    token = factory.Sequence(lambda n: f"00000000:tokentokentokentokentokentoken{n}")
    telegram_bot_id = factory.Sequence(lambda n: 10000 + n)
    username = factory.Sequence(lambda n: f"bot{n}")
    title = factory.LazyAttribute(lambda o: f"Bot {o.username}")
    is_active = True


class ChannelFactory(SQLAlchemyModelFactory):
    class Meta:
        model = Channel
        sqlalchemy_session_persistence = "flush"
    telegram_chat_id = factory.Sequence(lambda n: -1000000000000 - n)
    title = factory.Sequence(lambda n: f"Channel {n}")
    bot = factory.SubFactory(BotFactory)


class ProductFactory(SQLAlchemyModelFactory):
    class Meta:
        model = Product
        sqlalchemy_session_persistence = "flush"
    code = factory.Sequence(lambda n: f"product-{n}")
    name = factory.Sequence(lambda n: f"Product {n}")
    description = "test product"
    channel = factory.SubFactory(ChannelFactory)
    price_3m = 1000
    price_6m = 1800
    price_12m = 3000
    currency = "RUB"
    is_active = True


class UserFactory(SQLAlchemyModelFactory):
    class Meta:
        model = User
        sqlalchemy_session_persistence = "flush"
    telegram_user_id = factory.Sequence(lambda n: 100000 + n)
    username = factory.Sequence(lambda n: f"user{n}")
    first_name = "Test"
    last_name = "User"


class LeadFactory(SQLAlchemyModelFactory):
    class Meta:
        model = Lead
        sqlalchemy_session_persistence = "flush"
    user = factory.SubFactory(UserFactory)
    product = factory.SubFactory(ProductFactory)
    status = "new"


class PaymentFactory(SQLAlchemyModelFactory):
    class Meta:
        model = Payment
        sqlalchemy_session_persistence = "flush"
    user = factory.SubFactory(UserFactory)
    product = factory.SubFactory(ProductFactory)
    period_months = 3
    amount = 1000
    currency = "RUB"


class SubscriptionFactory(SQLAlchemyModelFactory):
    class Meta:
        model = Subscription
        sqlalchemy_session_persistence = "flush"
    user = factory.SubFactory(UserFactory)
    channel = factory.SubFactory(ChannelFactory)
    starts_at = factory.LazyFunction(lambda: __import__("datetime").datetime.now(tz=__import__("datetime").timezone.utc))
    ends_at = factory.LazyAttribute(lambda o: o.starts_at + __import__("datetime").timedelta(days=90))
    status = "active"


class TrackingLinkFactory(SQLAlchemyModelFactory):
    class Meta:
        model = TrackingLink
        sqlalchemy_session_persistence = "flush"
    slug = factory.Sequence(lambda n: f"slug{n:04d}")
    product = factory.SubFactory(ProductFactory)
    utm_source = "instagram"
    utm_medium = "reels"
    utm_campaign = "test"
    is_active = True
```

## 1.6 Примеры тестов по слоям

### 1.6.1 Service unit — TrackingLinksService.create

```python
# tests/unit/services/test_tracking_links.py
import pytest
from app.services.tracking_links import (
    TrackingLinksService, ConflictError, InvalidSlugError, GenerationError,
)


@pytest.mark.asyncio
async def test_create_with_custom_slug_succeeds(session, factories):
    product = factories.Product()
    await session.flush()
    svc = TrackingLinksService(session)
    link = await svc.create(
        product_id=product.id,
        utm_source="instagram",
        custom_slug="mycustomslug",
    )
    assert link.slug == "mycustomslug"
    assert link.utm_source == "instagram"
    assert link.is_active is True
    assert link.click_count == 0


@pytest.mark.asyncio
async def test_create_autogen_slug_length_8(session, factories):
    product = factories.Product()
    await session.flush()
    svc = TrackingLinksService(session)
    link = await svc.create(product_id=product.id, utm_source="ig")
    assert len(link.slug) == 8
    assert link.slug.isalnum()


@pytest.mark.asyncio
async def test_create_with_invalid_slug_raises(session, factories):
    product = factories.Product()
    await session.flush()
    svc = TrackingLinksService(session)
    with pytest.raises(InvalidSlugError):
        await svc.create(product_id=product.id, utm_source="ig", custom_slug="ab")  # <4 chars


@pytest.mark.asyncio
async def test_slug_collision_with_existing_link(session, factories):
    factories.TrackingLink(slug="taken123")
    product = factories.Product()
    await session.flush()
    svc = TrackingLinksService(session)
    with pytest.raises(ConflictError, match="already taken"):
        await svc.create(product_id=product.id, utm_source="ig", custom_slug="taken123")


@pytest.mark.asyncio
async def test_slug_collision_with_product_code(session, factories):
    factories.Product(code="yoga12")
    product2 = factories.Product()
    await session.flush()
    svc = TrackingLinksService(session)
    with pytest.raises(ConflictError, match="conflicts with"):
        await svc.create(product_id=product2.id, utm_source="ig", custom_slug="yoga12")


@pytest.mark.asyncio
async def test_increment_click_count_is_atomic(session, factories):
    link = factories.TrackingLink()
    await session.flush()
    svc = TrackingLinksService(session)
    await svc.increment_click_count(link.id)
    await svc.increment_click_count(link.id)
    await session.refresh(link)
    assert link.click_count == 2
```

### 1.6.2 Service integration — grant_for_payment

```python
# tests/unit/services/test_subscriptions.py
import pytest
from datetime import datetime, timedelta, timezone
from freezegun import freeze_time

from app.services.subscriptions import grant_for_payment


@pytest.mark.asyncio
@freeze_time("2026-05-22 12:00:00")
async def test_grant_creates_subscription_with_correct_ends_at(session, factories, mock_telegram, monkeypatch):
    # Подменяем bot_manager.get_aiogram_bot → возвращает мок
    from app.bot import manager as bot_manager
    from unittest.mock import AsyncMock, MagicMock
    fake_bot = MagicMock()
    fake_bot.create_chat_invite_link = AsyncMock(return_value=MagicMock(invite_link="https://t.me/+abc"))
    fake_bot.send_message = AsyncMock()
    monkeypatch.setattr(bot_manager, "get_aiogram_bot", lambda _: fake_bot)

    payment = factories.Payment(period_months=3)
    await session.flush()

    sub = await grant_for_payment(session, payment)
    assert sub.status == "active"
    assert sub.starts_at == datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    # 3 календарных месяца
    assert sub.ends_at == datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)
    assert sub.invite_link == "https://t.me/+abc"
    fake_bot.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_grant_extends_existing_active_subscription(session, factories, monkeypatch):
    # ... продление работает: ends_at += 3 месяца, новый payment_id
```

### 1.6.3 API integration — POST /api/payments

```python
# tests/unit/api/test_payments.py
import pytest


@pytest.mark.asyncio
async def test_create_payment_requires_auth(api_client):
    r = await api_client.post("/api/payments", json={"user_id": 1, "product_id": 1, "period_months": 3})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_create_payment_rejects_inactive_bot(admin_client, session, factories, monkeypatch):
    user = factories.User()
    product = factories.Product()
    await session.commit()
    # Бот не запущен в manager → 409
    from app.bot import manager
    monkeypatch.setattr(manager, "get_aiogram_bot", lambda _: None)
    r = await admin_client.post("/api/payments", json={
        "user_id": user.id, "product_id": product.id, "period_months": 3,
    })
    assert r.status_code == 409
    assert "неактивен" in r.json()["detail"]


@pytest.mark.asyncio
async def test_create_payment_sets_admin_id_and_tracking_link(admin_client, session, factories, monkeypatch):
    user = factories.User()
    product = factories.Product()
    link = factories.TrackingLink(product=product)
    # Создаём lead с трекингом
    lead = factories.Lead(user=user, product=product, tracking_link_id=link.id, utm_source="ig")
    await session.commit()

    monkeypatch.setattr("app.bot.manager.get_aiogram_bot", lambda _: __fake_bot())

    r = await admin_client.post("/api/payments", json={
        "user_id": user.id, "product_id": product.id, "period_months": 3,
    })
    assert r.status_code == 201

    # Проверяем что payment получил admin_id и tracking_link_id наследовался от lead
    pid = r.json()["id"]
    payment = await session.get(Payment, pid)
    assert payment.admin_id is not None
    assert payment.tracking_link_id == link.id
```

### 1.6.4 Bot handlers test

```python
# tests/unit/bot/test_handlers_start.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import Message, User as TgUser

from app.bot.handlers import start_with_arg


@pytest.mark.asyncio
async def test_start_with_slug_resolves_to_tracking_link(session, factories):
    link = factories.TrackingLink(slug="mySlug12", utm_source="instagram")
    await session.commit()

    msg = _make_message(tg_id=999, text="/start mySlug12")
    cmd = _make_command(args="mySlug12")
    fake_bot = _make_aiogram_bot(bot_id=link.product.channel.bot.telegram_bot_id)

    await start_with_arg(msg, cmd, fake_bot)

    # Проверяем что click_count инкрементнут
    await session.refresh(link)
    assert link.click_count == 1
    # Проверяем что user создан с first-touch
    from app.models import User
    user = (await session.execute(select(User).where(User.telegram_user_id == 999))).scalar_one()
    assert user.first_utm_source == "instagram"
    assert user.first_tracking_link_id == link.id


@pytest.mark.asyncio
async def test_start_with_invalid_slug_falls_back_to_catalog(session, factories):
    msg = _make_message(tg_id=999, text="/start nosuchslug")
    cmd = _make_command(args="nosuchslug")
    fake_bot = _make_aiogram_bot()
    await start_with_arg(msg, cmd, fake_bot)
    msg.answer.assert_any_call(__contains_text="устарела или недоступна")


# helpers
def _make_message(tg_id, text):
    msg = MagicMock(spec=Message)
    msg.from_user = TgUser(id=tg_id, is_bot=False, first_name="Test")
    msg.text = text
    msg.answer = AsyncMock()
    return msg
```

### 1.6.5 Property-based — slug generator

```python
# tests/property/test_slug_generator.py
from hypothesis import given, strategies as st
from app.services.tracking_links import SLUG_PATTERN


@given(st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-", min_size=4, max_size=64))
def test_valid_slugs_pass_regex(slug):
    assert SLUG_PATTERN.match(slug) is not None


@given(st.text(alphabet=" !@#$%^&*()", min_size=4, max_size=64))
def test_invalid_chars_rejected(slug):
    assert SLUG_PATTERN.match(slug) is None
```

## 1.7 Coverage policy

В `pyproject.toml`:

```toml
[tool.coverage.run]
source = ["app"]
omit = [
    "app/main.py",                   # boot-код, не нуждается в тестах
    "app/alembic/*",                 # миграции отдельно
    "*/__init__.py",
]
branch = true

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
    "if __name__ == .__main__.:",
]
fail_under = 98
precision = 2
```

CI блокирует merge, если coverage упал ниже 98%.

## 1.8 Что нельзя/сложно покрыть и что делать

| Кейс | Решение |
|------|---------|
| `bot/manager.py` polling — бесконечный цикл | Запускать на 100ms через `asyncio.wait_for`, проверять что задача в `_runners` |
| `workers/scheduler.py` — APScheduler с реальным временем | freezegun + ручной trigger: `await sch.run_job(...)`|
| `services/telegram.py` — реальные TG ошибки 429/500 | pytest-httpx `httpx_mock.add_response(status_code=429)` |
| Race conditions | hypothesis stateful tests или конкретный сценарий с asyncio.gather |
| Тяжёлые миграции | Тесты на pre/post-conditions через `alembic upgrade head` + проверка `SELECT * FROM information_schema.columns` |

## 1.9 Запуск тестов

```bash
# Все
pytest

# С координатором — параллельно по 4 ядрам
pytest -n 4

# Только unit
pytest tests/unit -m "not slow"

# Только integration
pytest tests/integration

# С покрытием и html-отчётом
pytest --cov-report=html
open htmlcov/index.html

# Конкретный файл
pytest tests/unit/services/test_subscriptions.py -v

# Только тесты с «grant» в имени
pytest -k grant -v

# Mutation testing на критичный модуль
mutmut run --paths-to-mutate app/services/subscriptions.py
mutmut results
```

## 1.10 Чек-лист внедрения backend-тестов

- [ ] Установить `requirements-dev.txt`
- [ ] Создать `tests/`, `pytest.ini`, `pyproject.toml`
- [ ] Написать `conftest.py` с фикстурами (engine, session, api_client, admin_client, factories)
- [ ] Написать `factories.py` (все 9 моделей)
- [ ] Покрыть `services/tracking_links.py` → target 100%
- [ ] Покрыть `services/subscriptions.py` → target 100%
- [ ] Покрыть `services/telegram.py` → target 95% (некоторые TG-ответы трудно мокать)
- [ ] Покрыть `bot/handlers.py` → target 95%
- [ ] Покрыть `bot/manager.py` → target 80% (polling сложно тестировать целиком)
- [ ] Покрыть `api/*` → target 100% (каждый эндпоинт + auth case + 4xx-ветки)
- [ ] Покрыть `core/security.py` → target 100%
- [ ] Покрыть `workers/scheduler.py` → target 90%
- [ ] Property-based для slug-генератора и валидаторов
- [ ] Integration `full_purchase_flow`: создать продукт → ссылка → /start → /lead → /payment → check subscription + invite
- [ ] Integration `expire_due_cron`: создать активную подписку → freeze в будущее → run job → expired + kick
- [ ] Достичь 98% overall + ноль warnings от ruff/mypy
