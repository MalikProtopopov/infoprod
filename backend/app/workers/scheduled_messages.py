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
from app.models.funnel_step_media import FunnelStepMedia
from app.models.scheduled_message import ScheduledMessage
from app.models.user import User

logger = structlog.get_logger("scheduled_messages")

BATCH_LIMIT = 100
# После скольки неудачных попыток отправки помечаем сообщение как
# permanently cancelled. Защита от вечного спама в логах (типичный случай —
# юзер заблокировал бота или test-юзер с невалидным telegram_user_id).
MAX_ATTEMPTS = 5


def _build_keyboard(step_buttons: Any | None, include_unsubscribe: bool = True):
    """Inline-кнопки из step.buttons (json) + универсальная кнопка отписки.

    Фильтруем кнопки, у которых ни url, ни callback_data — Telegram
    отвергает такие кнопки и роняет весь send_message ошибкой
    'Text buttons are unallowed in the inline keyboard'.
    """
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard: list[list[InlineKeyboardButton]] = []
    if step_buttons:
        for row in step_buttons:
            if not isinstance(row, list):
                continue
            cleaned: list[InlineKeyboardButton] = []
            for btn in row:
                if not isinstance(btn, dict):
                    continue
                url = (btn.get("url") or "").strip()
                cb = (btn.get("callback_data") or "").strip()
                text_btn = btn.get("text") or "?"
                if not url and not cb:
                    # Пустая «текстовая» кнопка — Telegram её не примет.
                    continue
                cleaned.append(InlineKeyboardButton(
                    text=text_btn,
                    url=url or None,
                    callback_data=cb or None,
                ))
            if cleaned:
                keyboard.append(cleaned)
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
    """Увеличивает attempts + error. После MAX_ATTEMPTS — помечает cancelled,
    чтобы worker перестал бесконечно повторять заведомо безнадёжные сообщения
    (битый telegram_user_id, бот заблокирован юзером и т.п.)."""
    # Сначала прочитаем текущее значение attempts
    msg = await session.get(ScheduledMessage, msg_id)
    next_attempts = (msg.attempts if msg else 0) + 1
    values: dict = {"error": error[:1000], "attempts": next_attempts}
    if next_attempts >= MAX_ATTEMPTS:
        values["cancelled_at"] = datetime.now(tz=timezone.utc)
        values["cancel_reason"] = f"max_attempts_reached ({error[:60]})"
    await session.execute(
        update(ScheduledMessage)
        .where(ScheduledMessage.id == msg_id)
        .values(**values)
    )


def _media_input(media: FunnelStepMedia, *, force_disk: bool = False):
    """Возвращает аргумент для aiogram: telegram_file_id (str) если есть кэш,
    иначе FSInputFile с диска.

    `force_disk=True` — игнорирует cache и грузит файл с диска. Используется
    в retry после ошибки "wrong file identifier" (typично — file_id из-под
    другого бота при смене bot_id у воронки).
    """
    from aiogram.types import FSInputFile
    if not force_disk and media.telegram_file_id:
        return media.telegram_file_id
    return FSInputFile(media.storage_path, filename=media.original_filename or None)


def _is_bad_file_id_error(err: Exception) -> bool:
    """Telegram отвечает 400 'wrong file identifier' если file_id невалиден
    или принадлежит другому боту. Хотим распознать и повторить с диска."""
    msg = str(err).lower()
    return "wrong file identifier" in msg or "wrong file_id" in msg


async def _reset_file_id(session: AsyncSession, media_id: int) -> None:
    """Снести закешированный file_id перед retry с диска."""
    await session.execute(
        update(FunnelStepMedia)
        .where(FunnelStepMedia.id == media_id)
        .values(telegram_file_id=None)
    )


def _extract_file_id(message, media_type: str) -> str | None:
    """Извлекает file_id из ответа Telegram по типу медиа."""
    if media_type == "photo":
        photos = getattr(message, "photo", None)
        if photos:
            return photos[-1].file_id
    if media_type == "video":
        v = getattr(message, "video", None)
        if v:
            return v.file_id
    if media_type == "animation":
        a = getattr(message, "animation", None)
        if a:
            return a.file_id
    if media_type == "audio":
        au = getattr(message, "audio", None)
        if au:
            return au.file_id
    if media_type == "voice":
        vo = getattr(message, "voice", None)
        if vo:
            return vo.file_id
    doc = getattr(message, "document", None)
    if doc:
        return doc.file_id
    return None


