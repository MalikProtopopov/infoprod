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


# ─── Funnels module ───

from app.models.funnel import Funnel as _Funnel
from app.models.funnel_step import FunnelStep as _FunnelStep
from app.models.funnel_entry import FunnelEntry as _FunnelEntry
from app.models.funnel_trigger import FunnelTrigger as _FunnelTrigger
from app.models.lead_magnet import LeadMagnet as _LeadMagnet
from app.models.scheduled_message import ScheduledMessage as _ScheduledMessage


class LeadMagnetFactory(_Base):
    class Meta:
        model = _LeadMagnet
        exclude = ("product",)

    name = factory.Sequence(lambda n: f"Lead Magnet {n}")
    description = None
    file_url = factory.Sequence(lambda n: f"/tmp/test_lm_{n}.pdf")
    file_type = "pdf"
    file_size = 1024
    telegram_file_id = None
    product = None
    product_id = factory.LazyAttribute(lambda o: o.product.id if o.product else None)
    is_active = True
    download_count = 0


class FunnelFactory(_Base):
    class Meta:
        model = _Funnel
        exclude = ("product",)

    name = factory.Sequence(lambda n: f"Funnel {n}")
    description = None
    product = factory.SubFactory(ProductFactory)
    product_id = factory.LazyAttribute(lambda o: o.product.id)
    bot_id = None
    is_active = True
    ttl_days = 90
    cancel_on_payment = True


class FunnelStepFactory(_Base):
    class Meta:
        model = _FunnelStep
        exclude = ("funnel",)

    funnel = factory.SubFactory(FunnelFactory)
    funnel_id = factory.LazyAttribute(lambda o: o.funnel.id)
    order_idx = factory.Sequence(lambda n: n)
    delay_minutes = 0
    message_text = "Default step text"
    parse_mode = "HTML"
    lead_magnet_id = None
    buttons = None
    is_active = True


class FunnelEntryFactory(_Base):
    class Meta:
        model = _FunnelEntry
        exclude = ("funnel", "user")

    funnel = factory.SubFactory(FunnelFactory)
    user = factory.SubFactory(UserFactory)
    funnel_id = factory.LazyAttribute(lambda o: o.funnel.id)
    user_id = factory.LazyAttribute(lambda o: o.user.id)
    source = "manual"
    source_ref = None
    status = "active"


class FunnelTriggerFactory(_Base):
    class Meta:
        model = _FunnelTrigger
        exclude = ("funnel",)

    funnel = factory.SubFactory(FunnelFactory)
    funnel_id = factory.LazyAttribute(lambda o: o.funnel.id)
    word = factory.Sequence(lambda n: f"trigger{n}")
    is_active = True
    use_count = 0


class ScheduledMessageFactory(_Base):
    class Meta:
        model = _ScheduledMessage
        exclude = ("user", "entry", "step")

    user = factory.SubFactory(UserFactory)
    entry = None
    step = None
    user_id = factory.LazyAttribute(lambda o: o.user.id)
    funnel_entry_id = factory.LazyAttribute(lambda o: o.entry.id if o.entry else None)
    funnel_step_id = factory.LazyAttribute(lambda o: o.step.id if o.step else None)
    template_key = None
    payload = None
    scheduled_at = factory.LazyFunction(_now)
    sent_at = None
    cancelled_at = None
    attempts = 0


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
Funnel = FunnelFactory
FunnelStep = FunnelStepFactory
FunnelEntry = FunnelEntryFactory
FunnelTrigger = FunnelTriggerFactory
LeadMagnet = LeadMagnetFactory
ScheduledMessage = ScheduledMessageFactory
