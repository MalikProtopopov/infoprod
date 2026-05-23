"""Воркер отложенных сообщений (follow-up из воронок).

Запускается каждые N минут через APScheduler, выбирает scheduled_messages.scheduled_at <= now,
отправляет, проставляет sent_at/cancelled_at/error.

Проверки перед отправкой:
- user.notifications_enabled
- funnel_entry.status == 'active'
- bot ещё активен (есть в bot_manager)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.funnel import Funnel
from app.models.funnel_entry import FunnelEntry
from app.models.funnel_step import FunnelStep
from app.models.scheduled_message import ScheduledMessage
from app.models.user import User

logger = structlog.get_logger("scheduled_messages")

BATCH_LIMIT = 100


def _build_keyboard(step_buttons: Any | None, include_unsubscribe: bool = True):
    """Inline-кнопки из step.buttons (json) + универсальная кнопка отписки."""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard: list[list[InlineKeyboardButton]] = []
    if step_buttons:
        for row in step_buttons:
            if isinstance(row, list):
                keyboard.append([
                    InlineKeyboardButton(
                        text=btn.get("text", "?"),
                        callback_data=btn.get("callback_data"),
                        url=btn.get("url"),
                    ) for btn in row if isinstance(btn, dict)
                ])
    if include_unsubscribe:
        keyboard.append([
            InlineKeyboardButton(
                text="🔕 Не присылать напоминания",
                callback_data="unsubscribe_notifications",
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def _render_template(text: str, user: User) -> str:
    """Минимальный шаблонизатор: {first_name}, {username}."""
    return (
        text
        .replace("{first_name}", user.first_name or "")
        .replace("{username}", user.username or "")
    )


async def _mark_sent(session: AsyncSession, msg_id: int) -> None:
    await session.execute(
        update(ScheduledMessage)
        .where(ScheduledMessage.id == msg_id)
        .values(sent_at=datetime.now(tz=timezone.utc))
    )


async def _mark_cancelled(session: AsyncSession, msg_id: int, reason: str) -> None:
    await session.execute(
        update(ScheduledMessage)
        .where(ScheduledMessage.id == msg_id)
        .values(cancelled_at=datetime.now(tz=timezone.utc), cancel_reason=reason)
    )


async def _mark_failed(session: AsyncSession, msg_id: int, error: str) -> None:
    await session.execute(
        update(ScheduledMessage)
        .where(ScheduledMessage.id == msg_id)
        .values(error=error[:1000], attempts=ScheduledMessage.attempts + 1)
    )


async def process_due_messages(session: AsyncSession) -> dict[str, int]:
    """Один проход воркера.

    Возвращает dict со счётчиками: sent / cancelled / failed.
    """
    from app.bot import manager as bot_manager
    from app.services.funnels import FunnelsService
    from app.services.lead_magnets import LeadMagnetsService

    funnels_svc = FunnelsService(session)
    lm_svc = LeadMagnetsService(session)

    now = datetime.now(tz=timezone.utc)
    rows = (
        await session.execute(
            select(ScheduledMessage)
            .where(
                ScheduledMessage.scheduled_at <= now,
                ScheduledMessage.sent_at.is_(None),
                ScheduledMessage.cancelled_at.is_(None),
            )
            .order_by(ScheduledMessage.scheduled_at.asc())
            .limit(BATCH_LIMIT)
        )
    ).scalars().all()

    stats = {"sent": 0, "cancelled": 0, "failed": 0}

    for msg in rows:
        try:
            user = await session.get(User, msg.user_id)
            if user is None:
                await _mark_cancelled(session, msg.id, "user_missing")
                stats["cancelled"] += 1
                continue
            if not user.notifications_enabled:
                await _mark_cancelled(session, msg.id, "user_unsubscribed")
                stats["cancelled"] += 1
                continue

            # Связано с воронкой? Проверяем что активна
            entry: FunnelEntry | None = None
            step: FunnelStep | None = None
            funnel: Funnel | None = None
            if msg.funnel_entry_id:
                entry = await session.get(FunnelEntry, msg.funnel_entry_id)
                if entry is None or entry.status != "active":
                    await _mark_cancelled(session, msg.id, "entry_inactive")
                    stats["cancelled"] += 1
                    continue
                funnel = await session.get(Funnel, entry.funnel_id)
                if funnel is None or not funnel.is_active:
                    await _mark_cancelled(session, msg.id, "funnel_inactive")
                    stats["cancelled"] += 1
                    continue
                # TTL проверка
                age = (now - entry.started_at).days
                if funnel.ttl_days and age > funnel.ttl_days:
                    await funnels_svc.cancel_entry(entry.id, reason="ttl_expired")
                    stats["cancelled"] += 1
                    continue
                if msg.funnel_step_id:
                    step = await session.get(FunnelStep, msg.funnel_step_id)

            # Получаем bot для отправки
            bot_id = funnel.bot_id if funnel else None
            aio_bot = bot_manager.get_aiogram_bot(bot_id) if bot_id else None
            if aio_bot is None:
                # Если у funnel не привязан bot — берём первый активный
                # (best-effort, без явной ошибки)
                aio_bot = _any_active_bot(bot_manager)
            if aio_bot is None:
                await _mark_failed(session, msg.id, "no_active_bot")
                stats["failed"] += 1
                continue

            if step is None:
                # Системный template-only сообщение — пропускаем (для будущих расширений)
                await _mark_cancelled(session, msg.id, "no_step")
                stats["cancelled"] += 1
                continue

            text = _render_template(step.message_text, user)
            keyboard = _build_keyboard(step.buttons)

            await aio_bot.send_message(
                user.telegram_user_id, text,
                parse_mode=step.parse_mode or "HTML",
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )

            # Лидмагнит — отдельным сообщением
            if step.lead_magnet_id:
                await lm_svc.send_to_user(
                    bot=aio_bot,
                    user_telegram_id=user.telegram_user_id,
                    lead_magnet_id=step.lead_magnet_id,
                )

            await _mark_sent(session, msg.id)
            stats["sent"] += 1

            # Проверяем завершение entry
            if entry is not None:
                await funnels_svc.check_and_complete(entry.id)

        except Exception as e:  # noqa: BLE001
            logger.exception("scheduled_message.failed", id=msg.id, error=str(e))
            await _mark_failed(session, msg.id, str(e))
            stats["failed"] += 1

    await session.commit()
    if any(stats.values()):
        logger.info("scheduled_messages.processed", **stats, batch=len(rows))
    return stats


def _any_active_bot(bot_manager) -> Any | None:
    runners = getattr(bot_manager, "_runners", {})
    for r in runners.values():
        return getattr(r, "bot", None)
    return None
