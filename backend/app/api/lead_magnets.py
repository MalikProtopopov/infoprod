from __future__ import annotations

import os

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_admin, get_session
from app.models.admin import Admin
from app.models.lead_magnet import LeadMagnet
from app.schemas.lead_magnet import LeadMagnetOut, LeadMagnetUpdate
from app.services.lead_magnets import InvalidFileError, LeadMagnetsService

router = APIRouter(prefix="/lead-magnets", tags=["lead-magnets"])


def _to_out(lm: LeadMagnet) -> LeadMagnetOut:
    return LeadMagnetOut(
        id=lm.id, name=lm.name, description=lm.description,
        file_type=lm.file_type, file_size=lm.file_size,
        product_id=lm.product_id, is_active=lm.is_active,
        download_count=lm.download_count,
        has_telegram_file_id=bool(lm.telegram_file_id),
        created_at=lm.created_at,
    )


@router.get("", response_model=list[LeadMagnetOut])
async def list_lead_magnets(
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> list[LeadMagnetOut]:
    rows = (
        await session.execute(select(LeadMagnet).order_by(LeadMagnet.id.desc()))
    ).scalars().all()
    return [_to_out(r) for r in rows]


@router.post("", response_model=LeadMagnetOut, status_code=201)
async def upload_lead_magnet(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: str | None = Form(default=None),
    product_id: int | None = Form(default=None),
    admin: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> LeadMagnetOut:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="Файл пустой")
    svc = LeadMagnetsService(session)
    try:
        lm = await svc.upload(
            name=name, file_bytes=content,
            original_filename=file.filename or "upload.bin",
            description=description, product_id=product_id,
            created_by=admin.id,
        )
    except InvalidFileError as e:
        raise HTTPException(status_code=422, detail=str(e))
    await session.commit()
    await session.refresh(lm)
    return _to_out(lm)


@router.get("/{lm_id}", response_model=LeadMagnetOut)
async def get_lead_magnet(
    lm_id: int,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> LeadMagnetOut:
    lm = await session.get(LeadMagnet, lm_id)
    if lm is None:
        raise HTTPException(status_code=404, detail="Lead magnet not found")
    return _to_out(lm)


@router.patch("/{lm_id}", response_model=LeadMagnetOut)
async def update_lead_magnet(
    lm_id: int,
    payload: LeadMagnetUpdate,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> LeadMagnetOut:
    lm = await session.get(LeadMagnet, lm_id)
    if lm is None:
        raise HTTPException(status_code=404, detail="Lead magnet not found")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        if v is not None or k == "product_id":  # product_id может явно очищаться
            setattr(lm, k, v)
    await session.commit()
    await session.refresh(lm)
    return _to_out(lm)


@router.delete("/{lm_id}", status_code=204, response_class=Response)
async def delete_lead_magnet(
    lm_id: int,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> Response:
    lm = await session.get(LeadMagnet, lm_id)
    if lm is None:
        raise HTTPException(status_code=404, detail="Lead magnet not found")
    # Удаляем файл с диска, если он есть
    try:
        if lm.file_url and os.path.exists(lm.file_url):
            os.unlink(lm.file_url)
    except OSError:
        pass
    await session.delete(lm)
    await session.commit()
    return Response(status_code=204)


@router.get("/{lm_id}/download")
async def download_lead_magnet(
    lm_id: int,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
):
    lm = await session.get(LeadMagnet, lm_id)
    if lm is None:
        raise HTTPException(status_code=404, detail="Lead magnet not found")
    if not lm.file_url or not os.path.exists(lm.file_url):
        raise HTTPException(status_code=404, detail="Файл не найден на диске")
    media_type_map = {
        "pdf": "application/pdf",
        "image": "image/jpeg",
        "video": "video/mp4",
        "document": "application/octet-stream",
    }
    return FileResponse(
        lm.file_url,
        media_type=media_type_map.get(lm.file_type, "application/octet-stream"),
        filename=f"{lm.name}.{lm.file_type}",
    )
