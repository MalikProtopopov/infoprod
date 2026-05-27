"""Форм-машина (form:start:, form:cancel:). Фича forms."""
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
router = Router(name="public_forms")

@router.callback_query(F.data.startswith("form:start:"))
async def cb_form_start(cb: CallbackQuery) -> None:
    if not is_enabled("forms"):
        await cb.answer("Форма недоступна", show_alert=True)
        return
    try:
        step_id = int(cb.data.split(":", 2)[2])
    except (ValueError, IndexError):
        await cb.answer("Не нашёл форму", show_alert=True)
        return
    async with SessionLocal() as session:
        user, _ = await _upsert_user(session, cb)
        entry_id = await _resolve_active_entry_id(session, user_id=user.id, step_id=step_id)
        flow = StepFlowService(session)
        result = await flow.start_form(
            user_id=user.id, step_id=step_id, funnel_entry_id=entry_id,
        )
        await session.commit()
    if result.error:
        await cb.answer("Форма сейчас недоступна", show_alert=True)
        return
    if result.messages:
        await _send_flow_messages(cb.message, result.messages)
    await cb.answer()


@router.callback_query(F.data.startswith("form:cancel:"))
async def cb_form_cancel(cb: CallbackQuery) -> None:
    if not is_enabled("forms"):
        await cb.answer()
        return
    try:
        state_id = int(cb.data.split(":", 2)[2])
    except (ValueError, IndexError):
        await cb.answer()
        return
    async with SessionLocal() as session:
        user, _ = await _upsert_user(session, cb)
        flow = StepFlowService(session)
        result = await flow.cancel_form(user_id=user.id, state_id=state_id)
        await session.commit()
    if result.messages:
        await _send_flow_messages(cb.message, result.messages)
    await cb.answer()

