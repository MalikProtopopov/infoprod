"""StepMediaService — пайплайн загрузки + reorder + delete медиа на шагах.

Хранение — локальная файловая система (как у lead_magnets). Структура папок:
    {STORAGE_DIR}/{step_id}/{media_uuid}{ext}

Лимиты и MIME-валидация — `app.share.limits`.
"""
from __future__ import annotations

import hashlib
import io
import mimetypes
import os
import uuid
from pathlib import Path

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.funnel_step_media import FunnelStepMedia
from app.share.limits import (
    GENERIC_LIMIT_BYTES,
    MAX_UPLOAD_BYTES,
    MEDIA_GROUP_MAX,
    PHOTO_LIMIT_BYTES,
    infer_media_type,
)

logger = structlog.get_logger("step_media")


STORAGE_DIR = Path(os.environ.get("STEP_MEDIA_DIR", "/var/lib/infobizbot/step_media"))


class InvalidMediaError(Exception):
    """Загружаемый файл нарушает правила (размер, тип, лимит на группу)."""


def _image_dimensions(content: bytes) -> tuple[int | None, int | None]:
    try:
        from PIL import Image  # ленивый импорт — Pillow не нужен на старте
    except ImportError:
        return None, None
    try:
        with Image.open(io.BytesIO(content)) as img:
            return img.width, img.height
    except Exception:
        return None, None


def _detect_mime(filename: str | None, declared: str | None) -> str:
    if declared and declared != "application/octet-stream":
        return declared
    guessed, _ = mimetypes.guess_type(filename or "")
    return guessed or declared or "application/octet-stream"


def _validate_size(media_type: str, file_size: int) -> None:
    """Проверка лимитов Telegram Bot API. Для совсем больших — отдельный код."""
    if file_size > MAX_UPLOAD_BYTES:
        raise InvalidMediaError(
            f"Файл больше {MAX_UPLOAD_BYTES // (1024**3)} GiB — не принимается"
        )
    if media_type == "photo" and file_size > PHOTO_LIMIT_BYTES:
        raise InvalidMediaError(
            f"Фото больше {PHOTO_LIMIT_BYTES // (1024 * 1024)} MB — Telegram не примет sendPhoto. "
            "Загрузите как документ или уменьшите размер."
        )
    if file_size > GENERIC_LIMIT_BYTES:
        raise InvalidMediaError(
            f"Файл больше {GENERIC_LIMIT_BYTES // (1024 * 1024)} MB — Telegram Bot API не примет"
        )


def _save_to_disk(content: bytes, step_id: int, original_filename: str | None) -> tuple[Path, str]:
    """Сохраняет на диск. Возвращает (полный путь, имя файла)."""
    step_dir = STORAGE_DIR / str(step_id)
    step_dir.mkdir(parents=True, exist_ok=True)
    ext = ""
    if original_filename and "." in original_filename:
        ext = "." + original_filename.rsplit(".", 1)[-1].lower()
    stored_name = f"{uuid.uuid4().hex}{ext}"
    dst = step_dir / stored_name
    dst.write_bytes(content)
    return dst, stored_name


class StepMediaService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_for_step(self, step_id: int) -> list[FunnelStepMedia]:
        rows = (
            await self.session.execute(
                select(FunnelStepMedia)
                .where(FunnelStepMedia.funnel_step_id == step_id)
                .order_by(FunnelStepMedia.order_idx)
            )
        ).scalars().all()
        return list(rows)

    async def upload(
        self,
        *,
        step_id: int,
        content: bytes,
        original_filename: str | None,
        declared_mime: str | None,
        caption: str | None = None,
    ) -> FunnelStepMedia:
        if not content:
            raise InvalidMediaError("Файл пустой")

        # Проверяем лимит media-group до записи на диск
        existing = await self.list_for_step(step_id)
        if len(existing) >= MEDIA_GROUP_MAX:
            raise InvalidMediaError(
                f"У шага уже {MEDIA_GROUP_MAX} медиа — лимит Telegram media-group"
            )

        mime = _detect_mime(original_filename, declared_mime)
        media_type = infer_media_type(mime)
        file_size = len(content)
        _validate_size(media_type, file_size)

        # Размеры для фото — best effort
        width = height = None
        if media_type == "photo":
            width, height = _image_dimensions(content)

        checksum = hashlib.sha256(content).hexdigest()

        dst_path, _stored_name = _save_to_disk(content, step_id, original_filename)

        # Следующий свободный order_idx
        used = {m.order_idx for m in existing}
        order_idx = 0
        while order_idx in used:
            order_idx += 1

        media = FunnelStepMedia(
            funnel_step_id=step_id,
            media_type=media_type,
            storage_path=str(dst_path),
            original_filename=(original_filename or "")[:512] or None,
            mime_type=mime,
            file_size=file_size,
            width=width,
            height=height,
            order_idx=order_idx,
            caption=caption,
            checksum_sha256=checksum,
        )
        self.session.add(media)
        await self.session.flush()
        await self.session.refresh(media)
        logger.info(
            "step_media.uploaded",
            step_id=step_id,
            media_id=media.id,
            media_type=media_type,
            size=file_size,
            order_idx=order_idx,
        )

        # Для видео — async-генерация thumbnail (ffmpeg в Docker image).
        # Fire-and-forget: не блокируем upload response, ошибки не падают
        # вверх — фронт фолбэкает на «▶» иконку если thumbnail не появится.
        if media_type == "video":
            try:
                from app.workers.thumbnails import enqueue_video_thumbnail
                enqueue_video_thumbnail(media.id)
            except Exception as e:  # noqa: BLE001
                logger.warning("step_media.thumbnail_enqueue_failed", error=str(e))

        return media

    async def update_caption(self, media_id: int, caption: str | None) -> FunnelStepMedia | None:
        media = await self.session.get(FunnelStepMedia, media_id)
        if media is None:
            return None
        media.caption = caption
        await self.session.flush()
        return media

    async def reorder(self, step_id: int, ordered_ids: list[int]) -> list[FunnelStepMedia]:
        """Принимает желаемый порядок ID. Применяет order_idx по позиции."""
        media_list = await self.list_for_step(step_id)
        by_id = {m.id: m for m in media_list}
        if set(ordered_ids) != set(by_id.keys()):
            raise InvalidMediaError(
                "Список ID в запросе не совпадает с текущими медиа шага"
            )
        # Уникальный индекс DEFERRABLE INITIALLY DEFERRED — можем свопить
        # значения в одной транзакции, проверка сработает на commit.
        for new_idx, media_id in enumerate(ordered_ids):
            by_id[media_id].order_idx = new_idx
        await self.session.flush()
        return [by_id[mid] for mid in ordered_ids]

    async def delete(self, media_id: int) -> bool:
        media = await self.session.get(FunnelStepMedia, media_id)
        if media is None:
            return False
        # Удаляем файл с диска (best-effort)
        try:
            if media.storage_path and os.path.exists(media.storage_path):
                os.unlink(media.storage_path)
        except OSError:
            pass
        # И thumbnail, если был
        try:
            if media.thumbnail_path and os.path.exists(media.thumbnail_path):
                os.unlink(media.thumbnail_path)
        except OSError:
            pass
        await self.session.delete(media)
        await self.session.flush()
        return True
