"""Приведение видео к формату Telegram-кружка (video_note).

Кружок в Telegram обязан быть КВАДРАТНЫМ (иначе клиент показывает обрезанный
кадр — «как квадратное видео», а не круг) и не длиннее 60 сек. Здесь любое
загруженное видео центрируется, обрезается до квадрата по меньшей стороне,
масштабируется до VIDEO_NOTE_SIZE и триммится до 60 сек через ffmpeg
(установлен в Docker image — см. backend/Dockerfile).

Best-effort: если ffmpeg недоступен/упал или видео битое — возвращаем None, и
вызывающий код оставляет исходный файл как есть (уже-квадратное видео всё равно
уйдёт кружком корректно).
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import structlog

logger = structlog.get_logger("video_note")

# Сторона квадрата (px). Кружок Telegram ограничен 640; 480 — баланс
# чёткости и размера файла, кратно 2 (требование h264).
VIDEO_NOTE_SIZE = 480
# Лимит Telegram на длину кружка.
VIDEO_NOTE_MAX_SECONDS = 60

# Центрированный crop до квадрата по меньшей стороне + скейл до квадрата.
# Запятые внутри min() экранированы — иначе ffmpeg примет их за разделитель
# фильтров в filtergraph.
_FILTER = f"crop=min(iw\\,ih):min(iw\\,ih),scale={VIDEO_NOTE_SIZE}:{VIDEO_NOTE_SIZE}"


async def process_to_square(src: Path) -> tuple[Path, int, int, int] | None:
    """Делает из видео квадратный ≤60с mp4, пригодный для send_video_note.

    Возвращает (путь_результата, width, height, duration_сек) или None при любой
    ошибке (ffmpeg отсутствует / упал / пустой выход). Результат пишется рядом
    с исходником с суффиксом `.note.mp4`.
    """
    src = Path(src)
    if not src.exists():
        return None
    dst = src.with_name(f"{src.stem}.note.mp4")

    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y",
            "-i", str(src),
            "-t", str(VIDEO_NOTE_MAX_SECONDS),
            "-vf", _FILTER,
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            str(dst),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.warning(
                "video_note.ffmpeg_failed",
                rc=proc.returncode,
                stderr=stderr.decode(errors="replace")[:500],
            )
            _safe_unlink(dst)
            return None
    except FileNotFoundError:
        logger.warning("video_note.ffmpeg_missing")
        return None
    except Exception as e:  # noqa: BLE001
        logger.warning("video_note.exception", error=str(e))
        _safe_unlink(dst)
        return None

    if not dst.exists() or dst.stat().st_size == 0:
        logger.warning("video_note.empty_output")
        _safe_unlink(dst)
        return None

    duration = await _probe_duration(dst) or 0
    return dst, VIDEO_NOTE_SIZE, VIDEO_NOTE_SIZE, duration


async def _probe_duration(path: Path) -> int | None:
    """Длительность видео в секундах (округлённая) через ffprobe; None при ошибке."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        out, _ = await proc.communicate()
        if proc.returncode != 0:
            return None
        return int(round(float(out.decode().strip())))
    except Exception:  # noqa: BLE001
        return None


def _safe_unlink(p: Path) -> None:
    try:
        if p.exists():
            p.unlink()
    except OSError:
        pass
