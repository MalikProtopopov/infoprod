from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_admin, get_session
from app.bot import manager as bot_manager
from app.models.admin import Admin
from app.models.bot import Bot as BotModel
from app.models.channel import Channel
from app.models.product import Product
from app.models.subscription import Subscription
from app.schemas.channel import ChannelCreate, ChannelOut, ChannelUpdate
from app.services import telegram as tg

router = APIRouter(prefix="/channels", tags=["channels"])


def _to_out(
    ch: Channel,
    bot_username: str | None = None,
    products_count: int = 0,
    active_subs_count: int = 0,
) -> ChannelOut:
    return ChannelOut(
        id=ch.id,
        telegram_chat_id=ch.telegram_chat_id,
        title=ch.title,
        username=ch.username,
        bot_id=ch.bot_id,
        bot_username=bot_username,
        created_at=ch.created_at,
        products_count=products_count,
        active_subs_count=active_subs_count,
    )


@router.get("", response_model=list[ChannelOut])
async def list_channels(_: Admin = Depends(current_admin), session: AsyncSession = Depends(get_session)) -> list[ChannelOut]:
    rows = (
        await session.execute(
            select(Channel, BotModel.username)
            .join(BotModel, BotModel.id == Channel.bot_id)
            .order_by(Channel.id.desc())
        )
    ).all()
    if not rows:
        return []
    channel_ids = [ch.id for ch, _ in rows]
    # products_count показываем согласованно с active_subs_count — только активные продукты,
    # иначе UI противоречит сам себе: «3 продукта · 0 активных подписок» при том, что 2 из 3 — drafts.
    prod_counts_rows = (
        await session.execute(
            select(Product.channel_id, func.count(Product.id))
            .where(Product.channel_id.in_(channel_ids), Product.is_active.is_(True))
            .group_by(Product.channel_id)
        )
    ).all()
    prod_counts = {r[0]: r[1] for r in prod_counts_rows}
    sub_counts_rows = (
        await session.execute(
            select(Subscription.channel_id, func.count(Subscription.id))
            .where(Subscription.channel_id.in_(channel_ids), Subscription.status == "active")
            .group_by(Subscription.channel_id)
        )
    ).all()
    sub_counts = {r[0]: r[1] for r in sub_counts_rows}
    return [
        _to_out(ch, bot_un, prod_counts.get(ch.id, 0), sub_counts.get(ch.id, 0))
        for ch, bot_un in rows
    ]


@router.post("", response_model=ChannelOut, status_code=201)
async def add_channel(
    payload: ChannelCreate,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> ChannelOut:
    bot_row = (
        await session.execute(select(BotModel).where(BotModel.id == payload.bot_id, BotModel.is_active.is_(True)))
    ).scalar_one_or_none()
    if not bot_row:
        raise HTTPException(status_code=400, detail="Бот не найден или неактивен")

    aiogram_bot = bot_manager.get_aiogram_bot(bot_row.id)
    if aiogram_bot is None:
        await bot_manager.sync()
        aiogram_bot = bot_manager.get_aiogram_bot(bot_row.id)
    if aiogram_bot is None:
        raise HTTPException(status_code=400, detail="Бот не запущен. Повторите чуть позже.")

    ok, reason = await tg.ensure_bot_can_invite(aiogram_bot, payload.telegram_chat_id)
    if not ok:
        raise HTTPException(status_code=400, detail=reason or "Бот не имеет прав в канале")

    title, username = await tg.get_chat_title(aiogram_bot, payload.telegram_chat_id)
    final_title = payload.title or title or f"Channel {payload.telegram_chat_id}"
    final_username = payload.username or username

    existing = (
        await session.execute(select(Channel).where(Channel.telegram_chat_id == payload.telegram_chat_id))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Канал уже добавлен")

    ch = Channel(
        telegram_chat_id=payload.telegram_chat_id,
        title=final_title,
        username=final_username,
        bot_id=bot_row.id,
    )
    session.add(ch)
    await session.commit()
    await session.refresh(ch)
    return _to_out(ch, bot_row.username)


@router.patch("/{channel_id}", response_model=ChannelOut)
async def update_channel(
    channel_id: int,
    payload: ChannelUpdate,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> ChannelOut:
    ch = (await session.execute(select(Channel).where(Channel.id == channel_id))).scalar_one_or_none()
    if not ch:
        raise HTTPException(status_code=404, detail="Channel not found")
    if payload.title is not None:
        ch.title = payload.title
    if payload.username is not None:
        ch.username = payload.username
    await session.commit()
    await session.refresh(ch)
    return _to_out(ch)


@router.delete("/{channel_id}", status_code=204, response_class=Response)
async def delete_channel(
    channel_id: int,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> Response:
    ch = (await session.execute(select(Channel).where(Channel.id == channel_id))).scalar_one_or_none()
    if not ch:
        raise HTTPException(status_code=404, detail="Channel not found")
    prod_cnt = (
        await session.execute(select(func.count()).select_from(Product).where(Product.channel_id == ch.id))
    ).scalar_one()
    sub_cnt = (
        await session.execute(
            select(func.count())
            .select_from(Subscription)
            .where(Subscription.channel_id == ch.id, Subscription.status == "active")
        )
    ).scalar_one()
    if prod_cnt or sub_cnt:
        details = []
        if prod_cnt:
            details.append(f"продуктов: {prod_cnt}")
        if sub_cnt:
            details.append(f"активных подписок: {sub_cnt}")
        raise HTTPException(status_code=409, detail="К каналу привязано " + ", ".join(details))
    await session.delete(ch)
    await session.commit()
    return Response(status_code=204)
