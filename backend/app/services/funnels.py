"""FunnelsService — create/update funnel, add_step, start_for_user, cancel."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.funnel import Funnel
from app.models.funnel_entry import FunnelEntry
from app.models.funnel_step import FunnelStep
from app.models.scheduled_message import ScheduledMessage
from app.models.user import User

logger = structlog.get_logger("funnels")


class FunnelNotActiveError(Exception):
    pass


class FunnelsService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ───────── CRUD ─────────

    async def create(
        self,
        *,
        name: str,
        product_id: int,
        description: str | None = None,
        bot_id: int | None = None,
        ttl_days: int = 90,
        cancel_on_payment: bool = True,
        created_by: int | None = None,
        steps: list[dict[str, Any]] | None = None,
    ) -> Funnel:
        f = Funnel(
            name=name, description=description, product_id=product_id,
            bot_id=bot_id, ttl_days=ttl_days,
            cancel_on_payment=cancel_on_payment, created_by=created_by,
        )
        self.session.add(f)
        await self.session.flush()

        if steps:
            for idx, st in enumerate(steps):
                step = FunnelStep(
                    funnel_id=f.id,
                    order_idx=st.get("order_idx", idx),
                    delay_minutes=int(st["delay_minutes"]),
                    message_text=st["message_text"],
                    parse_mode=st.get("parse_mode", "HTML"),
                    lead_magnet_id=st.get("lead_magnet_id"),
                    buttons=st.get("buttons"),
                    is_active=st.get("is_active", True),
                )
                self.session.add(step)
            await self.session.flush()
        return f

    async def update(self, funnel_id: int, **fields) -> Funnel | None:
        f = await self.session.get(Funnel, funnel_id)
        if f is None:
            return None
        for k, v in fields.items():
            if v is not None and hasattr(f, k):
                setattr(f, k, v)
        return f

    async def add_step(
        self, funnel_id: int, *, order_idx: int, delay_minutes: int,
        message_text: str, lead_magnet_id: int | None = None,
        buttons: Any = None, parse_mode: str = "HTML",
    ) -> FunnelStep:
        step = FunnelStep(
            funnel_id=funnel_id, order_idx=order_idx,
            delay_minutes=delay_minutes, message_text=message_text,
            parse_mode=parse_mode, lead_magnet_id=lead_magnet_id, buttons=buttons,
        )
        self.session.add(step)
        await self.session.flush()
        return step

    async def reorder_steps(self, funnel_id: int, ordered_step_ids: list[int]) -> None:
        """Перенумеровать шаги. ordered_step_ids[0] получит order_idx=0 и т.д."""
        for new_idx, step_id in enumerate(ordered_step_ids):
            await self.session.execute(
                update(FunnelStep)
                .where(FunnelStep.id == step_id, FunnelStep.funnel_id == funnel_id)
                .values(order_idx=new_idx)
            )

    # ───────── Запуск воронки ─────────

    async def find_active_entry(self, *, user_id: int, funnel_id: int) -> FunnelEntry | None:
        return (
            await self.session.execute(
                select(FunnelEntry).where(
                    FunnelEntry.user_id == user_id,
                    FunnelEntry.funnel_id == funnel_id,
                    FunnelEntry.status == "active",
                )
            )
        ).scalar_one_or_none()

    async def start_for_user(
        self,
        *,
        user_id: int,
        funnel_id: int,
        source: str,
        source_ref: int | None = None,
    ) -> FunnelEntry | None:
        """Создаёт FunnelEntry и плановые сообщения для всех шагов.

        Возвращает None если воронка неактивна, юзер отписан, или entry уже есть.
        """
        funnel = await self.session.get(Funnel, funnel_id)
        if funnel is None or not funnel.is_active:
            return None

        user = await self.session.get(User, user_id)
        if user is None or not user.notifications_enabled:
            return None

        # Уже подписан?
        existing = await self.find_active_entry(user_id=user_id, funnel_id=funnel_id)
        if existing is not None:
            return existing

        now = datetime.now(tz=timezone.utc)
        entry = FunnelEntry(
            funnel_id=funnel_id,
            user_id=user_id,
            source=source,
            source_ref=source_ref,
            started_at=now,
            status="active",
        )
        self.session.add(entry)
        await self.session.flush()

        # Загружаем шаги
        steps = (
            await self.session.execute(
                select(FunnelStep)
                .where(FunnelStep.funnel_id == funnel_id, FunnelStep.is_active.is_(True))
                .order_by(FunnelStep.order_idx)
            )
        ).scalars().all()

        for step in steps:
            sched = ScheduledMessage(
                user_id=user_id,
                funnel_entry_id=entry.id,
                funnel_step_id=step.id,
                scheduled_at=now + timedelta(minutes=step.delay_minutes),
            )
            self.session.add(sched)

        await self.session.flush()
        logger.info("funnel.started", funnel_id=funnel_id, user_id=user_id, source=source,
                    steps_count=len(steps))
        return entry

    # ───────── Отмена ─────────

    async def cancel_entry(self, entry_id: int, *, reason: str = "manual") -> bool:
        entry = await self.session.get(FunnelEntry, entry_id)
        if entry is None or entry.status != "active":
            return False
        now = datetime.now(tz=timezone.utc)
        entry.status = "cancelled"
        entry.cancelled_at = now
        entry.cancel_reason = reason

        # Отменяем недотправленные сообщения
        await self.session.execute(
            update(ScheduledMessage)
            .where(
                ScheduledMessage.funnel_entry_id == entry_id,
                ScheduledMessage.sent_at.is_(None),
                ScheduledMessage.cancelled_at.is_(None),
            )
            .values(cancelled_at=now, cancel_reason=reason)
        )
        logger.info("funnel.cancelled", entry_id=entry_id, reason=reason)
        return True

    async def cancel_entries_for_user_on_payment(
        self, *, user_id: int, product_id: int,
    ) -> int:
        """Отменяет все активные FunnelEntry юзера для воронок этого продукта
        у которых cancel_on_payment=true.

        Возвращает кол-во отменённых entry.
        """
        rows = (
            await self.session.execute(
                select(FunnelEntry, Funnel)
                .join(Funnel, Funnel.id == FunnelEntry.funnel_id)
                .where(
                    FunnelEntry.user_id == user_id,
                    FunnelEntry.status == "active",
                    Funnel.product_id == product_id,
                    Funnel.cancel_on_payment.is_(True),
                )
            )
        ).all()
        count = 0
        for entry, _funnel in rows:
            if await self.cancel_entry(entry.id, reason="payment_received"):
                count += 1
        return count

    async def check_and_complete(self, entry_id: int) -> bool:
        """Если у entry все шаги отправлены — переводит в completed."""
        entry = await self.session.get(FunnelEntry, entry_id)
        if entry is None or entry.status != "active":
            return False
        # Остались ли неотправленные?
        unsent = (
            await self.session.execute(
                select(ScheduledMessage.id).where(
                    ScheduledMessage.funnel_entry_id == entry_id,
                    ScheduledMessage.sent_at.is_(None),
                    ScheduledMessage.cancelled_at.is_(None),
                ).limit(1)
            )
        ).scalar_one_or_none()
        if unsent is not None:
            return False
        entry.status = "completed"
        entry.completed_at = datetime.now(tz=timezone.utc)
        logger.info("funnel.completed", entry_id=entry_id)
        return True
