"""Сервис приведения видео к Telegram-кружку (ffmpeg-квадрат)."""
from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

import pytest

from app.services import video_note

_FFMPEG_MISSING = shutil.which("ffmpeg") is None


async def _make_test_video(path: Path, size: str = "320x180", duration: int = 2) -> None:
    """Генерит тестовое видео заданного размера через ffmpeg lavfi."""
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"testsrc=size={size}:duration={duration}:rate=10",
        "-pix_fmt", "yuv420p", str(path),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.communicate()


@pytest.mark.skipif(_FFMPEG_MISSING, reason="ffmpeg не установлен")
@pytest.mark.asyncio
async def test_process_to_square_makes_square_from_rectangle(tmp_path):
    src = tmp_path / "rect.mp4"
    await _make_test_video(src, size="320x180", duration=2)

    result = await video_note.process_to_square(src)
    assert result is not None
    out_path, w, h, dur = result
    assert w == h == video_note.VIDEO_NOTE_SIZE
    assert Path(out_path).exists() and Path(out_path).stat().st_size > 0
    assert dur >= 1


@pytest.mark.skipif(_FFMPEG_MISSING, reason="ffmpeg не установлен")
@pytest.mark.asyncio
async def test_process_to_square_trims_to_limit(tmp_path):
    src = tmp_path / "long.mp4"
    await _make_test_video(src, size="200x200", duration=video_note.VIDEO_NOTE_MAX_SECONDS + 5)

    result = await video_note.process_to_square(src)
    assert result is not None
    _out, _w, _h, dur = result
    assert dur <= video_note.VIDEO_NOTE_MAX_SECONDS


@pytest.mark.asyncio
async def test_process_to_square_returns_none_on_garbage(tmp_path):
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"definitely not a video")
    assert await video_note.process_to_square(bad) is None


@pytest.mark.asyncio
async def test_process_to_square_returns_none_on_missing_file(tmp_path):
    assert await video_note.process_to_square(tmp_path / "nope.mp4") is None
