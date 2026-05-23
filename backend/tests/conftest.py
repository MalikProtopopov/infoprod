"""Глобальные фикстуры pytest для backend-тестов.

Архитектура:
- `postgres_container` — один Postgres-контейнер на весь test session
- `engine` — async-движок, на нём применяется alembic upgrade head один раз
- `session` — каждая тестовая функция получает свежую транзакцию + rollback в конце
- `api_client` — httpx AsyncClient против FastAPI ASGI без сети
- `admin_client` — то же что api_client, но с авторизованной кукой админа
- `factories` — namespace с factory-boy фабриками для всех моделей
"""
from __future__ import annotations

# ВАЖНО: установить EventLoopPolicy ДО любых импортов, которые могут подтянуть uvloop.
# uvicorn[standard] и его зависимости ставят свою policy при импорте, что ломает pytest-asyncio.
import asyncio

asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())

import os
from pathlib import Path
from typing import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.postgres import PostgresContainer


# Гарантируем, что приложение не пытается стартовать на production-БД во время тестов
os.environ.setdefault("JWT_SECRET", "test-secret-32-chars-aaaaaaaaaaaaaaaa")
os.environ.setdefault("ADMIN_PASSWORD", "testpass")
os.environ.setdefault("ENV", "test")
os.environ.setdefault("SENTRY_DSN", "")  # выключаем Sentry в тестах


# ---------- session-level: один Postgres контейнер ----------
@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    """Запускает Postgres 16 в Docker. Доступен всем тестам сессии."""
    container = PostgresContainer("postgres:16-alpine")
    container.start()
    try:
        yield container
    finally:
        container.stop()


@pytest.fixture(scope="session")
def _db_url(postgres_container: PostgresContainer) -> str:
    url = postgres_container.get_connection_url().replace(
        "postgresql+psycopg2", "postgresql+asyncpg"
    )
    os.environ["DATABASE_URL"] = url
    return url


@pytest_asyncio.fixture
async def engine(_db_url: str) -> AsyncIterator[AsyncEngine]:
    """Async-движок на каждый тест.

    Postgres контейнер session-scope, но движок создаётся в текущем event-loop'е
    функции — иначе asyncpg падает с «Future attached to a different loop».
    create_all идемпотентен.
    """
    eng = create_async_engine(_db_url, poolclass=NullPool, future=True)

    from app.db.base import Base
    from app import models  # noqa: F401  triggers model registration

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    try:
        yield eng
    finally:
        await eng.dispose()


