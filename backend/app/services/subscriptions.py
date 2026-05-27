from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import manager as bot_manager
from app.bot.texts import access_granted, access_expired
from app.models.channel import Channel
from app.models.payment import Payment
from app.models.product import Product
from app.models.subscription import Subscription
from app.models.user import User
from app.services import telegram as tg

logger = logging.getLogger(__name__)


def _add_months(dt: datetime, months: int) -> datetime:
    from dateutil.relativedelta import relativedelta
    return dt + relativedelta(months=months)


async def grant_for_payment(session: AsyncSession, payment: Payment) -> Subscription:
    """Создаёт/продлевает подписку под payment и отправляет invite‑ссылку клиенту."""
    product = (await session.execute(select(Product).where(Product.id == payment.product_id))).scalar_one()
    channel = (await session.execute(select(Channel).where(Channel.id == product.channel_id))).scalar_one()
    user = (await session.execute(select(User).where(User.id == payment.user_id))).scalar_one()

    now = datetime.now(tz=timezone.utc)

    existing = (
        await session.execute(
            select(Subscription).where(
                Subscription.user_id == user.id,
                Subscription.channel_id == channel.id,
                Subscription.status == "active",
            )
        )
    ).scalar_one_or_none()

    if existing and existing.ends_at > now:
        existing.ends_at = _add_months(existing.ends_at, payment.period_months)
        existing.product_id = product.id
        existing.payment_id = payment.id
        existing.updated_at = now
        sub = existing
    else:
        sub = Subscription(
            user_id=user.id,
            channel_id=channel.id,
            product_id=product.id,
            payment_id=payment.id,
            starts_at=now,
            ends_at=_add_months(now, payment.period_months),
            status="active",
        )
        session.add(sub)

    await session.flush()

    bot = bot_manager.get_aiogram_bot(channel.bot_id)
    invite_link: Optional[str] = None
    if bot is not None:
        invite_link = await tg.create_one_time_invite(bot, channel.telegram_chat_id, expire_at=sub.ends_at)
        if invite_link:
            sub.invite_link = invite_link
            await session.flush()

        text = access_granted(
            channel_title=channel.title,
            ends_at=sub.ends_at,
            invite_link=invite_link or "(ссылка будет отправлена администратором)",
        )
        await tg.send_message_safe(bot, user.telegram_user_id, text)

        # Благодарственное сообщение продукта (если настроено) — отдельным сообщением.
        thank_you = getattr(product, "thank_you_message", None)
        if thank_you and thank_you.strip():
            await tg.send_message_safe(bot, user.telegram_user_id, thank_you)

    return sub


async def revoke(session: AsyncSession, sub: Subscription, *, status: str = "revoked", notify: bool = True) -> None:
    channel = (await session.execute(select(Channel).where(Channel.id == sub.channel_id))).scalar_one()
    user = (await session.execute(select(User).where(User.id == sub.user_id))).scalar_one()
    bot = bot_manager.get_aiogram_bot(channel.bot_id)
    if bot is not None:
        await tg.kick_user(bot, channel.telegram_chat_id, user.telegram_user_id)
        if notify:
            await tg.send_message_safe(bot, user.telegram_user_id, access_expired(channel.title))

    sub.status = status
    sub.updated_at = datetime.now(tz=timezone.utc)


async def extend(session: AsyncSession, sub: Subscription, *, days: int = 0, months: int = 0) -> None:
    from dateutil.relativedelta import relativedelta  # локальный импорт чтобы не тащить наверх

    now = datetime.now(tz=timezone.utc)
    was_inactive = sub.status != "active"

    base = max(sub.ends_at, now)
    sub.ends_at = base + timedelta(days=days) + relativedelta(months=months)
    sub.status = "active"
    sub.updated_at = now

    # Если подписка была неактивной — пользователь не в канале, нужна новая invite-ссылка.
    if was_inactive:
        channel = (await session.execute(select(Channel).where(Channel.id == sub.channel_id))).scalar_one()
        user = (await session.execute(select(User).where(User.id == sub.user_id))).scalar_one()
        bot = bot_manager.get_aiogram_bot(channel.bot_id)
        if bot is not None:
            link = await tg.create_one_time_invite(bot, channel.telegram_chat_id, expire_at=sub.ends_at)
            if link:
                sub.invite_link = link
            await tg.send_message_safe(
                bot, user.telegram_user_id,
                access_granted(channel.title, sub.ends_at, link or "(ссылка будет отправлена администратором)"),
            )


async def expire_due(session: AsyncSession) -> int:
    """Выбрать истёкшие активные подписки, отозвать их."""
    now = datetime.now(tz=timezone.utc)
    rows = (
        await session.execute(
            select(Subscription).where(Subscription.status == "active", Subscription.ends_at <= now)
        )
    ).scalars().all()
    count = 0
    for sub in rows:
        try:
            await revoke(session, sub, status="expired", notify=True)
            count += 1
        except Exception as e:  # не падаем из-за одной подписки
            logger.exception("expire_due failed for sub_id=%s: %s", sub.id, e)
    await session.commit()
    return count
