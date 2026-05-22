from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_admin, get_session
from app.models.admin import Admin
from app.models.channel import Channel
from app.models.product import Product
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.subscription import SubscriptionExtend, SubscriptionOut
from app.services import subscriptions as sub_service

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


def _to_out(
    s: Subscription,
    user: User | None,
    channel_title: str | None,
    product_name: str | None,
) -> SubscriptionOut:
    return SubscriptionOut(
        id=s.id,
        user_id=s.user_id,
        user_username=getattr(user, "username", None) if user else None,
        user_first_name=getattr(user, "first_name", None) if user else None,
        channel_id=s.channel_id,
        channel_title=channel_title,
        product_id=s.product_id,
        product_name=product_name,
        payment_id=s.payment_id,
        starts_at=s.starts_at,
        ends_at=s.ends_at,
        status=s.status,
        invite_link=s.invite_link,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


@router.get("", response_model=list[SubscriptionOut])
async def list_subscriptions(
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
    status: str | None = Query(default=None, description="active|expired|revoked|all"),
) -> list[SubscriptionOut]:
    stmt = (
        select(Subscription, User, Channel.title, Product.name)
        .join(User, User.id == Subscription.user_id)
        .join(Channel, Channel.id == Subscription.channel_id)
        .outerjoin(Product, Product.id == Subscription.product_id)
        .order_by(Subscription.id.desc())
    )
    if status and status != "all":
        stmt = stmt.where(Subscription.status == status)
    rows = (await session.execute(stmt)).all()
    return [_to_out(s, u, ct, pn) for s, u, ct, pn in rows]


@router.post("/{sub_id}/revoke", response_model=SubscriptionOut)
async def revoke(
    sub_id: int,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> SubscriptionOut:
    s = (await session.execute(select(Subscription).where(Subscription.id == sub_id))).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Subscription not found")
    await sub_service.revoke(session, s, status="revoked", notify=True)
    await session.commit()
    await session.refresh(s)
    return _to_out(s, None, None, None)


@router.post("/{sub_id}/extend", response_model=SubscriptionOut)
async def extend(
    sub_id: int,
    payload: SubscriptionExtend,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> SubscriptionOut:
    s = (await session.execute(select(Subscription).where(Subscription.id == sub_id))).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Subscription not found")
    if not (payload.days or payload.months):
        raise HTTPException(status_code=400, detail="Укажите days или months")
    await sub_service.extend(session, s, days=payload.days or 0, months=payload.months or 0)
    await session.commit()
    await session.refresh(s)
    return _to_out(s, None, None, None)
