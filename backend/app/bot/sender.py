"""Универсальная отправка медиа в бота (одиночное / альбом / кружок / голос).

Duck-typed по медиа-строкам (ProductMedia / FunnelStepMedia): нужны атрибуты
`media_type`, `storage_path`, `original_filename`, `telegram_file_id`, `caption`, `id`.
Кэш telegram_file_id переиспользуется (не перезаливаем файл на каждого юзера);
при «wrong file identifier» (file_id из-под другого бота) — retry с диска.

`on_file_id(media_id, file_id)` — опциональный async-колбэк для сохранения file_id.
"""
from __future__ import annotations

from typing import Awaitable, Callable, Optional

import structlog

logger = structlog.get_logger("bot_sender")

OnFileId = Optional[Callable[[int, str], Awaitable[None]]]

# Telegram-лимит подписи к медиа — 1024 символа (для текста сообщения — 4096).
# Длиннее — подпись не помещается, шлём медиа без неё, текст отдельным сообщением.
MEDIA_CAPTION_LIMIT = 1024


def caption_too_long(text: str | None) -> bool:
    return bool(text) and len(text) > MEDIA_CAPTION_LIMIT


def _src(media, *, force_disk: bool = False):
    from aiogram.types import FSInputFile

    if not force_disk and media.telegram_file_id:
        return media.telegram_file_id
    return FSInputFile(media.storage_path, filename=media.original_filename or None)


def _is_bad_file_id(err: Exception) -> bool:
    msg = str(err).lower()
    return "wrong file identifier" in msg or "wrong file_id" in msg


def _extract_file_id(message, media_type: str) -> str | None:
    attr = {
        "photo": "photo",
        "video": "video",
        "animation": "animation",
        "audio": "audio",
        "voice": "voice",
        "video_note": "video_note",
        "document": "document",
    }.get(media_type, "document")
    val = getattr(message, attr, None)
    if attr == "photo" and val:
        return val[-1].file_id  # массив размеров — берём наибольший
    if val:
        return getattr(val, "file_id", None)
    doc = getattr(message, "document", None)
    return getattr(doc, "file_id", None) if doc else None


async def send_media_item(
    bot,
    chat_id: int,
    media,
    *,
    caption: str | None = None,
    parse_mode: str | None = "HTML",
    reply_markup=None,
    on_file_id: OnFileId = None,
):
    """Отправить одно медиа. video_note — без подписи (Telegram-ограничение)."""

    async def _do(force_disk: bool):
        src = _src(media, force_disk=force_disk)
        mt = media.media_type
        if mt == "photo":
            return await bot.send_photo(chat_id, src, caption=caption, parse_mode=parse_mode, reply_markup=reply_markup)
        if mt == "video":
            return await bot.send_video(chat_id, src, caption=caption, parse_mode=parse_mode, reply_markup=reply_markup)
        if mt == "animation":
            return await bot.send_animation(chat_id, src, caption=caption, parse_mode=parse_mode, reply_markup=reply_markup)
        if mt == "audio":
            return await bot.send_audio(chat_id, src, caption=caption, parse_mode=parse_mode, reply_markup=reply_markup)
        if mt == "voice":
            return await bot.send_voice(chat_id, src, caption=caption, parse_mode=parse_mode, reply_markup=reply_markup)
        if mt == "video_note":
            # У кружка нет подписи; reply_markup допустим.
            return await bot.send_video_note(chat_id, src, reply_markup=reply_markup)
        return await bot.send_document(chat_id, src, caption=caption, parse_mode=parse_mode, reply_markup=reply_markup)

    try:
        sent = await _do(force_disk=False)
    except Exception as e:  # noqa: BLE001
        if media.telegram_file_id and _is_bad_file_id(e):
            logger.warning("sender.stale_file_id", media_id=getattr(media, "id", None))
            media.telegram_file_id = None
            sent = await _do(force_disk=True)
        else:
            raise

    if on_file_id and sent:
        fid = _extract_file_id(sent, media.media_type)
        if fid:
            await on_file_id(media.id, fid)
    return sent


async def send_media_group(
    bot,
    chat_id: int,
    media_rows: list,
    *,
    parse_mode: str | None = "HTML",
    on_file_id: OnFileId = None,
):
    """Отправить альбом (2..10 фото/видео/анимаций/документов). Подпись — per-item."""
    from aiogram.types import (
        InputMediaAnimation,
        InputMediaAudio,
        InputMediaDocument,
        InputMediaPhoto,
        InputMediaVideo,
    )

    def _build(force_disk: bool):
        cls_by_type = {
            "photo": InputMediaPhoto,
            "video": InputMediaVideo,
            "animation": InputMediaAnimation,
            "audio": InputMediaAudio,
        }
        out = []
        for m in media_rows:
            cls = cls_by_type.get(m.media_type, InputMediaDocument)
            cap = m.caption
            out.append(cls(media=_src(m, force_disk=force_disk), caption=cap, parse_mode=parse_mode if cap else None))
        return out

    try:
        sent_messages = await bot.send_media_group(chat_id, media=_build(force_disk=False))
    except Exception as e:  # noqa: BLE001
        if any(m.telegram_file_id for m in media_rows) and _is_bad_file_id(e):
            logger.warning("sender.media_group.stale_file_id", count=len(media_rows))
            for m in media_rows:
                m.telegram_file_id = None
            sent_messages = await bot.send_media_group(chat_id, media=_build(force_disk=True))
        else:
            raise

    if on_file_id:
        for m, sent in zip(media_rows, sent_messages):
            fid = _extract_file_id(sent, m.media_type)
            if fid:
                await on_file_id(m.id, fid)
    return sent_messages
