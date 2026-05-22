from __future__ import annotations

from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_admin, get_session
from app.models.admin import Admin
from app.models.bot import Bot as BotModel
from app.models.lead import Lead
from app.models.payment import Payment
from app.models.product import Product
from app.models.tracking_link import TrackingLink
from app.schemas.tracking_link import (
    TrackingLinkBotRef,
    TrackingLinkCreate,
    TrackingLinkOut,
    TrackingLinkProductRef,
    TrackingLinkUpdate,
)
from app.services.tracking_links import (
    ConflictError,
    GenerationError,
    InvalidSlugError,
    TrackingLinksService,
)

router = APIRouter(prefix="/tracking-links", tags=["tracking-links"])


async def _build_out(
    session: AsyncSession,
    link: TrackingLink,
    *,
    metrics: dict | None = None,
) -> TrackingLinkOut:
    """Соберёт TrackingLinkOut с подгрузкой Product и Bot, и метриками.

    Если metrics не передан — считается одиночными запросами.
    """
    prod = (
        await session.execute(
            select(Product.id, Product.code, Product.name).where(Product.id == link.product_id)
        )
    ).first()
    if prod is None:
        raise HTTPException(status_code=500, detail="Продукт не найден для ссылки")
    product_ref = TrackingLinkProductRef(id=prod[0], code=prod[1], name=prod[2])

    bot_ref: TrackingLinkBotRef | None = None
    if link.bot_id is not None:
        bot_row = (
            await session.execute(
                select(BotModel.id, BotModel.username).where(BotModel.id == link.bot_id)
            )
        ).first()
        if bot_row is not None:
            bot_ref = TrackingLinkBotRef(id=bot_row[0], username=bot_row[1])

    bot_username = bot_ref.username if bot_ref else "_"
    url = f"https://t.me/{bot_username}?start={link.slug}"

    if metrics is None:
        leads_count = (
            await session.execute(
                select(func.count()).select_from(Lead).where(Lead.tracking_link_id == link.id)
            )
        ).scalar_one()
        payments_count = (
            await session.execute(
                select(func.count()).select_from(Payment).where(Payment.tracking_link_id == link.id)
            )
        ).scalar_one()
        revenue = (
            await session.execute(
                select(func.coalesce(func.sum(Payment.amount), 0)).where(
                    Payment.tracking_link_id == link.id
                )
            )
        ).scalar_one()
        metrics = {
            "leads_count": int(leads_count),
            "payments_count": int(payments_count),
            "revenue": str(revenue),
        }

    return TrackingLinkOut(
        id=link.id,
        slug=link.slug,
        url=url,
        product=product_ref,
        bot=bot_ref,
        utm_source=link.utm_source,
        utm_medium=link.utm_medium,
        utm_campaign=link.utm_campaign,
        utm_content=link.utm_content,
        notes=link.notes,
        is_active=link.is_active,
        click_count=int(link.click_count),
        unique_users=int(link.unique_users),
        leads_count=metrics["leads_count"],
        payments_count=metrics["payments_count"],
        revenue=str(metrics["revenue"]),
        created_at=link.created_at,
    )


