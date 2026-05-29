"""Запуск воронки из кнопки (funnel:start:). Фича funnels."""
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
from app.models.funnel_event import FunnelEvent
from app.models.funnel_step import FunnelStep
from app.models.lead import Lead
from app.models.product import Product
from app.models.subscription import Subscription
from app.models.tracking_link import TrackingLink
from app.models.user import User
from app.services.step_flow import FlowMessage, FlowResult, StepFlowService
from app.services.tracking_links import TrackingLinksService

logger = logging.getLogger(__name__)
router = Router(name="public_funnels")

@router.callback_query(F.data.startswith("funnel:start:"))
async def cb_funnel_start(cb: CallbackQuery) -> None:
    """Запустить указанную воронку для текущего юзера.

    Идемпотентно: если юзер уже в этой воронке (status='active') — повторно
    не стартует, отвечаем подтверждением.
    """
    if not is_enabled("funnels"):
        await cb.answer("Недоступно", show_alert=True)
        return
    try:
        funnel_id = int(cb.data.split(":", 2)[2])
    except (ValueError, IndexError):
        await cb.answer("Воронка не найдена", show_alert=True)
        return

    new_entry_id: int | None = None
    async with SessionLocal() as session:
        user, _ = await _upsert_user(session, cb)
        from app.services.funnels import FunnelsService
        funnels = FunnelsService(session)
        existing = await funnels.find_active_entry(user_id=user.id, funnel_id=funnel_id)
        if existing is None:
            entry = await funnels.start_for_user(
                user_id=user.id,
                funnel_id=funnel_id,
                source="button_click",
                source_ref=None,
            )
            if entry is None:
                await session.rollback()
                await cb.answer("Не удалось запустить воронку", show_alert=True)
                return
            new_entry_id = entry.id
        await session.commit()

    await cb.answer("Подписал вас на серию сообщений ✓")
    if new_entry_id is not None:
        await _flush_funnel_entry_now(new_entry_id)


def _find_track_button(buttons, step_id: int, key: str) -> tuple[str | None, str | None]:
    """Находит конфиг track-кнопки (tag, reply_text) по её callback_data."""
    cd = f"track:{step_id}:{key}"
    if not buttons:
        return None, None
    for row in buttons:
        if not isinstance(row, list):
            continue
        for b in row:
            if isinstance(b, dict) and (b.get("callback_data") or "") == cd:
                tag = (b.get("tag") or "").strip() or None
                reply = (b.get("reply_text") or "").strip() or None
                return tag, reply
    return None, None


@router.callback_query(F.data.startswith("track:"))
async def cb_track(cb: CallbackQuery) -> None:
    """Кнопка-отметка: фиксирует клик, ставит тег сегмента, опц. отвечает текстом.

    callback_data: track:{step_id}:{key}. tag/reply_text лежат в самом
    описании кнопки (step.buttons), сюда не передаются.
    """
    if not is_enabled("funnels"):
        await cb.answer("Недоступно", show_alert=True)
        return
    parts = (cb.data or "").split(":")
    if len(parts) < 3:
        await cb.answer()
        return
    try:
        step_id = int(parts[1])
    except ValueError:
        await cb.answer()
        return
    key = parts[2]

    reply_text: str | None = None
    async with SessionLocal() as session:
        user, _ = await _upsert_user(session, cb)
        step = await session.get(FunnelStep, step_id)
        if step is None:
            await cb.answer("Кнопка устарела")
            return
        tag, reply_text = _find_track_button(step.buttons, step_id, key)
        from app.services.funnels import FunnelsService
        funnels = FunnelsService(session)
        entry = await funnels.find_active_entry(user_id=user.id, funnel_id=step.funnel_id)
        if entry is not None:
            session.add(FunnelEvent(
                funnel_entry_id=entry.id,
                user_id=user.id,
                funnel_step_id=step_id,
                event_type="click",
                key=key,
            ))
            if tag:
                tags = list(entry.tags or [])
                if tag not in tags:
                    tags.append(tag)
                    entry.tags = tags
        await session.commit()

    await cb.answer("Принято ✓")
    if reply_text:
        try:
            await cb.message.answer(
                reply_text, parse_mode=ParseMode.HTML, disable_web_page_preview=True
            )
        except Exception:  # noqa: BLE001
            logger.warning("track.reply_failed step_id=%s key=%s", step_id, key)