async def _persist_file_id(session: AsyncSession, media_id: int, file_id: str | None) -> None:
    if not file_id:
        return
    await session.execute(
        update(FunnelStepMedia)
        .where(FunnelStepMedia.id == media_id, FunnelStepMedia.telegram_file_id.is_(None))
        .values(telegram_file_id=file_id)
    )


async def _send_single_media(
    aio_bot,
    chat_id: int,
    media: FunnelStepMedia,
    text: str,
    keyboard,
    parse_mode: str | None,
    session: AsyncSession,
) -> None:
    """Отправляет один файл с текстом-caption и inline-кнопками.

    Если у media закеширован чужой telegram_file_id (например, был
    закеширован под другим ботом до смены bot_id у funnel) — Telegram
    отвергнет с "wrong file identifier". Ловим эту ошибку, сбрасываем
    кеш и повторяем с диска.
    """
    caption = text  # текст шага идёт как caption

    async def _do_send(force_disk: bool):
        src = _media_input(media, force_disk=force_disk)
        if media.media_type == "photo":
            return await aio_bot.send_photo(chat_id, src, caption=caption, parse_mode=parse_mode, reply_markup=keyboard)
        if media.media_type == "video":
            return await aio_bot.send_video(chat_id, src, caption=caption, parse_mode=parse_mode, reply_markup=keyboard)
        if media.media_type == "animation":
            return await aio_bot.send_animation(chat_id, src, caption=caption, parse_mode=parse_mode, reply_markup=keyboard)
        if media.media_type == "audio":
            return await aio_bot.send_audio(chat_id, src, caption=caption, parse_mode=parse_mode, reply_markup=keyboard)
        if media.media_type == "voice":
            # voice не поддерживает caption и parse_mode — шлём текст отдельным сообщением.
            await aio_bot.send_message(chat_id, text, parse_mode=parse_mode, reply_markup=keyboard,
                                       disable_web_page_preview=True)
            return await aio_bot.send_voice(chat_id, src)
        # document
        return await aio_bot.send_document(chat_id, src, caption=caption, parse_mode=parse_mode, reply_markup=keyboard)

    sent = None
    try:
        sent = await _do_send(force_disk=False)
    except Exception as e:  # noqa: BLE001
        if media.telegram_file_id and _is_bad_file_id_error(e):
            logger.warning(
                "step_media.stale_file_id media_id=%s — retrying from disk", media.id,
            )
            await _reset_file_id(session, media.id)
            media.telegram_file_id = None
            sent = await _do_send(force_disk=True)
        else:
            raise

    fid = _extract_file_id(sent, media.media_type) if sent else None
    await _persist_file_id(session, media.id, fid)


