from __future__ import annotations

import re
import secrets
import string
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.models.payment import Payment
from app.models.product import Product
from app.models.tracking_link import TrackingLink

SLUG_CHARS = string.ascii_letters + string.digits  # 62 символа
SLUG_LENGTH = 8
SLUG_PATTERN = re.compile(r"^[A-Za-z0-9_-]{4,64}$")


class TrackingLinksError(Exception):
    pass


class ConflictError(TrackingLinksError):
    pass


class InvalidSlugError(TrackingLinksError):
    pass


class GenerationError(TrackingLinksError):
    pass


@dataclass
class LinkMetrics:
    clicks: int
    unique_users: int
    leads_count: int
    payments_count: int
    revenue: Decimal


class TrackingLinksService:
    """Сервис управления трекинговыми ссылками.

    Slug — 8 символов из [A-Za-z0-9] для авто-генерации,
    [A-Za-z0-9_-]{4,64} для кастомных.

    Namespace slug + product.code общий — collision-проверка в обе стороны.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    # ---------------- Public API ----------------

    async def create(
        self,
        *,
        product_id: int,
        utm_source: str,
        utm_medium: str | None = None,
        utm_campaign: str | None = None,
        utm_content: str | None = None,
        bot_id: int | None = None,
        notes: str | None = None,
        custom_slug: str | None = None,
        created_by: int | None = None,
        funnel_id: int | None = None,
    ) -> TrackingLink:
        # Резолвим bot_id: если не указан явно — берём через канал продукта
        if bot_id is None:
            row = (
                await self.session.execute(
                    select(Product.channel_id).where(Product.id == product_id)
                )
            ).first()
            if row is not None:
                # bot_id у канала
                from app.models.channel import Channel
                ch = (
                    await self.session.execute(
                        select(Channel.bot_id).where(Channel.id == row[0])
                    )
                ).scalar_one_or_none()
                bot_id = ch

        # Генерация / валидация slug
        if custom_slug:
            slug = custom_slug.strip()
            self._validate_slug_format(slug)
            await self._check_unique(slug)
        else:
            slug = await self._generate_unique_slug()

        link = TrackingLink(
            slug=slug,
            product_id=product_id,
            bot_id=bot_id,
            utm_source=utm_source.strip(),
            utm_medium=(utm_medium or None),
            utm_campaign=(utm_campaign or None),
            utm_content=(utm_content or None),
            notes=(notes or None),
            is_active=True,
            click_count=0,
            unique_users=0,
            created_by=created_by,
            funnel_id=funnel_id,
        )
        self.session.add(link)
        await self.session.flush()
        return link

    async def find_by_slug(self, slug: str) -> TrackingLink | None:
        return (
            await self.session.execute(
                select(TrackingLink).where(TrackingLink.slug == slug)
            )
        ).scalar_one_or_none()

    async def find_by_id(self, link_id: int) -> TrackingLink | None:
        return await self.session.get(TrackingLink, link_id)

    async def list_all(
        self,
        *,
        product_id: int | None = None,
        is_active: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[TrackingLink]:
        stmt = select(TrackingLink)
        if product_id is not None:
            stmt = stmt.where(TrackingLink.product_id == product_id)
        if is_active is not None:
            stmt = stmt.where(TrackingLink.is_active.is_(is_active))
        stmt = stmt.order_by(TrackingLink.id.desc()).limit(limit).offset(offset)
        return (await self.session.execute(stmt)).scalars().all()

    async def list_for_product(self, product_id: int) -> list[TrackingLink]:
        return await self.list_all(product_id=product_id)

    async def increment_click_count(self, link_id: int) -> None:
        await self.session.execute(
            update(TrackingLink)
            .where(TrackingLink.id == link_id)
            .values(click_count=TrackingLink.click_count + 1)
        )

    async def increment_unique_users(self, link_id: int) -> None:
        await self.session.execute(
            update(TrackingLink)
            .where(TrackingLink.id == link_id)
            .values(unique_users=TrackingLink.unique_users + 1)
        )

    async def update(
        self, link_id: int, *,
        notes: str | None = None,
        is_active: bool | None = None,
        funnel_id: int | None = None,
        funnel_id_set: bool = False,  # явный флаг чтобы можно было обнулить через None
    ) -> TrackingLink | None:
        link = await self.session.get(TrackingLink, link_id)
        if link is None:
            return None
        if notes is not None:
            link.notes = notes
        if is_active is not None:
            link.is_active = is_active
        if funnel_id_set:
            link.funnel_id = funnel_id
        await self.session.flush()
        return link

    async def deactivate(self, link_id: int) -> None:
        await self.session.execute(
            update(TrackingLink).where(TrackingLink.id == link_id).values(is_active=False)
        )

    async def can_hard_delete(self, link_id: int) -> tuple[bool, dict]:
        """Проверка, можно ли удалить ссылку без потери атрибуции."""
        leads_cnt = (
            await self.session.execute(
                select(func.count())
                .select_from(Lead)
                .where(Lead.tracking_link_id == link_id)
            )
        ).scalar_one()
        pay_cnt = (
            await self.session.execute(
                select(func.count())
                .select_from(Payment)
                .where(Payment.tracking_link_id == link_id)
            )
        ).scalar_one()
        return (leads_cnt == 0 and pay_cnt == 0), {
            "leads": int(leads_cnt),
            "payments": int(pay_cnt),
        }

    async def get_metrics(self, link_id: int) -> LinkMetrics:
        """Базовые метрики ссылки."""
        link = await self.session.get(TrackingLink, link_id)
        if link is None:
            return LinkMetrics(0, 0, 0, 0, Decimal("0"))
        leads_count = (
            await self.session.execute(
                select(func.count())
                .select_from(Lead)
                .where(Lead.tracking_link_id == link_id)
            )
        ).scalar_one()
        pay_cnt = (
            await self.session.execute(
                select(func.count())
                .select_from(Payment)
                .where(Payment.tracking_link_id == link_id)
            )
        ).scalar_one()
        revenue = (
            await self.session.execute(
                select(func.coalesce(func.sum(Payment.amount), 0))
                .where(Payment.tracking_link_id == link_id)
            )
        ).scalar_one()
        return LinkMetrics(
            clicks=int(link.click_count),
            unique_users=int(link.unique_users),
            leads_count=int(leads_count),
            payments_count=int(pay_cnt),
            revenue=Decimal(revenue or 0),
        )

    # ---------------- Helpers ----------------

    async def _generate_unique_slug(self, max_attempts: int = 10) -> str:
        for _ in range(max_attempts):
            slug = "".join(secrets.choice(SLUG_CHARS) for _ in range(SLUG_LENGTH))
            if not await self._exists_in_links(slug) and not await self._conflicts_with_product_code(slug):
                return slug
        raise GenerationError("Could not generate unique slug after 10 attempts")

    @staticmethod
    def _validate_slug_format(slug: str) -> None:
        if not SLUG_PATTERN.match(slug):
            raise InvalidSlugError(
                "Slug must match [A-Za-z0-9_-]{4,64}"
            )

    async def _exists_in_links(self, slug: str) -> bool:
        row = (
            await self.session.execute(
                select(TrackingLink.id).where(TrackingLink.slug == slug)
            )
        ).first()
        return row is not None

    async def _conflicts_with_product_code(self, slug: str) -> bool:
        row = (
            await self.session.execute(
                select(Product.id).where(Product.code == slug)
            )
        ).first()
        return row is not None

    async def _check_unique(self, slug: str) -> None:
        if await self._exists_in_links(slug):
            raise ConflictError(f"Slug '{slug}' already taken by another tracking link")
        if await self._conflicts_with_product_code(slug):
            raise ConflictError(
                f"Slug '{slug}' conflicts with existing product.code"
            )


# Обратная проверка коллизии — используется в products API при create/update.
async def product_code_conflicts_with_slug(session: AsyncSession, code: str) -> bool:
    row = (
        await session.execute(
            select(TrackingLink.id).where(TrackingLink.slug == code)
        )
    ).first()
    return row is not None
