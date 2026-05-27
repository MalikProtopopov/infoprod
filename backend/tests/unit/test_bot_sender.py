"""Тесты универсального отправителя медиа bot/sender.py."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.bot import sender


class _FakeMedia:
    def __init__(self, media_type, mid=1, telegram_file_id="fid"):
        self.media_type = media_type
        self.telegram_file_id = telegram_file_id  # чтобы не трогать диск
        self.storage_path = "/tmp/none"
        self.original_filename = "x"
        self.caption = None
        self.id = mid


def _bot():
    b = MagicMock()
    sent = MagicMock(photo=None, video=None, animation=None, audio=None,
                     voice=None, video_note=None, document=None)
    for m in ("send_photo", "send_video", "send_animation", "send_audio",
              "send_voice", "send_video_note", "send_document", "send_media_group"):
        setattr(b, m, AsyncMock(return_value=sent))
    b.send_media_group = AsyncMock(return_value=[sent, sent])
    return b


@pytest.mark.asyncio
async def test_video_note_uses_send_video_note():
    b = _bot()
    await sender.send_media_item(b, 1, _FakeMedia("video_note"))
    b.send_video_note.assert_awaited_once()
    b.send_photo.assert_not_called()


@pytest.mark.asyncio
async def test_voice_uses_send_voice():
    b = _bot()
    await sender.send_media_item(b, 1, _FakeMedia("voice"), caption="hi")
    b.send_voice.assert_awaited_once()


@pytest.mark.asyncio
async def test_photo_uses_send_photo():
    b = _bot()
    await sender.send_media_item(b, 1, _FakeMedia("photo"), caption="cap")
    b.send_photo.assert_awaited_once()


@pytest.mark.asyncio
async def test_document_fallback():
    b = _bot()
    await sender.send_media_item(b, 1, _FakeMedia("document"))
    b.send_document.assert_awaited_once()


@pytest.mark.asyncio
async def test_media_group():
    b = _bot()
    rows = [_FakeMedia("photo", mid=1), _FakeMedia("photo", mid=2)]
    await sender.send_media_group(b, 1, rows)
    b.send_media_group.assert_awaited_once()
