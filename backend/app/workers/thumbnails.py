"""Генерация миниатюр для видео-медиа в funnel_step_media.

Запускается асинхронно после upload видео-файла. Использует ffmpeg
(установлен в Dockerfile). Извлекает кадр на 1-й секунде, ресайзит
до ширины 480px, сохраняет в `{storage_path}.thumb.jpg`.

Если ffmpeg недоступен или видео битое — миниатюра не создаётся,
фронт фолбэкает на «▶» иконку. Не критическая фича.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import structlog
from sqlalchemy import update

from app.db.session import SessionLocal
from app.models.funnel_step_media import FunnelStepMedia

logger = structlog.get_logger("thumbnails")


THUMBNAIL_WIDTH = 480
SEEK_SECONDS = 1.0


async def generate_video_thumbnail(media_id: int) -> None:
    """Извлекает первый кадр видео в JPEG, сохраняет рядом с оригиналом."""
    async with SessionLocal() as session:
        media = await session.get(FunnelStepMedia, media_id)
        if media is None:
            return
        if media.media_type != "video":
            return
        if media.thumbnail_path:
            return  # уже есть
        if not media.storage_path or not os.path.exists(media.storage_path):
            return

        src = media.storage_path
        dst = src + ".thumb.jpg"

        try:
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg",
                "-y",                       # перезаписывать без вопросов
                "-ss", str(SEEK_SECONDS),   # seek в видео
                "-i", src,
                "-vframes", "1",
                "-vf", f"scale={THUMBNAIL_WIDTH}:-1",
                "-q:v", "3",                # качество JPEG (1=лучшее, 31=худшее)
                dst,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                logger.warning(
                    "thumbnail.ffmpeg_failed",
                    media_id=media_id,
                    rc=proc.returncode,
                    stderr=stderr.decode(errors="replace")[:500],
                )
                return
        except FileNotFoundError:
            logger.warning("thumbnail.ffmpeg_missing", media_id=media_id)
            return
        except Exception as e:  # noqa: BLE001
            logger.warning("thumbnail.exception", media_id=media_id, error=str(e))
            return

        # Проверяем что файл создан и не пустой
        if not os.path.exists(dst) or os.path.getsize(dst) == 0:
            logger.warning("thumbnail.empty_output", media_id=media_id)
            return

        from datetime import datetime, timezone
        await session.execute(
            update(FunnelStepMedia)
            .where(FunnelStepMedia.id == media_id)
            .values(thumbnail_path=dst, thumbnail_generated_at=datetime.now(tz=timezone.utc))
        )
        await session.commit()
        logger.info(
            "thumbnail.generated",
            media_id=media_id,
            path=dst,
            size=os.path.getsize(dst),
        )


def enqueue_video_thumbnail(media_id: int) -> None:
    """Fire-and-forget запуск генерации thumbnail.

    Не блокирует upload-response. Если уже есть running loop — добавляет
    task; иначе игнорирует (test-окружение без event loop).
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(generate_video_thumbnail(media_id))
    except RuntimeError:
        # Нет активного loop (тесты, синхронный контекст) — игнор.
        pass