@router.get("", response_model=list[TrackingLinkOut])
async def list_tracking_links(
    admin: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
    product_id: int | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[TrackingLinkOut]:
    service = TrackingLinksService(session)
    links = await service.list_all(product_id=product_id, is_active=is_active, limit=limit, offset=offset)
    if not links:
        return []
    # Batch-агрегаты для метрик
    link_ids = [l.id for l in links]
    leads_rows = (
        await session.execute(
            select(Lead.tracking_link_id, func.count(Lead.id))
            .where(Lead.tracking_link_id.in_(link_ids))
            .group_by(Lead.tracking_link_id)
        )
    ).all()
    leads_map = {r[0]: r[1] for r in leads_rows}
    pay_rows = (
        await session.execute(
            select(Payment.tracking_link_id, func.count(Payment.id), func.coalesce(func.sum(Payment.amount), 0))
            .where(Payment.tracking_link_id.in_(link_ids))
            .group_by(Payment.tracking_link_id)
        )
    ).all()
    pay_map = {r[0]: (r[1], r[2]) for r in pay_rows}

    out: list[TrackingLinkOut] = []
    for link in links:
        m = {
            "leads_count": int(leads_map.get(link.id, 0)),
            "payments_count": int(pay_map.get(link.id, (0, 0))[0]),
            "revenue": str(pay_map.get(link.id, (0, 0))[1]),
        }
        out.append(await _build_out(session, link, metrics=m))
    return out


@router.post("", response_model=TrackingLinkOut, status_code=201)
async def create_tracking_link(
    payload: TrackingLinkCreate,
    admin: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> TrackingLinkOut:
    # Проверка существования продукта и (опционально) бота
    product_exists = (
        await session.execute(select(Product.id).where(Product.id == payload.product_id))
    ).first()
    if product_exists is None:
        raise HTTPException(status_code=400, detail="Продукт не найден")
    if payload.bot_id is not None:
        bot_exists = (
            await session.execute(select(BotModel.id).where(BotModel.id == payload.bot_id))
        ).first()
        if bot_exists is None:
            raise HTTPException(status_code=400, detail="Бот не найден")

    service = TrackingLinksService(session)
    try:
        link = await service.create(
            product_id=payload.product_id,
            utm_source=payload.utm_source,
            utm_medium=payload.utm_medium,
            utm_campaign=payload.utm_campaign,
            utm_content=payload.utm_content,
            bot_id=payload.bot_id,
            notes=payload.notes,
            custom_slug=payload.custom_slug,
            created_by=admin.id,
        )
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except InvalidSlugError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except GenerationError as e:
        raise HTTPException(status_code=500, detail=str(e))

    await session.commit()
    await session.refresh(link)
    return await _build_out(session, link)


@router.get("/{link_id}", response_model=TrackingLinkOut)
async def get_tracking_link(
    link_id: int,
    admin: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> TrackingLinkOut:
    link = await session.get(TrackingLink, link_id)
    if link is None:
        raise HTTPException(status_code=404, detail="Ссылка не найдена")
    return await _build_out(session, link)


@router.patch("/{link_id}", response_model=TrackingLinkOut)
async def update_tracking_link(
    link_id: int,
    payload: TrackingLinkUpdate,
    admin: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> TrackingLinkOut:
    service = TrackingLinksService(session)
    link = await service.update(link_id, notes=payload.notes, is_active=payload.is_active)
    if link is None:
        raise HTTPException(status_code=404, detail="Ссылка не найдена")
    await session.commit()
    await session.refresh(link)
    return await _build_out(session, link)


@router.delete("/{link_id}", status_code=204, response_class=Response)
async def delete_tracking_link(
    link_id: int,
    hard: bool = Query(default=False, description="Удалить полностью; недоступно если есть leads/payments"),
    admin: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> Response:
    service = TrackingLinksService(session)
    link = await session.get(TrackingLink, link_id)
    if link is None:
        raise HTTPException(status_code=404, detail="Ссылка не найдена")
    if hard:
        can, counts = await service.can_hard_delete(link_id)
        if not can:
            raise HTTPException(
                status_code=409,
                detail=f"К ссылке привязано: заявок {counts['leads']}, оплат {counts['payments']}. Hard-delete недоступен.",
            )
        await session.delete(link)
        await session.commit()
        return Response(status_code=204)
    # soft delete
    await service.deactivate(link_id)
    await session.commit()
    return Response(status_code=204)


@router.get("/{link_id}/qr.png", response_class=Response)
async def qr_png(
    link_id: int,
    admin: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> Response:
    link = await session.get(TrackingLink, link_id)
    if link is None:
        raise HTTPException(status_code=404, detail="Ссылка не найдена")

    bot_username = "_"
    if link.bot_id is not None:
        bot_row = (
            await session.execute(select(BotModel.username).where(BotModel.id == link.bot_id))
        ).scalar_one_or_none()
        if bot_row is not None:
            bot_username = bot_row
    url = f"https://t.me/{bot_username}?start={link.slug}"

    try:
        import qrcode  # type: ignore
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="qrcode не установлен. Добавьте qrcode[pil] в requirements.txt.",
        )

    img = qrcode.make(url, box_size=10, border=2)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png", headers={
        "Cache-Control": "public, max-age=3600",
    })
