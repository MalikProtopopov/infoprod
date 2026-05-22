from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_admin, get_session
from app.models.admin import Admin
from app.models.channel import Channel
from app.models.lead import Lead
from app.models.product import Product
from app.models.user import User
from app.schemas.lead import LeadOut, LeadUpdate

router = APIRouter(prefix="/leads", tags=["leads"])


def _to_out(lead: Lead, user: User, product: Product, channel: Channel) -> LeadOut:
    return LeadOut(
        id=lead.id,
        status=lead.status,
        created_at=lead.created_at,
        user_id=user.id,
        user_telegram_id=user.telegram_user_id,
        user_username=user.username,
        user_first_name=user.first_name,
        user_last_name=user.last_name,
        user_language=user.language_code,
        user_phone=user.phone,
        user_email=user.email,
        user_notes=user.notes,
        product_id=product.id,
        product_code=product.code,
        product_name=product.name,
        product_description=product.description,
        product_currency=product.currency,
        product_price_3m=product.price_3m,
        product_price_6m=product.price_6m,
        product_price_12m=product.price_12m,
        channel_id=channel.id,
        channel_title=channel.title,
    )


@router.get("", response_model=dict)
async def list_leads(
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
    status: str | None = Query(default=None, description="new|contacted|paid|closed|all"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict:
    stmt = (
        select(Lead, User, Product, Channel)
        .join(User, User.id == Lead.user_id)
        .join(Product, Product.id == Lead.product_id)
        .join(Channel, Channel.id == Product.channel_id)
        .order_by(Lead.id.desc())
    )
    count_stmt = select(func.count()).select_from(Lead)
    if status and status != "all":
        stmt = stmt.where(Lead.status == status)
        count_stmt = count_stmt.where(Lead.status == status)
    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(stmt.limit(limit).offset(offset))).all()
    return {
        "total": total,
        "items": [_to_out(l, u, p, c).model_dump(mode="json") for l, u, p, c in rows],
    }


@router.get("/{lead_id}", response_model=LeadOut)
async def get_lead(
    lead_id: int,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> LeadOut:
    row = (
        await session.execute(
            select(Lead, User, Product, Channel)
            .join(User, User.id == Lead.user_id)
            .join(Product, Product.id == Lead.product_id)
            .join(Channel, Channel.id == Product.channel_id)
            .where(Lead.id == lead_id)
        )
    ).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    l, u, p, c = row
    return _to_out(l, u, p, c)


@router.patch("/{lead_id}", response_model=LeadOut)
async def update_lead(
    lead_id: int,
    payload: LeadUpdate,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> LeadOut:
    lead = (await session.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    # Фиксируем timestamp смены статуса — только при первом переходе
    from datetime import datetime, timezone
    now = datetime.now(tz=timezone.utc)
    field_map = {"contacted": "contacted_at", "paid": "paid_at", "closed": "closed_at"}
    ts_field = field_map.get(payload.status)
    if ts_field and getattr(lead, ts_field) is None:
        setattr(lead, ts_field, now)
    lead.status = payload.status
    await session.commit()
    await session.refresh(lead)
    # Загрузим связные сущности
    user = (await session.execute(select(User).where(User.id == lead.user_id))).scalar_one()
    product = (await session.execute(select(Product).where(Product.id == lead.product_id))).scalar_one()
    channel = (await session.execute(select(Channel).where(Channel.id == product.channel_id))).scalar_one()
    return _to_out(lead, user, product, channel)


@router.delete("/{lead_id}", status_code=204, response_class=Response)
async def delete_lead(
    lead_id: int,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> Response:
    lead = (await session.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    await session.delete(lead)
    await session.commit()
    return Response(status_code=204)
