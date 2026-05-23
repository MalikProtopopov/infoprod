"""LeadMagnetsService — upload (filesystem) + send_to_user через aiogram + file_id reuse."""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Optional

import structlog
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead_magnet import LeadMagnet

logger = structlog.get_logger("lead_magnets")

# Где хранить файлы (на проде монтируется volume)
STORAGE_DIR = Path(os.environ.get("LEAD_MAGNETS_DIR", "/var/lib/infobizbot/lead_magnets"))


# Максимум для upload
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB


class InvalidFileError(Exception):
    pass


def _detect_file_type(filename: str) -> str:
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext in {"pdf"}:
        return "pdf"
    if ext in {"jpg", "jpeg", "png", "webp", "gif"}:
        return "image"
    if ext in {"mp4", "mov", "webm", "mkv"}:
        return "video"
    return "document"


class LeadMagnetsService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upload(
        self,
        *,
        name: str,
        file_bytes: bytes,
        original_filename: str,
        description: str | None = None,
        product_id: int | None = None,
        created_by: int | None = None,
    ) -> LeadMagnet:
        if not file_bytes:
            raise InvalidFileError("Файл пустой")
        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            raise InvalidFileError(f"Файл больше {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB")

        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        ext = original_filename.lower().rsplit(".", 1)[-1] if "." in original_filename else "bin"
        stored_name = f"{uuid.uuid4().hex}.{ext}"
        dst = STORAGE_DIR / stored_name
        dst.write_bytes(file_bytes)

        lm = LeadMagnet(
            name=name,
            description=description,
            file_url=str(dst),
            file_type=_detect_file_type(original_filename),
            file_size=len(file_bytes),
            product_id=product_id,
            created_by=created_by,
            is_active=True,
        )
        self.session.add(lm)
        await self.session.flush()
        logger.info("lead_magnet.uploaded", id=lm.id, size=len(file_bytes), type=lm.file_type)
        return lm

    async def list_for_product(self, product_id: int) -> list[LeadMagnet]:
        """Возвращает универсальные (product_id=NULL) + привязанные к продукту."""
        rows = (
            await self.session.execute(
                select(LeadMagnet).where(
                    LeadMagnet.is_active.is_(True),
                    or_(LeadMagnet.product_id == product_id, LeadMagnet.product_id.is_(None)),
                ).order_by(LeadMagnet.id.desc())
            )
        ).scalars().all()
        return list(rows)

    async def list_all(self) -> list[LeadMagnet]:
        rows = (
            await self.session.execute(
                select(LeadMagnet).order_by(LeadMagnet.id.desc())
            )
        ).scalars().all()
        return list(rows)

    async def send_to_user(
        self,
        *,
        bot,
        user_telegram_id: int,
        lead_magnet_id: int,
    ) -> bool:
        """Отправляет файл через aiogram. Если есть telegram_file_id — переиспользуем."""
        lm = await self.session.get(LeadMagnet, lead_magnet_id)
        if lm is None or not lm.is_active:
            return False

        try:
            from aiogram.types import FSInputFile, BufferedInputFile
            file_id_to_save: Optional[str] = None

            # 1) Если есть file_id — используем его
            if lm.telegram_file_id:
                sent = await self._send_by_file_id(bot, user_telegram_id, lm)
            else:
                # 2) Иначе грузим файл с диска
                if not os.path.exists(lm.file_url):
                    logger.warning("lead_magnet.file_missing", id=lm.id, path=lm.file_url)
                    return False
                input_file = FSInputFile(lm.file_url, filename=lm.name)
                sent = await self._send_input_file(bot, user_telegram_id, lm, input_file)

            # 3) Сохраняем file_id если получили
            if sent is not None:
                fid = self._extract_file_id(sent, lm.file_type)
                if fid and not lm.telegram_file_id:
                    file_id_to_save = fid

            if file_id_to_save:
                await self.session.execute(
                    update(LeadMagnet)
                    .where(LeadMagnet.id == lm.id)
                    .values(telegram_file_id=file_id_to_save)
                )
            await self.session.execute(
                update(LeadMagnet)
                .where(LeadMagnet.id == lm.id)
                .values(download_count=LeadMagnet.download_count + 1)
            )
            return True
        except Exception:
            logger.exception("lead_magnet.send_failed", id=lead_magnet_id, user_tg_id=user_telegram_id)
            return False

    @staticmethod
    async def _send_by_file_id(bot, user_telegram_id: int, lm: LeadMagnet):
        if lm.file_type == "image":
            return await bot.send_photo(user_telegram_id, lm.telegram_file_id, caption=lm.name)
        if lm.file_type == "video":
            return await bot.send_video(user_telegram_id, lm.telegram_file_id, caption=lm.name)
        return await bot.send_document(user_telegram_id, lm.telegram_file_id, caption=lm.name)

    @staticmethod
    async def _send_input_file(bot, user_telegram_id: int, lm: LeadMagnet, input_file):
        if lm.file_type == "image":
            return await bot.send_photo(user_telegram_id, input_file, caption=lm.name)
        if lm.file_type == "video":
            return await bot.send_video(user_telegram_id, input_file, caption=lm.name)
        return await bot.send_document(user_telegram_id, input_file, caption=lm.name)

    @staticmethod
    def _extract_file_id(message, file_type: str) -> Optional[str]:
        # Telegram возвращает разные поля в зависимости от типа
        if file_type == "image":
            photos = getattr(message, "photo", None)
            if photos:
                return photos[-1].file_id
        if file_type == "video":
            video = getattr(message, "video", None)
            if video:
                return video.file_id
        document = getattr(message, "document", None)
        if document:
            return document.file_id
        return None
