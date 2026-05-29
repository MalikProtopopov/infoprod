"""Хендлер заявок (lead:). Роутер подключается при фиче leads."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts
from app.bot.handlers.common import (
    CURRENT_LINK_TTL,
    MAIN_MENU_BTN,
    _catalog_kb,
    _flow_buttons_to_markup,
    _flush_funnel_entry_now,
    _main_reply_kb,
    _nav_inline_kb,
    _product_kb,
    _resolve_active_entry_id,
    _resolve_bot_id,
    _send_catalog,
    _send_flow_messages,
    _send_product_card,
    _set_current_link,
    _set_first_touch,
    _upsert_user,
)
from app.core.features import is_enabled
from app.db.session import SessionLocal
from app.models.bot import Bot as BotModel
from app.models.channel import Channel
from app.models.lead import Lead
from app.models.product import Product
from app.models.subscription import Subscription
from app.models.tracking_link import TrackingLink
from app.models.user import User
from app.services.step_flow import FlowMessage, FlowResult, StepFlowService
from app.services.tracking_links import TrackingLinksService

logger = logging.getLogger(__name__)
router = Router(name="public_leads")

@router.callback_query(F.data.startswith("lead:"))
async def cb_lead(cb: CallbackQuery) -> None:
    if not is_enabled("leads"):
        await cb.answer("Недоступно", show_alert=True)
        return
    try:
        product_id = int(cb.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await cb.answer("Кнопка не настроена", show_alert=True)
        return
    async with SessionLocal() as session:
        user, _ = await _upsert_user(session, cb)
        product = (
            await session.execute(
                select(Product).where(Product.id == product_id, Product.is_active.is_(True))
            )
        ).scalar_one_or_none()
        if not product:
            await cb.answer(texts.PRODUCT_NOT_FOUND, show_alert=True)
            return

        # Берём current_tracking_link если контекст свежий (TTL 30 мин)
        tracking_link: TrackingLink | None = None
        if user.current_tracking_link_id and user.current_link_set_at:
            now = datetime.now(tz=timezone.utc)
            set_at = user.current_link_set_at
            if set_at.tzinfo is None:
                set_at = set_at.replace(tzinfo=timezone.utc)
            if (now - set_at) <= CURRENT_LINK_TTL:
                tracking_link = await session.get(TrackingLink, user.current_tracking_link_id)
                # деактивированная ссылка не наследуется в lead — но click_count уже зафиксирован
                if tracking_link and not tracking_link.is_active:
                    tracking_link = None

        lead = Lead(
            user_id=user.id,
            product_id=product.id,
            status="new",
            tracking_link_id=tracking_link.id if tracking_link else None,
            utm_source=tracking_link.utm_source if tracking_link else None,
            utm_medium=tracking_link.utm_medium if tracking_link else None,
            utm_campaign=tracking_link.utm_campaign if tracking_link else None,
        )
        session.add(lead)
        await session.flush()

        # NEW: автозапуск default-воронки продукта
        new_entry_id: int | None = None
        if product.default_funnel_id and is_enabled("funnels"):
            from app.services.funnels import FunnelsService
            funnels = FunnelsService(session)
            entry = await funnels.start_for_user(
                user_id=user.id,
                funnel_id=product.default_funnel_id,
                source="lead_created",
                source_ref=lead.id,
            )
            new_entry_id = entry.id if entry is not None else None

        await session.commit()

    # Если воронка не стартует — показываем навигацию, чтобы не было тупика.
    # Если стартует — D0 воронки сам придёт следующим сообщением, меню лишнее.
    lead_kb = None if new_entry_id is not None else _nav_inline_kb()
    await cb.message.answer(texts.LEAD_SENT, reply_markup=lead_kb)
    await cb.answer("Заявка отправлена")
    if new_entry_id is not None:
        await _flush_funnel_entry_now(new_entry_id)

