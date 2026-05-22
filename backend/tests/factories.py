"""Factory-Boy фабрики для всех ORM-моделей.

Поскольку у большинства моделей НЕТ ORM-relationships (только FK *_id),
SubFactory отдаёт ID через `LazyAttribute(lambda o: ...)`.

Использование:
    user = factories.User()                  # добавлен в session, ещё без id
    await session.flush()                    # получаем id
    product = factories.Product(channel=ch)  # для Product → Channel relationship
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import factory
from factory.alchemy import SQLAlchemyModelFactory

from app.models.admin import Admin
from app.models.bot import Bot
from app.models.channel import Channel
from app.models.lead import Lead
from app.models.payment import Payment
from app.models.product import Product
from app.models.subscription import Subscription
from app.models.tracking_link import TrackingLink
from app.models.user import User


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


# Базовый класс: не auto-flush (AsyncSession.flush — coroutine, factory-boy не await'ит).
class _Base(SQLAlchemyModelFactory):
    class Meta:
        abstract = True
        sqlalchemy_session_persistence = None


class AdminFactory(_Base):
    class Meta:
        model = Admin

    username = factory.Sequence(lambda n: f"admin{n}")
    password_hash = "$2b$12$dummybcrypt.hash.for.tests.aaaaaaaaaaaaaaaaaa"


class BotFactory(_Base):
    class Meta:
        model = Bot

    token = factory.Sequence(lambda n: f"{10000 + n}:tokentokentokentokentokentokenA")
    telegram_bot_id = factory.Sequence(lambda n: 10000 + n)
    username = factory.Sequence(lambda n: f"bot{n}")
    title = factory.LazyAttribute(lambda o: f"Bot {o.username}")
    is_active = True


class ChannelFactory(_Base):
    class Meta:
        model = Channel

    telegram_chat_id = factory.Sequence(lambda n: -1000000000000 - n)
    title = factory.Sequence(lambda n: f"Channel {n}")
    username = None
    bot = factory.SubFactory(BotFactory)


class ProductFactory(_Base):
    class Meta:
        model = Product

    code = factory.Sequence(lambda n: f"product-{n}")
    name = factory.Sequence(lambda n: f"Product {n}")
    description = "Test product description"
    cover_url = None
    channel = factory.SubFactory(ChannelFactory)
    price_3m = 1000
    price_6m = 1800
    price_12m = 3000
    currency = "RUB"
    is_active = True


class UserFactory(_Base):
    class Meta:
        model = User

    telegram_user_id = factory.Sequence(lambda n: 100000 + n)
    username = factory.Sequence(lambda n: f"user{n}")
    first_name = "Test"
    last_name = "User"
    language_code = "ru"


# --- Модели БЕЗ relationships — передаём родителей в kwargs только как
# вспомогательные (exclude), а в БД пишем *_id.

class LeadFactory(_Base):
    """
    factories.Lead(user=u, product=p)
        — создаёт sub-объекты, если они не указаны.
    """
    class Meta:
        model = Lead
        exclude = ("user", "product")

    user = factory.SubFactory(UserFactory)
    product = factory.SubFactory(ProductFactory)
    user_id = factory.LazyAttribute(lambda o: o.user.id)
    product_id = factory.LazyAttribute(lambda o: o.product.id)
    status = "new"


class PaymentFactory(_Base):
    class Meta:
        model = Payment
        exclude = ("user", "product")

    user = factory.SubFactory(UserFactory)
    product = factory.SubFactory(ProductFactory)
    user_id = factory.LazyAttribute(lambda o: o.user.id)
    product_id = factory.LazyAttribute(lambda o: o.product.id)
    period_months = 3
    amount = 1000
    currency = "RUB"
    comment = None


class SubscriptionFactory(_Base):
    class Meta:
        model = Subscription
        exclude = ("user", "channel", "product", "payment")

    user = factory.SubFactory(UserFactory)
    channel = factory.SubFactory(ChannelFactory)
    product = None
    payment = None
    user_id = factory.LazyAttribute(lambda o: o.user.id)
    channel_id = factory.LazyAttribute(lambda o: o.channel.id)
    product_id = factory.LazyAttribute(lambda o: o.product.id if o.product else None)
    payment_id = factory.LazyAttribute(lambda o: o.payment.id if o.payment else None)
    starts_at = factory.LazyFunction(_now)
    ends_at = factory.LazyAttribute(lambda o: o.starts_at + timedelta(days=90))
    status = "active"
    invite_link = None


class TrackingLinkFactory(_Base):
    class Meta:
        model = TrackingLink
        exclude = ("product", "bot")

    slug = factory.Sequence(lambda n: f"slug{n:04d}AB")
    product = factory.SubFactory(ProductFactory)
    bot = None
    product_id = factory.LazyAttribute(lambda o: o.product.id)
    bot_id = factory.LazyAttribute(lambda o: o.bot.id if o.bot else None)
    utm_source = "instagram"
    utm_medium = "reels"
    utm_campaign = "test"
    utm_content = None
    notes = None
    is_active = True
    click_count = 0
    unique_users = 0


# Short aliases
User = UserFactory
Bot = BotFactory
Channel = ChannelFactory
Product = ProductFactory
Admin = AdminFactory
Lead = LeadFactory
Payment = PaymentFactory
Subscription = SubscriptionFactory
TrackingLink = TrackingLinkFactory