async def _send_media_group_then_text(
    aio_bot,
    chat_id: int,
    media_rows: list[FunnelStepMedia],
    text: str,
    keyboard,
    parse_mode: str | None,
    session: AsyncSession,
) -> None:
    """Шлёт text-сообщение с кнопками ПЕРВЫМ, потом media-group без подписи.

    Порядок выбран осознанно:
    - Если кнопки невалидны / текст слишком длинный — упадём сразу на тексте,
      media-group не отправится дублем при retry.
    - Caption media-group ограничен 1024 символами (text может быть до 4096),
      а кнопки к media-group вообще невозможны — поэтому без compromise
      шлём двумя сообщениями.
    """
    from aiogram.types import (
        InputMediaAnimation,
        InputMediaAudio,
        InputMediaDocument,
        InputMediaPhoto,
        InputMediaVideo,
    )

    # 1) Текст + кнопки — первым (хрупкое место).
    if text or keyboard:
        await aio_bot.send_message(
            chat_id, text,
            parse_mode=parse_mode,
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )

    # 2) Media-group — после успеха текста.
    def _build_items(force_disk: bool):
        out = []
        for m in media_rows:
            src = _media_input(m, force_disk=force_disk)
            cap = m.caption  # per-item caption
            if m.media_type == "photo":
                out.append(InputMediaPhoto(media=src, caption=cap, parse_mode=parse_mode if cap else None))
            elif m.media_type == "video":
                out.append(InputMediaVideo(media=src, caption=cap, parse_mode=parse_mode if cap else None))
            elif m.media_type == "animation":
                out.append(InputMediaAnimation(media=src, caption=cap, parse_mode=parse_mode if cap else None))
            elif m.media_type == "audio":
                out.append(InputMediaAudio(media=src, caption=cap, parse_mode=parse_mode if cap else None))
            else:  # document / voice (voice не входит в group по спеке TG, но fallback на document)
                out.append(InputMediaDocument(media=src, caption=cap, parse_mode=parse_mode if cap else None))
        return out

    try:
        sent_messages = await aio_bot.send_media_group(chat_id, media=_build_items(force_disk=False))
    except Exception as e:  # noqa: BLE001
        if any(m.telegram_file_id for m in media_rows) and _is_bad_file_id_error(e):
            logger.warning(
                "media_group.stale_file_id — retrying %d items from disk",
                len(media_rows),
            )
            for m in media_rows:
                if m.telegram_file_id:
                    await _reset_file_id(session, m.id)
                    m.telegram_file_id = None
            sent_messages = await aio_bot.send_media_group(chat_id, media=_build_items(force_disk=True))
        else:
            raise

    # Сохраняем file_id для каждого ответа
    for media_row, sent in zip(media_rows, sent_messages):
        fid = _extract_file_id(sent, media_row.media_type)
        await _persist_file_id(session, media_row.id, fid)


async def process_due_messages(
    session: AsyncSession,
    *,
    entry_id: int | None = None,
) -> dict[str, int]:
    """Один проход воркера.

    Если передан `entry_id` — обрабатываем только сообщения этого entry
    (используется для немедленной отправки D0 при старте воронки, чтобы
    юзер не ждал тика scheduler'а).

    Возвращает dict со счётчиками: sent / cancelled / failed.
    """
    from app.bot import manager as bot_manager
    from app.services.funnels import FunnelsService
    from app.services.lead_magnets import LeadMagnetsService

    funnels_svc = FunnelsService(session)
    lm_svc = LeadMagnetsService(session)

    now = datetime.now(tz=timezone.utc)
    stmt = (
        select(ScheduledMessage)
        .where(
            ScheduledMessage.scheduled_at <= now,
            ScheduledMessage.sent_at.is_(None),
            ScheduledMessage.cancelled_at.is_(None),
        )
        .order_by(ScheduledMessage.scheduled_at.asc())
        .limit(BATCH_LIMIT)
    )
    if entry_id is not None:
        stmt = stmt.where(ScheduledMessage.funnel_entry_id == entry_id)
    rows = (await session.execute(stmt)).scalars().all()

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
            parse_mode = step.parse_mode or "HTML"

            # Загружаем медиа шага. Если их 0 — старая логика (текст +
            # опц. legacy lead_magnet). Если 1 — одиночное медиа с
            # caption+кнопками. Если ≥2 — media-group, потом отдельное
            # text-сообщение с кнопками (caption у media-group лимит 1024
            # символа, кнопки к media-group вообще нельзя).
            step_media = (
                await session.execute(
                    select(FunnelStepMedia)
                    .where(FunnelStepMedia.funnel_step_id == step.id)
                    .order_by(FunnelStepMedia.order_idx)
                )
            ).scalars().all()

            if not step_media:
                await aio_bot.send_message(
                    user.telegram_user_id, text,
                    parse_mode=parse_mode,
                    reply_markup=keyboard,
                    disable_web_page_preview=True,
                )
                if step.lead_magnet_id:
                    await lm_svc.send_to_user(
                        bot=aio_bot,
                        user_telegram_id=user.telegram_user_id,
                        lead_magnet_id=step.lead_magnet_id,
                    )
            elif len(step_media) == 1:
                await _send_single_media(
                    aio_bot, user.telegram_user_id, step_media[0],
                    text, keyboard, parse_mode, session,
                )
            else:
                await _send_media_group_then_text(
                    aio_bot, user.telegram_user_id, list(step_media),
                    text, keyboard, parse_mode, session,
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
