"""Тесты LeadMagnetsService — upload, send_to_user с моком aiogram."""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.lead_magnets import (
    InvalidFileError,
    LeadMagnetsService,
    _detect_file_type,
)


def test_detect_file_type():
    assert _detect_file_type("doc.pdf") == "pdf"
    assert _detect_file_type("photo.JPG") == "image"
    assert _detect_file_type("movie.mp4") == "video"
    assert _detect_file_type("file.docx") == "document"
    assert _detect_file_type("noext") == "document"


@pytest.mark.asyncio
async def test_upload_writes_file_and_creates_record(session, monkeypatch, tmp_path):
    monkeypatch.setattr("app.services.lead_magnets.STORAGE_DIR", tmp_path)
    svc = LeadMagnetsService(session)
    content = b"%PDF-1.4 test content"
    lm = await svc.upload(
        name="My PDF",
        file_bytes=content,
        original_filename="checklist.pdf",
        description="Test description",
    )
    assert lm.id is not None
    assert lm.name == "My PDF"
    assert lm.file_type == "pdf"
    assert lm.file_size == len(content)
    # Файл реально записан
    assert Path(lm.file_url).exists()
    assert Path(lm.file_url).read_bytes() == content


@pytest.mark.asyncio
async def test_upload_empty_file_raises(session, monkeypatch, tmp_path):
    monkeypatch.setattr("app.services.lead_magnets.STORAGE_DIR", tmp_path)
    svc = LeadMagnetsService(session)
    with pytest.raises(InvalidFileError):
        await svc.upload(name="X", file_bytes=b"", original_filename="empty.pdf")


@pytest.mark.asyncio
async def test_upload_oversized_file_raises(session, monkeypatch, tmp_path):
    monkeypatch.setattr("app.services.lead_magnets.STORAGE_DIR", tmp_path)
    monkeypatch.setattr("app.services.lead_magnets.MAX_FILE_SIZE_BYTES", 10)
    svc = LeadMagnetsService(session)
    with pytest.raises(InvalidFileError):
        await svc.upload(
            name="big", file_bytes=b"x" * 100, original_filename="big.pdf",
        )


@pytest.mark.asyncio
async def test_list_for_product_returns_attached_and_universal(session, make):
    p1 = await make.product()
    p2 = await make.product()
    await make.lead_magnet(product_id=p1.id, name="For P1")
    await make.lead_magnet(product_id=p2.id, name="For P2")
    await make.lead_magnet(product_id=None, name="Universal")

    svc = LeadMagnetsService(session)
    rows = await svc.list_for_product(p1.id)
    names = {r.name for r in rows}
    assert "For P1" in names
    assert "Universal" in names
    assert "For P2" not in names


@pytest.mark.asyncio
async def test_send_to_user_with_file_id_reuse(session, make, tmp_path):
    """Если есть telegram_file_id — используем send_document с ним."""
    lm = await make.lead_magnet(file_type="pdf", telegram_file_id="cached_file_id")

    fake_bot = MagicMock()
    sent_msg = MagicMock()
    sent_msg.document = MagicMock(file_id="new_file_id_from_response")
    fake_bot.send_document = AsyncMock(return_value=sent_msg)

    svc = LeadMagnetsService(session)
    ok = await svc.send_to_user(bot=fake_bot, user_telegram_id=12345, lead_magnet_id=lm.id)
    assert ok is True
    fake_bot.send_document.assert_awaited_once()
    args, kwargs = fake_bot.send_document.await_args
    assert args[0] == 12345
    assert args[1] == "cached_file_id"

    # download_count инкрементнут
    await session.refresh(lm)
    assert lm.download_count == 1


@pytest.mark.asyncio
async def test_send_to_user_uploads_file_from_disk(session, make, tmp_path):
    """Без telegram_file_id — грузим с диска через FSInputFile."""
    f = tmp_path / "test.pdf"
    f.write_bytes(b"%PDF-1.4")
    lm = await make.lead_magnet(file_url=str(f), telegram_file_id=None)

    fake_bot = MagicMock()
    sent_msg = MagicMock()
    sent_msg.document = MagicMock(file_id="returned_id")
    fake_bot.send_document = AsyncMock(return_value=sent_msg)

    svc = LeadMagnetsService(session)
    ok = await svc.send_to_user(bot=fake_bot, user_telegram_id=999, lead_magnet_id=lm.id)
    assert ok is True
    # telegram_file_id сохранился
    await session.refresh(lm)
    assert lm.telegram_file_id == "returned_id"


@pytest.mark.asyncio
async def test_send_to_user_returns_false_when_file_missing(session, make):
    lm = await make.lead_magnet(file_url="/tmp/nonexistent_xyz.pdf", telegram_file_id=None)
    fake_bot = MagicMock()
    svc = LeadMagnetsService(session)
    ok = await svc.send_to_user(bot=fake_bot, user_telegram_id=1, lead_magnet_id=lm.id)
    assert ok is False


@pytest.mark.asyncio
async def test_send_to_user_returns_false_when_not_active(session, make):
    lm = await make.lead_magnet(is_active=False)
    fake_bot = MagicMock()
    svc = LeadMagnetsService(session)
    ok = await svc.send_to_user(bot=fake_bot, user_telegram_id=1, lead_magnet_id=lm.id)
    assert ok is False
