"""API контент-блоков продукта (презентация в боте) + загрузка медиа.

Полный CRUD (в отличие от чеков — здесь нужно редактировать): блоки text/media/
video_note/voice, reorder, медиа (до 10 в media-блоке; 1 в video_note/voice).
"""
from __future__ import annotations

import mimetypes
import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_admin, get_session
from app.models.admin import Admin
from app.models.product import Product
from app.models.product_content import ProductContentBlock, ProductMedia
from app.schemas.product_content import (
    ContentBlockCreate,
    ContentBlockOut,
    ContentBlockUpdate,
    ReorderIn,
)
from app.services import product_content as svc
from app.share.limits import infer_media_type

router = APIRouter(tags=["product-content"])

MEDIA_GROUP_MAX = 10
MEDIA_MAX_BYTES = 100 * 1024 * 1024  # 100 MiB — презентационные видео могут быть крупнее чеков


def _media_out(m: ProductMedia) -> dict:
    return {
        "id": m.id,
        "media_type": m.media_type,
        "is_image": m.media_type == "photo",
        "original_filename": m.original_filename,
        "caption": m.caption,
        "order_idx": m.order_idx,
    }


def _block_out(b: ProductContentBlock) -> ContentBlockOut:
    return ContentBlockOut(
        id=b.id, product_id=b.product_id, order_idx=b.order_idx, kind=b.kind,
        text=b.text, delay_ms=b.delay_ms, is_active=b.is_active,
        media=[_media_out(m) for m in sorted(b.media, key=lambda x: x.order_idx)],
        created_at=b.created_at,
    )


@router.get("/products/{product_id}/content-blocks", response_model=list[ContentBlockOut])
async def list_blocks(
    product_id: int,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> list[ContentBlockOut]:
    blocks = await svc.list_blocks(session, product_id, only_active=False)
    return [_block_out(b) for b in blocks]


@router.post("/products/{product_id}/content-blocks", response_model=ContentBlockOut, status_code=201)
async def create_block(
    product_id: int,
    payload: ContentBlockCreate,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> ContentBlockOut:
    product = (await session.execute(select(Product).where(Product.id == product_id))).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Продукт не найден")
    next_idx = (
        await session.execute(
            select(func.coalesce(func.max(ProductContentBlock.order_idx), -1) + 1)
            .where(ProductContentBlock.product_id == product_id)
        )
    ).scalar_one()
    block = ProductContentBlock(
        product_id=product_id, kind=payload.kind, text=payload.text,
        delay_ms=payload.delay_ms, order_idx=next_idx,
    )
    session.add(block)
    await session.commit()
    block = await svc.get_block(session, block.id)
    return _block_out(block)


@router.post("/products/{product_id}/content-blocks/reorder", response_model=list[ContentBlockOut])
async def reorder_blocks(
    product_id: int,
    payload: ReorderIn,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> list[ContentBlockOut]:
    blocks = await svc.list_blocks(session, product_id, only_active=False)
    by_id = {b.id: b for b in blocks}
    for idx, bid in enumerate(payload.ordered_ids):
        if bid in by_id:
            by_id[bid].order_idx = idx
    await session.commit()
    return [_block_out(b) for b in await svc.list_blocks(session, product_id, only_active=False)]


@router.patch("/content-blocks/{block_id}", response_model=ContentBlockOut)
async def update_block(
    block_id: int,
    payload: ContentBlockUpdate,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> ContentBlockOut:
    block = await svc.get_block(session, block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Блок не найден")
    if payload.text is not None:
        block.text = payload.text
    if payload.delay_ms is not None:
        block.delay_ms = payload.delay_ms
    if payload.is_active is not None:
        block.is_active = payload.is_active
    if payload.kind is not None:
        block.kind = payload.kind
    await session.commit()
    return _block_out(await svc.get_block(session, block_id))


@router.delete("/content-blocks/{block_id}", status_code=204, response_class=Response)
async def delete_block(
    block_id: int,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> Response:
    block = (await session.execute(select(ProductContentBlock).where(ProductContentBlock.id == block_id))).scalar_one_or_none()
    if not block:
        raise HTTPException(status_code=404, detail="Блок не найден")
    await session.delete(block)
    await session.commit()
    return Response(status_code=204)


def _resolve_media_type(block_kind: str, mime: str) -> str:
    if block_kind == "video_note":
        return "video_note"
    if block_kind == "voice":
        return "voice"
    return infer_media_type(mime)  # photo/animation/video/audio/document


@router.post("/content-blocks/{block_id}/media", response_model=ContentBlockOut, status_code=201)
async def upload_media(
    block_id: int,
    file: UploadFile = File(...),
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> ContentBlockOut:
    block = await svc.get_block(session, block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Блок не найден")
    if block.kind == "text":
        raise HTTPException(status_code=400, detail="Текстовый блок не содержит медиа")
    limit = 1 if block.kind in ("video_note", "voice") else MEDIA_GROUP_MAX
    if len(block.media) >= limit:
        raise HTTPException(status_code=409, detail=f"В блоке уже {limit} медиа — лимит")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="Пустой файл")
    if len(content) > MEDIA_MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"Файл больше {MEDIA_MAX_BYTES // (1024*1024)} МБ")

    mime = file.content_type or mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream"
    media_type = _resolve_media_type(block.kind, mime)
    ext = os.path.splitext(file.filename or "")[1] or mimetypes.guess_extension(mime) or ""
    dst = svc.save_media_to_disk(content, block_id, ext)

    next_idx = max([m.order_idx for m in block.media], default=-1) + 1
    session.add(ProductMedia(
        block_id=block_id, media_type=media_type, storage_path=str(dst),
        original_filename=file.filename, mime_type=mime, file_size=len(content),
        order_idx=next_idx,
    ))
    await session.commit()
    # сбрасываем identity-map: иначе re-query вернёт объект со «старой» (пустой)
    # коллекцией media, загруженной до вставки.
    session.expire_all()
    return _block_out(await svc.get_block(session, block_id))


@router.delete("/content-block-media/{media_id}", status_code=204, response_class=Response)
async def delete_media(
    media_id: int,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> Response:
    m = await session.get(ProductMedia, media_id)
    if not m:
        raise HTTPException(status_code=404, detail="Медиа не найдено")
    if m.storage_path and os.path.exists(m.storage_path):
        try:
            os.remove(m.storage_path)
        except OSError:
            pass
    await session.delete(m)
    await session.commit()
    return Response(status_code=204)


@router.get("/content-block-media/{media_id}/file")
async def get_media_file(
    media_id: int,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
):
    m = await session.get(ProductMedia, media_id)
    if not m or not m.storage_path or not os.path.exists(m.storage_path):
        raise HTTPException(status_code=404, detail="Файл не найден")
    return FileResponse(m.storage_path, media_type=m.mime_type, filename=m.original_filename or f"media_{media_id}")
