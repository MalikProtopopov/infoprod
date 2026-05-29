from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_admin, get_session
from app.core.config import settings
from app.models.admin import Admin
from app.models.channel import Channel
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductOut, ProductUpdate
from app.services.tracking_links import product_code_conflicts_with_slug

router = APIRouter(prefix="/products", tags=["products"])


def _to_out(p: Product, channel_title: str | None = None) -> ProductOut:
    return ProductOut(
        id=p.id,
        code=p.code,
        name=p.name,
        description=p.description,
        cover_url=p.cover_url,
        channel_id=p.channel_id,
        channel_title=channel_title,
        price_3m=p.price_3m,
        price_6m=p.price_6m,
        price_12m=p.price_12m,
        currency=p.currency,
        is_active=p.is_active,
        default_funnel_id=p.default_funnel_id,
        card_text=p.card_text,
        thank_you_message=p.thank_you_message,
        presentation_enabled=p.presentation_enabled,
        created_at=p.created_at,
    )


@router.get("", response_model=list[ProductOut])
async def list_products(
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> list[ProductOut]:
    rows = (
        await session.execute(
            select(Product, Channel.title)
            .outerjoin(Channel, Channel.id == Product.channel_id)
            .order_by(Product.id.desc())
        )
    ).all()
    return [_to_out(p, ct) for p, ct in rows]


@router.get("/{product_id}", response_model=ProductOut)
async def get_product(
    product_id: int,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> ProductOut:
    row = (
        await session.execute(
            select(Product, Channel.title)
            .outerjoin(Channel, Channel.id == Product.channel_id)
            .where(Product.id == product_id)
        )
    ).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    p, ct = row
    return _to_out(p, ct)


@router.post("", response_model=ProductOut, status_code=201)
async def create_product(
    payload: ProductCreate,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> ProductOut:
    # Канал необязателен (продукт-лид-магнит). Если указан — проверяем, что существует.
    ch: Channel | None = None
    if payload.channel_id is not None:
        ch = (await session.execute(select(Channel).where(Channel.id == payload.channel_id))).scalar_one_or_none()
        if not ch:
            raise HTTPException(status_code=400, detail="Канал не найден")

    exists = (
        await session.execute(select(Product).where(Product.code == payload.code))
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="Продукт с таким кодом уже существует")
    if await product_code_conflicts_with_slug(session, payload.code):
        raise HTTPException(status_code=409, detail="Код совпадает со slug существующей трекинговой ссылки")

    p = Product(
        code=payload.code,
        name=payload.name,
        description=payload.description,
        cover_url=payload.cover_url,
        channel_id=payload.channel_id,
        price_3m=payload.price_3m,
        price_6m=payload.price_6m,
        price_12m=payload.price_12m,
        currency=payload.currency or settings.default_currency,
        is_active=payload.is_active,
    )
    session.add(p)
    await session.commit()
    await session.refresh(p)
    return _to_out(p, ch.title if ch else None)


@router.patch("/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: int,
    payload: ProductUpdate,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> ProductOut:
    p = (await session.execute(select(Product).where(Product.id == product_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    data = payload.model_dump(exclude_unset=True)
    if "code" in data and data["code"] is not None and data["code"] != p.code:
        clash = (
            await session.execute(select(Product).where(Product.code == data["code"]))
        ).scalar_one_or_none()
        if clash:
            raise HTTPException(status_code=409, detail="Код уже занят")
        if await product_code_conflicts_with_slug(session, data["code"]):
            raise HTTPException(status_code=409, detail="Код совпадает со slug существующей трекинговой ссылки")
    # channel_id обрабатываем отдельно: допускаем явный сброс в None (продукт
    # без канала), а также проверяем существование при назначении.
    if "channel_id" in data:
        new_channel_id = data.pop("channel_id")
        if new_channel_id is not None:
            ch = (await session.execute(select(Channel).where(Channel.id == new_channel_id))).scalar_one_or_none()
            if not ch:
                raise HTTPException(status_code=400, detail="Канал не найден")
        p.channel_id = new_channel_id
    for key, value in data.items():
        if value is not None:
            setattr(p, key, value)
    await session.commit()
    await session.refresh(p)
    ch_title = (
        await session.execute(select(Channel.title).where(Channel.id == p.channel_id))
    ).scalar_one_or_none()
    return _to_out(p, ch_title)


@router.delete("/{product_id}", status_code=204, response_class=Response)
async def delete_product(
    product_id: int,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> Response:
    p = (await session.execute(select(Product).where(Product.id == product_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")

    # Платежи на продукт хранятся с ondelete=RESTRICT (финансовые записи нельзя
    # терять). Если они есть — удаление невозможно: возвращаем понятный 409
    # вместо сырого 500/IntegrityError. Продукт следует деактивировать.
    from app.models.payment import Payment

    payments_count = (
        await session.execute(
            select(func.count()).select_from(Payment).where(Payment.product_id == product_id)
        )
    ).scalar_one()
    if payments_count:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Нельзя удалить продукт: по нему есть платежи ({payments_count}). "
                "Снимите галочку «Активен», чтобы скрыть его, вместо удаления."
            ),
        )

    await session.delete(p)
    try:
        await session.commit()
    except IntegrityError:
        # Подстраховка на любой другой RESTRICT/ограничение целостности.
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Нельзя удалить продукт: на него есть связанные записи. Деактивируйте его.",
        )
    return Response(status_code=204)
