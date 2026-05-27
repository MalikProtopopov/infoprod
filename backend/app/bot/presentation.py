"""Презентация продукта в боте — последовательная отправка контент-блоков.

Эффект «живого» менеджера: перед каждым блоком шлём chat_action (печатает…/
записывает кружок…) и небольшую задержку, затем сам блок (текст/медиа/кружок/голос).
Best-effort: падение одного блока не прерывает остальные.
"""
from __future__ import annotations

import asyncio

import structlog
from sqlalchemy import update

from app.bot import sender
from app.db import session as _db
from app.models.product_content import ProductMedia
from app.services.product_content import list_blocks

logger = structlog.get_logger("presentation")

# chat_action под тип блока/медиа
_BLOCK_ACTION = {"text": "typing", "video_note": "record_video_note", "voice": "record_voice"}
_MEDIA_ACTION = {
    "photo": "upload_photo", "video": "upload_video", "animation": "upload_video",
    "audio": "upload_document", "document": "upload_document",
    "voice": "record_voice", "video_note": "record_video_note",
}
_MAX_DELAY_S = 5.0


async def _persist_file_id(media_id: int, file_id: str) -> None:
    try:
        async with _db.SessionLocal() as s:
            await s.execute(
                update(ProductMedia)
                .where(ProductMedia.id == media_id, ProductMedia.telegram_file_id.is_(None))
                .values(telegram_file_id=file_id)
            )
            await s.commit()
    except Exception:  # noqa: BLE001
        logger.warning("presentation.persist_file_id_failed", media_id=media_id)


async def send_presentation(bot, chat_id: int, product) -> int:
    """Отправляет блоки презентации продукта. Возвращает число отправленных блоков."""
    if not getattr(product, "presentation_enabled", True):
        return 0
    async with _db.SessionLocal() as s:
        blocks = await list_blocks(s, product.id)  # media подгружены (selectinload)

    sent = 0
    for b in blocks:
        # 1) индикатор активности
        try:
            if b.kind in _BLOCK_ACTION:
                await bot.send_chat_action(chat_id, _BLOCK_ACTION[b.kind])
            elif b.kind == "media" and b.media:
                await bot.send_chat_action(chat_id, _MEDIA_ACTION.get(b.media[0].media_type, "upload_document"))
        except Exception:  # noqa: BLE001
            pass

        # 2) задержка (имитация набора), безопасно ограничена
        await asyncio.sleep(min(max((b.delay_ms or 0) / 1000.0, 0.0), _MAX_DELAY_S))

        # 3) сам блок
        try:
            if b.kind == "text":
                if b.text:
                    await bot.send_message(chat_id, b.text, parse_mode="HTML", disable_web_page_preview=True)
            elif b.kind == "voice":
                if b.media:
                    await sender.send_media_item(bot, chat_id, b.media[0], caption=b.text, on_file_id=_persist_file_id)
            elif b.kind == "video_note":
                if b.media:
                    await sender.send_media_item(bot, chat_id, b.media[0], on_file_id=_persist_file_id)
                    if b.text:
                        await bot.send_message(chat_id, b.text, parse_mode="HTML", disable_web_page_preview=True)
            elif b.kind == "media":
                if len(b.media) == 1:
                    await sender.send_media_item(bot, chat_id, b.media[0], caption=b.text, on_file_id=_persist_file_id)
                elif len(b.media) >= 2:
                    await sender.send_media_group(bot, chat_id, b.media, on_file_id=_persist_file_id)
                    if b.text:
                        await bot.send_message(chat_id, b.text, parse_mode="HTML", disable_web_page_preview=True)
            sent += 1
        except Exception:  # noqa: BLE001
            logger.warning("presentation.block_failed", block_id=b.id, kind=b.kind)
    return sent
