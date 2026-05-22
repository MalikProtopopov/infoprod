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
from app.schemas.bot import BotCreate, BotOut, BotUpdate
from app.services import telegram as tg

router = APIRouter(prefix="/bots", tags=["bots"])


def _to_out(b: BotModel, channels_count: int = 0, products_count: int = 0) -> BotOut:
    return BotOut(
        id=b.id,
        telegram_bot_id=b.telegram_bot_id,
        username=b.username,
        title=b.title,
        is_active=b.is_active,
        created_at=b.created_at,
        token_mask=_mask(b.token),
        channels_count=channels_count,
        products_count=products_count,
    )


def _mask(token: str) -> str:
    if not token:
        return ""
    if len(token) <= 10:
        return "***"
    return token[:6] + "…" + token[-4:]


@router.get("", response_model=list[BotOut])
async def list_bots(_: Admin = Depends(current_admin), session: AsyncSession = Depends(get_session)) -> list[BotOut]:
    rows = (await session.execute(select(BotModel).order_by(BotModel.id.desc()))).scalars().all()
    if not rows:
        return []
    bot_ids = [b.id for b in rows]
    ch_counts_rows = (
        await session.execute(
            select(Channel.bot_id, func.count(Channel.id))
            .where(Channel.bot_id.in_(bot_ids))
            .group_by(Channel.bot_id)
        )
    ).all()
    ch_counts = {row[0]: row[1] for row in ch_counts_rows}
    prod_counts_rows = (
        await session.execute(
            select(Channel.bot_id, func.count(Product.id))
            .join(Product, Product.channel_id == Channel.id)
            .where(Channel.bot_id.in_(bot_ids))
            .group_by(Channel.bot_id)
        )
    ).all()
    prod_counts = {row[0]: row[1] for row in prod_counts_rows}
    return [_to_out(b, ch_counts.get(b.id, 0), prod_counts.get(b.id, 0)) for b in rows]


@router.post("", response_model=BotOut, status_code=201)
async def add_bot(
    payload: BotCreate,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> BotOut:
    # Проверка токена через Telegram
    try:
        me = await tg.get_me(payload.token)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Не удалось проверить токен: {e}")
    if not me.get("is_bot"):
        raise HTTPException(status_code=400, detail="Токен не принадлежит боту")

    existing = (
        await session.execute(select(BotModel).where(BotModel.token == payload.token))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Такой бот уже добавлен")

    bot_row = BotModel(
        token=payload.token,
        telegram_bot_id=me["id"],
        username=me["username"],
        title=me.get("first_name"),
        is_active=True,
    )
    session.add(bot_row)
    await session.commit()
    await session.refresh(bot_row)

    await bot_manager.sync()
    return _to_out(bot_row)


@router.patch("/{bot_id}", response_model=BotOut)
async def update_bot(
    bot_id: int,
    payload: BotUpdate,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> BotOut:
    bot_row = (
        await session.execute(select(BotModel).where(BotModel.id == bot_id))
    ).scalar_one_or_none()
    if not bot_row:
        raise HTTPException(status_code=404, detail="Bot not found")
    if payload.is_active is not None:
        bot_row.is_active = payload.is_active
    await session.commit()
    await session.refresh(bot_row)
    await bot_manager.sync()
    return _to_out(bot_row)


@router.delete("/{bot_id}", status_code=204, response_class=Response)
async def delete_bot(
    bot_id: int,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> Response:
    bot_row = (
        await session.execute(select(BotModel).where(BotModel.id == bot_id))
    ).scalar_one_or_none()
    if not bot_row:
        raise HTTPException(status_code=404, detail="Bot not found")
    deps = (
        await session.execute(select(func.count()).select_from(Channel).where(Channel.bot_id == bot_row.id))
    ).scalar_one()
    if deps:
        raise HTTPException(
            status_code=409,
            detail=f"К этому боту привязано каналов: {deps}. Сначала удалите каналы.",
        )
    await session.delete(bot_row)
    await session.commit()
    await bot_manager.sync()
    return Response(status_code=204)
