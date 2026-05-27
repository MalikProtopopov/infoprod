"""Смоук презентации продукта: блоки отправляются нужными методами бота."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

import app.db.session as dbs
from app.bot.presentation import send_presentation
from app.models.product_content import ProductContentBlock, ProductMedia


@pytest.mark.asyncio
async def test_send_presentation_sends_text_and_video_note(make_committed, clean_db):
    product = await make_committed.product()
    async with dbs.SessionLocal() as s:
        b_text = ProductContentBlock(product_id=product.id, order_idx=0, kind="text",
                                     text="Привет! 👋", delay_ms=0)
        b_note = ProductContentBlock(product_id=product.id, order_idx=1, kind="video_note", delay_ms=0)
        s.add_all([b_text, b_note])
        await s.flush()
        s.add(ProductMedia(
            block_id=b_note.id, media_type="video_note", storage_path="/tmp/none",
            mime_type="video/mp4", file_size=10, telegram_file_id="fid", order_idx=0,
        ))
        await s.commit()

    bot = MagicMock()
    bot.send_chat_action = AsyncMock()
    bot.send_message = AsyncMock(return_value=MagicMock())
    bot.send_video_note = AsyncMock(return_value=MagicMock(video_note=None))

    n = await send_presentation(bot, 123, product)
    assert n == 2
    bot.send_message.assert_awaited()       # текстовый блок
    bot.send_video_note.assert_awaited()    # кружок


@pytest.mark.asyncio
async def test_long_caption_media_falls_back_to_separate_text(make_committed, clean_db):
    """F1: подпись >1024 → медиа без caption + текст отдельным сообщением (не теряется)."""
    product = await make_committed.product()
    long_text = "x" * 1500
    async with dbs.SessionLocal() as s:
        b = ProductContentBlock(product_id=product.id, order_idx=0, kind="media",
                                text=long_text, delay_ms=0)
        s.add(b)
        await s.flush()
        s.add(ProductMedia(block_id=b.id, media_type="photo", storage_path="/tmp/none",
                           mime_type="image/png", file_size=10, telegram_file_id="fid", order_idx=0))
        await s.commit()

    bot = MagicMock()
    bot.send_chat_action = AsyncMock()
    bot.send_photo = AsyncMock(return_value=MagicMock(photo=None))
    bot.send_message = AsyncMock(return_value=MagicMock())

    n = await send_presentation(bot, 1, product)
    assert n == 1
    # фото отправлено БЕЗ подписи
    _, kwargs = bot.send_photo.call_args
    assert kwargs.get("caption") is None
    # длинный текст ушёл отдельным сообщением
    bot.send_message.assert_awaited()


@pytest.mark.asyncio
async def test_presentation_disabled_sends_nothing(make_committed, clean_db):
    product = await make_committed.product(presentation_enabled=False)
    bot = MagicMock()
    bot.send_chat_action = AsyncMock()
    n = await send_presentation(bot, 1, product)
    assert n == 0
    bot.send_chat_action.assert_not_called()
