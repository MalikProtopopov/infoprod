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
import tempfile
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
# Файловое хранилище в тестах — во временную папку (прод-путь /var/lib не пишется).
os.environ.setdefault("RECEIPTS_DIR", tempfile.mkdtemp(prefix="test-receipts-"))
os.environ.setdefault("STEP_MEDIA_DIR", tempfile.mkdtemp(prefix="test-stepmedia-"))
os.environ.setdefault("PRODUCT_MEDIA_DIR", tempfile.mkdtemp(prefix="test-productmedia-"))


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
@pytest_asyncio.fixture(autouse=True)
async def _bind_sessionlocal(engine: AsyncEngine):
    """Привязывает app.db.session.SessionLocal к тестовому движку (NullPool).

    Код, использующий SessionLocal напрямую (напр. AuditMiddleware), в тестах
    должен ходить в тестовую БД, а не в глобальный пул (он ломается между
    per-test event loop'ами — «Future attached to a different loop»).
    """
    import app.db.session as dbs

    orig = dbs.SessionLocal
    dbs.SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        yield
    finally:
        dbs.SessionLocal = orig


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


# ---------- factory helper (общий для make / make_committed) ----------
# name -> (атрибут фабрики в tests.factories, [(dep_kwarg, dep_method), ...])
# Дефолтинг зависимостей (bot→channel→product и т.п.) описан здесь один раз,
# вместо дублирования в _Make (flush) и _Committed (commit).
_FACTORY_DEPS: dict[str, tuple[str, list[tuple[str, str]]]] = {
    "admin": ("AdminFactory", []),
    "bot": ("BotFactory", []),
    "channel": ("ChannelFactory", [("bot", "bot")]),
    "product": ("ProductFactory", [("channel", "channel")]),
    "user": ("UserFactory", []),
    "lead": ("LeadFactory", [("user", "user"), ("product", "product")]),
    "payment": ("PaymentFactory", [("user", "user"), ("product", "product")]),
    "subscription": ("SubscriptionFactory", [("user", "user"), ("channel", "channel")]),
    "tracking_link": ("TrackingLinkFactory", [("product", "product")]),
    "lead_magnet": ("LeadMagnetFactory", []),
    "funnel": ("FunnelFactory", [("product", "product")]),
    "funnel_step": ("FunnelStepFactory", [("funnel", "funnel")]),
    "funnel_entry": ("FunnelEntryFactory", [("user", "user"), ("funnel", "funnel")]),
    "funnel_trigger": ("FunnelTriggerFactory", [("funnel", "funnel")]),
    "scheduled_message": ("ScheduledMessageFactory", [("user", "user")]),
}


class _FactoryHelper:
    """Динамический фасад над factory-boy: дефолтит зависимости и сохраняет
    через стратегию persist(factory_attr, **kw) -> obj (flush либо commit)."""

    def __init__(self, persist):
        self._persist = persist

    def __getattr__(self, name: str):
        if name not in _FACTORY_DEPS:
            raise AttributeError(name)
        factory_attr, deps = _FACTORY_DEPS[name]

        async def _create(**kw):
            for dep_kw, dep_method in deps:
                if dep_kw not in kw and f"{dep_kw}_id" not in kw:
                    kw[dep_kw] = await getattr(self, dep_method)()
            return await self._persist(factory_attr, **kw)

        return _create


@pytest_asyncio.fixture
async def make(session: AsyncSession, factories):
    """Async-хелпер создания моделей на общей `session` с flush() (unit-тесты).

    Пример: sub = await make.subscription(status="active")
    """
    async def _persist(factory_attr: str, **kw):
        obj = getattr(factories, factory_attr)(**kw)
        session.add(obj)
        await session.flush()
        return obj

    return _FactoryHelper(_persist)


@pytest_asyncio.fixture
async def make_committed(engine: AsyncEngine):
    """Создаёт модели через отдельный коммит — данные видны API-эндпоинтам.

    Пример: product = await make_committed.product()
    """
    from tests import factories as f

    SetupSession = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    _all_factory_attrs = [attr for attr, _ in _FACTORY_DEPS.values()]

    async def _persist(factory_attr: str, **kw):
        async with SetupSession() as s:
            # Привязываем все фабрики к этой сессии перед созданием.
            for attr in _all_factory_attrs:
                getattr(f, attr)._meta.sqlalchemy_session = s
            obj = getattr(f, factory_attr)(**kw)
            s.add(obj)
            await s.commit()
            await s.refresh(obj)
            return obj

    return _FactoryHelper(_persist)


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
