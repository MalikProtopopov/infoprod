"""API /api/forms — список, создание, детальный read/update/delete."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_admin, get_session
from app.models.admin import Admin
from app.schemas.form import FormBriefOut, FormCreate, FormDetailOut, FormUpdate
from app.services.forms import FormService

router = APIRouter(prefix="/forms", tags=["forms"])


@router.get("", response_model=list[FormBriefOut])
async def list_forms(
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> list[FormBriefOut]:
    svc = FormService(session)
    rows = await svc.list_brief()
    return [FormBriefOut(**r) for r in rows]


@router.post("", response_model=FormDetailOut, status_code=201)
async def create_form(
    payload: FormCreate,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> FormDetailOut:
    svc = FormService(session)
    form = await svc.create(payload)
    await session.commit()
    return FormDetailOut.model_validate(form)


@router.get("/{form_id}", response_model=FormDetailOut)
async def get_form(
    form_id: int,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> FormDetailOut:
    svc = FormService(session)
    form = await svc.get_detail(form_id)
    if form is None:
        raise HTTPException(status_code=404, detail="Form not found")
    return FormDetailOut.model_validate(form)


@router.patch("/{form_id}", response_model=FormDetailOut)
async def update_form(
    form_id: int,
    payload: FormUpdate,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> FormDetailOut:
    svc = FormService(session)
    form = await svc.update(form_id, payload)
    if form is None:
        raise HTTPException(status_code=404, detail="Form not found")
    await session.commit()
    return FormDetailOut.model_validate(form)


@router.delete("/{form_id}", status_code=204, response_class=Response)
async def delete_form(
    form_id: int,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> Response:
    svc = FormService(session)
    ok = await svc.delete(form_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Form not found")
    await session.commit()
    return Response(status_code=204)