# ---------- per-test: чистая сессия с откатом ----------
@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Свежая сессия — каждый тест откатывает.

    Используем SAVEPOINT через nested-транзакцию: SQLAlchemy откатит всё что
    тест успел сделать. БД остаётся чистой между тестами.
    """
    connection = await engine.connect()
    trans = await connection.begin()
    TestSession = async_sessionmaker(bind=connection, expire_on_commit=False, class_=AsyncSession)
    test_session = TestSession()
    try:
        yield test_session
    finally:
        await test_session.close()
        await trans.rollback()
        await connection.close()


# ---------- API client ----------
@pytest_asyncio.fixture
async def api_client(engine: AsyncEngine):
    """httpx AsyncClient против FastAPI без реальной сети.

    Подменяет `get_session` из deps на тестовую сессию.
    """
    from httpx import ASGITransport, AsyncClient

    # Импортируем app здесь, чтобы избежать ленивых импортов при сборе тестов
    from app.api.deps import get_session
    from app.main import app

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        # Каждый запрос — своя сессия со своей транзакцией.
        # На fixture-level rollback не используем, потому что HTTP-запросы
        # коммитят в БД. Тесты сами должны чистить созданные данные либо
        # использовать тест с пустой БД.
        async with async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)() as s:
            yield s

    app.dependency_overrides[get_session] = _override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def clean_db(engine: AsyncEngine):
    """Очищает все таблицы после теста (для тестов через api_client).

    Используется при тестах, идущих через HTTP — там обычные rollback'и
    не сработают, потому что endpoint делает свой commit.
    """
    yield
    # TRUNCATE всех таблиц кроме alembic_version
    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                """
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public' AND tablename != 'alembic_version'
                """
            )
        )
        tables = [r[0] for r in result.all()]
        if tables:
            await conn.execute(text(f"TRUNCATE TABLE {', '.join(tables)} RESTART IDENTITY CASCADE"))


# ---------- авторизованный клиент ----------
@pytest_asyncio.fixture
async def admin_client(api_client, engine):
    """Клиент с JWT-cookie уже залогиненного админа."""
    from app.core.security import create_access_token, hash_password
    from app.models.admin import Admin

    async with async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)() as s:
        admin = (
            await s.execute(text("SELECT id, username FROM admins WHERE username = 'test_admin'"))
        ).first()
        if admin is None:
            s.add(Admin(username="test_admin", password_hash=hash_password("testpass")))
            await s.commit()

    token = create_access_token("test_admin")
    api_client.cookies.set("access_token", token)
    yield api_client


# ---------- factories ----------
@pytest.fixture
def factories(session: AsyncSession):
    """Привязывает factory-boy фабрики к текущей сессии."""
    from tests import factories as f

    for factory_cls in (
        f.AdminFactory,
        f.BotFactory,
        f.ChannelFactory,
        f.ProductFactory,
        f.UserFactory,
        f.LeadFactory,
        f.PaymentFactory,
        f.SubscriptionFactory,
        f.TrackingLinkFactory,
        f.FunnelFactory,
        f.FunnelStepFactory,
        f.FunnelEntryFactory,
        f.FunnelTriggerFactory,
        f.LeadMagnetFactory,
        f.ScheduledMessageFactory,
    ):
        factory_cls._meta.sqlalchemy_session = session
    return f


@pytest_asyncio.fixture
async def make(session: AsyncSession, factories):
    """Async-хелпер для создания моделей.

    Для unit-тестов сервисов и хендлеров: использует общую `session` с flush().
    Для API-тестов: см. `make_committed` — он коммитит данные сразу,
    чтобы HTTP-эндпоинты их видели (иначе lock на одной транзакции).

    Пример:
        sub = await make.subscription(status="active")
    """
    class _Make:
        async def admin(self, **kw):
            obj = factories.Admin(**kw); session.add(obj); await session.flush(); return obj

        async def bot(self, **kw):
            obj = factories.Bot(**kw); session.add(obj); await session.flush(); return obj

        async def channel(self, **kw):
            if "bot" not in kw and "bot_id" not in kw:
                kw["bot"] = await self.bot()
            obj = factories.Channel(**kw); session.add(obj); await session.flush(); return obj

        async def product(self, **kw):
            if "channel" not in kw and "channel_id" not in kw:
                kw["channel"] = await self.channel()
            obj = factories.Product(**kw); session.add(obj); await session.flush(); return obj

        async def user(self, **kw):
            obj = factories.User(**kw); session.add(obj); await session.flush(); return obj

        async def lead(self, **kw):
            if "user" not in kw and "user_id" not in kw:
                kw["user"] = await self.user()
            if "product" not in kw and "product_id" not in kw:
                kw["product"] = await self.product()
            obj = factories.Lead(**kw); session.add(obj); await session.flush(); return obj

        async def payment(self, **kw):
            if "user" not in kw and "user_id" not in kw:
                kw["user"] = await self.user()
            if "product" not in kw and "product_id" not in kw:
                kw["product"] = await self.product()
            obj = factories.Payment(**kw); session.add(obj); await session.flush(); return obj

        async def subscription(self, **kw):
            if "user" not in kw and "user_id" not in kw:
                kw["user"] = await self.user()
            if "channel" not in kw and "channel_id" not in kw:
                kw["channel"] = await self.channel()
            obj = factories.Subscription(**kw); session.add(obj); await session.flush(); return obj

        async def tracking_link(self, **kw):
            if "product" not in kw and "product_id" not in kw:
                kw["product"] = await self.product()
            obj = factories.TrackingLink(**kw); session.add(obj); await session.flush(); return obj

        async def lead_magnet(self, **kw):
            obj = factories.LeadMagnet(**kw); session.add(obj); await session.flush(); return obj

        async def funnel(self, **kw):
            if "product" not in kw and "product_id" not in kw:
                kw["product"] = await self.product()
            obj = factories.Funnel(**kw); session.add(obj); await session.flush(); return obj

        async def funnel_step(self, **kw):
            if "funnel" not in kw and "funnel_id" not in kw:
                kw["funnel"] = await self.funnel()
            obj = factories.FunnelStep(**kw); session.add(obj); await session.flush(); return obj

        async def funnel_entry(self, **kw):
            if "user" not in kw and "user_id" not in kw:
                kw["user"] = await self.user()
            if "funnel" not in kw and "funnel_id" not in kw:
                kw["funnel"] = await self.funnel()
            obj = factories.FunnelEntry(**kw); session.add(obj); await session.flush(); return obj

        async def funnel_trigger(self, **kw):
            if "funnel" not in kw and "funnel_id" not in kw:
                kw["funnel"] = await self.funnel()
            obj = factories.FunnelTrigger(**kw); session.add(obj); await session.flush(); return obj

        async def scheduled_message(self, **kw):
            if "user" not in kw and "user_id" not in kw:
                kw["user"] = await self.user()
            obj = factories.ScheduledMessage(**kw); session.add(obj); await session.flush(); return obj

    return _Make()


@pytest_asyncio.fixture
async def make_committed(engine: AsyncEngine):
    """Создаёт модели через отдельный коммит — данные видны API-эндпоинтам.

    Использовать в API-тестах:
        product = await make_committed.product()
        # тут уже product.id есть и виден через admin_client
    """
    from tests import factories as f

    SetupSession = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def _save(factory_cls, **kw):
        async with SetupSession() as s:
            # Привязываем фабрики к этой сессии
            for fc in (f.AdminFactory, f.BotFactory, f.ChannelFactory, f.ProductFactory,
                       f.UserFactory, f.LeadFactory, f.PaymentFactory,
                       f.SubscriptionFactory, f.TrackingLinkFactory,
                       f.FunnelFactory, f.FunnelStepFactory, f.FunnelEntryFactory,
                       f.FunnelTriggerFactory, f.LeadMagnetFactory,
                       f.ScheduledMessageFactory):
                fc._meta.sqlalchemy_session = s
            obj = factory_cls(**kw)
            s.add(obj)
            await s.commit()
            await s.refresh(obj)
            return obj

    class _Committed:
        async def admin(self, **kw):
            return await _save(f.AdminFactory, **kw)

        async def bot(self, **kw):
            return await _save(f.BotFactory, **kw)

        async def channel(self, **kw):
            if "bot" not in kw and "bot_id" not in kw:
                kw["bot"] = await self.bot()
            return await _save(f.ChannelFactory, **kw)

        async def product(self, **kw):
            if "channel" not in kw and "channel_id" not in kw:
                kw["channel"] = await self.channel()
            return await _save(f.ProductFactory, **kw)

        async def user(self, **kw):
            return await _save(f.UserFactory, **kw)

        async def lead(self, **kw):
            if "user" not in kw and "user_id" not in kw:
                kw["user"] = await self.user()
            if "product" not in kw and "product_id" not in kw:
                kw["product"] = await self.product()
            return await _save(f.LeadFactory, **kw)

        async def payment(self, **kw):
            if "user" not in kw and "user_id" not in kw:
                kw["user"] = await self.user()
            if "product" not in kw and "product_id" not in kw:
                kw["product"] = await self.product()
            return await _save(f.PaymentFactory, **kw)

        async def subscription(self, **kw):
            if "user" not in kw and "user_id" not in kw:
                kw["user"] = await self.user()
            if "channel" not in kw and "channel_id" not in kw:
                kw["channel"] = await self.channel()
            return await _save(f.SubscriptionFactory, **kw)

        async def tracking_link(self, **kw):
            if "product" not in kw and "product_id" not in kw:
                kw["product"] = await self.product()
            return await _save(f.TrackingLinkFactory, **kw)

        async def lead_magnet(self, **kw):
            return await _save(f.LeadMagnetFactory, **kw)

        async def funnel(self, **kw):
            if "product" not in kw and "product_id" not in kw:
                kw["product"] = await self.product()
            return await _save(f.FunnelFactory, **kw)

        async def funnel_step(self, **kw):
            if "funnel" not in kw and "funnel_id" not in kw:
                kw["funnel"] = await self.funnel()
            return await _save(f.FunnelStepFactory, **kw)

        async def funnel_entry(self, **kw):
            if "user" not in kw and "user_id" not in kw:
                kw["user"] = await self.user()
            if "funnel" not in kw and "funnel_id" not in kw:
                kw["funnel"] = await self.funnel()
            return await _save(f.FunnelEntryFactory, **kw)

        async def funnel_trigger(self, **kw):
            if "funnel" not in kw and "funnel_id" not in kw:
                kw["funnel"] = await self.funnel()
            return await _save(f.FunnelTriggerFactory, **kw)

        async def scheduled_message(self, **kw):
            if "user" not in kw and "user_id" not in kw:
                kw["user"] = await self.user()
            return await _save(f.ScheduledMessageFactory, **kw)

    return _Committed()


# ---------- Telegram-моки ----------
@pytest.fixture
def mock_telegram_ok(httpx_mock):
    """Стандартные счастливые ответы от Telegram API."""
    httpx_mock.add_response(
        url__regex=r"https://api\.telegram\.org/bot.+/getMe",
        json={
            "ok": True,
            "result": {"id": 12345, "is_bot": True, "username": "testbot", "first_name": "TestBot"},
        },
        is_reusable=True,
    )
    httpx_mock.add_response(
        url__regex=r"https://api\.telegram\.org/bot.+/createChatInviteLink",
        json={"ok": True, "result": {"invite_link": "https://t.me/+abc123"}},
        is_reusable=True,
    )
    httpx_mock.add_response(
        url__regex=r"https://api\.telegram\.org/bot.+/sendMessage",
        json={
            "ok": True,
            "result": {"message_id": 1, "date": 1700000000, "chat": {"id": 1, "type": "private"}},
        },
        is_reusable=True,
    )
    return httpx_mock
