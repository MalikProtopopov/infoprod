"""Контент-блоки продукта: чтение для бота + хранение медиа.

CRUD-эндпойнты (Фаза 3) тонкие — основная логика здесь.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.product_content import ProductContentBlock, ProductMedia

# Хранилище медиа продукта — на том же volume, что step_media/receipts.
PRODUCT_MEDIA_DIR = Path(os.environ.get("PRODUCT_MEDIA_DIR", "/var/lib/infobizbot/product_media"))


async def list_blocks(
    session: AsyncSession, product_id: int, *, only_active: bool = True
) -> list[ProductContentBlock]:
    """Блоки презентации продукта по порядку, с подгруженными медиа."""
    stmt = (
        select(ProductContentBlock)
        .where(ProductContentBlock.product_id == product_id)
        .options(selectinload(ProductContentBlock.media))
        .order_by(ProductContentBlock.order_idx, ProductContentBlock.id)
    )
    if only_active:
        stmt = stmt.where(ProductContentBlock.is_active.is_(True))
    return list((await session.execute(stmt)).scalars().all())


def save_media_to_disk(content: bytes, block_id: int, ext: str) -> Path:
    """Сохраняет файл медиа на диск, возвращает путь."""
    bdir = PRODUCT_MEDIA_DIR / str(block_id)
    bdir.mkdir(parents=True, exist_ok=True)
    dst = bdir / f"{uuid.uuid4().hex}{ext}"
    dst.write_bytes(content)
    return dst


async def get_block(session: AsyncSession, block_id: int) -> ProductContentBlock | None:
    return (
        await session.execute(
            select(ProductContentBlock)
            .where(ProductContentBlock.id == block_id)
            .options(selectinload(ProductContentBlock.media))
        )
    ).scalar_one_or_none()
