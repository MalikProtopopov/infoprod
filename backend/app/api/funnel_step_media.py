"""API: медиа на шагах воронок.

Endpoints:
    GET    /api/funnel-steps/{step_id}/media         — список
    POST   /api/funnel-steps/{step_id}/media         — загрузка (multipart, 1 файл)
    PATCH  /api/funnel-steps/{step_id}/media/reorder — переупорядочить
    PATCH  /api/funnel-step-media/{media_id}         — caption
    DELETE /api/funnel-step-media/{media_id}         — удалить

Доступ: admin или manager (current_admin без проверки role).
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_admin, get_session
from app.models.admin import Admin
from app.models.funnel_step import FunnelStep
from app.models.funnel_step_media import FunnelStepMedia
from app.services.step_media import InvalidMediaError, StepMediaService


router = APIRouter(tags=["funnel-step-media"])


class StepMediaOut(BaseModel):
    id: int
    funnel_step_id: int
    media_type: str
    original_filename: str | None
    mime_type: str
    file_size: int
    width: int | None
    height: int | None
    duration: int | None
    order_idx: int
    caption: str | None
    has_telegram_file_id: bool
    has_thumbnail: bool
    created_at: datetime


class StepMediaReorderIn(BaseModel):
    ordered_ids: list[int] = Field(..., description="ID медиа в желаемом порядке")


class StepMediaCaptionIn(BaseModel):
    caption: str | None = Field(default=None, max_length=2000)


def _to_out(m: FunnelStepMedia) -> StepMediaOut:
    return StepMediaOut(
        id=m.id,
        funnel_step_id=m.funnel_step_id,
        media_type=m.media_type,
        original_filename=m.original_filename,
        mime_type=m.mime_type,
        file_size=m.file_size,
        width=m.width,
        height=m.height,
        duration=m.duration,
        order_idx=m.order_idx,
        caption=m.caption,
        has_telegram_file_id=bool(m.telegram_file_id),
        has_thumbnail=bool(m.thumbnail_path),
        created_at=m.created_at,
    )


@router.get(
    "/funnel-steps/{step_id}/media",
    response_model=list[StepMediaOut],
)
async def list_step_media(
    step_id: int,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> list[StepMediaOut]:
    step = await session.get(FunnelStep, step_id)
    if step is None:
        raise HTTPException(status_code=404, detail="Step not found")
    svc = StepMediaService(session)
    media = await svc.list_for_step(step_id)
    return [_to_out(m) for m in media]


@router.post(
    "/funnel-steps/{step_id}/media",
    response_model=StepMediaOut,
    status_code=201,
)
async def upload_step_media(
    step_id: int,
    file: UploadFile = File(...),
    caption: str | None = Form(default=None),
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> StepMediaOut:
    step = await session.get(FunnelStep, step_id)
    if step is None:
        raise HTTPException(status_code=404, detail="Step not found")

    content = await file.read()
    svc = StepMediaService(session)
    try:
        media = await svc.upload(
            step_id=step_id,
            content=content,
            original_filename=file.filename,
            declared_mime=file.content_type,
            caption=caption,
        )
    except InvalidMediaError as e:
        raise HTTPException(status_code=422, detail=str(e))
    await session.commit()
    await session.refresh(media)
    return _to_out(media)


@router.patch(
    "/funnel-steps/{step_id}/media/reorder",
    response_model=list[StepMediaOut],
)
async def reorder_step_media(
    step_id: int,
    payload: StepMediaReorderIn,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> list[StepMediaOut]:
    step = await session.get(FunnelStep, step_id)
    if step is None:
        raise HTTPException(status_code=404, detail="Step not found")
    svc = StepMediaService(session)
    try:
        media = await svc.reorder(step_id, payload.ordered_ids)
    except InvalidMediaError as e:
        raise HTTPException(status_code=422, detail=str(e))
    await session.commit()
    return [_to_out(m) for m in media]


@router.patch(
    "/funnel-step-media/{media_id}",
    response_model=StepMediaOut,
)
async def update_step_media_caption(
    media_id: int,
    payload: StepMediaCaptionIn,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> StepMediaOut:
    svc = StepMediaService(session)
    media = await svc.update_caption(media_id, payload.caption)
    if media is None:
        raise HTTPException(status_code=404, detail="Step media not found")
    await session.commit()
    await session.refresh(media)
    return _to_out(media)


@router.delete(
    "/funnel-step-media/{media_id}",
    status_code=204,
    response_class=Response,
)
async def delete_step_media(
    media_id: int,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> Response:
    svc = StepMediaService(session)
    ok = await svc.delete(media_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Step media not found")
    await session.commit()
    return Response(status_code=204)
