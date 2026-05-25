"""FormService — CRUD формы с вложенными полями (full-replace на update)."""
from __future__ import annotations

from typing import Iterable

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.form import Form, FormField
from app.models.funnel_step import FunnelStep
from app.models.lead import Lead
from app.models.user_step_state import UserStepState
from app.schemas.form import FormCreate, FormFieldIn, FormUpdate


class FormService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_brief(self) -> list[dict]:
        rows = (await self.session.execute(select(Form).order_by(Form.id.desc()))).scalars().all()
        if not rows:
            return []
        ids = [f.id for f in rows]
        fld_counts = dict(
            (
                await self.session.execute(
                    select(FormField.form_id, func.count(FormField.id))
                    .where(FormField.form_id.in_(ids))
                    .group_by(FormField.form_id)
                )
            ).all()
        )
        # Submissions — total/completed по статусам
        sub_rows = (
            await self.session.execute(
                select(
                    FunnelStep.form_id,
                    UserStepState.status,
                    func.count(UserStepState.id),
                )
                .join(FunnelStep, FunnelStep.id == UserStepState.funnel_step_id)
                .where(
                    UserStepState.mode == "form",
                    FunnelStep.form_id.in_(ids),
                )
                .group_by(FunnelStep.form_id, UserStepState.status)
            )
        ).all()
        total_map: dict[int, int] = {}
        completed_map: dict[int, int] = {}
        for fid, status, cnt in sub_rows:
            total_map[fid] = total_map.get(fid, 0) + cnt
            if status == "completed":
                completed_map[fid] = cnt
        # Leads created
        lead_rows = dict(
            (
                await self.session.execute(
                    select(
                        FunnelStep.form_id,
                        func.count(Lead.id),
                    )
                    .join(FunnelStep, FunnelStep.id == Lead.form_step_id)
                    .where(FunnelStep.form_id.in_(ids))
                    .group_by(FunnelStep.form_id)
                )
            ).all()
        )
        return [
            {
                "id": f.id,
                "name": f.name,
                "description": f.description,
                "product_id": f.product_id,
                "fields_count": fld_counts.get(f.id, 0),
                "submissions_total": total_map.get(f.id, 0),
                "submissions_completed": completed_map.get(f.id, 0),
                "leads_created": lead_rows.get(f.id, 0),
                "created_at": f.created_at,
            }
            for f in rows
        ]

    async def get_detail(self, form_id: int) -> Form | None:
        return (
            await self.session.execute(
                select(Form)
                .where(Form.id == form_id)
                .options(selectinload(Form.fields))
            )
        ).scalar_one_or_none()

    async def create(self, payload: FormCreate) -> Form:
        form = Form(
            name=payload.name,
            description=payload.description,
            product_id=payload.product_id,
            success_message=payload.success_message,
            cancel_message=payload.cancel_message,
            completion_buttons=payload.completion_buttons,
        )
        self.session.add(form)
        await self.session.flush()
        await self._replace_fields(form.id, payload.fields)
        await self.session.flush()
        return await self.get_detail(form.id)  # type: ignore[return-value]

    async def update(self, form_id: int, payload: FormUpdate) -> Form | None:
        form = await self.session.get(Form, form_id)
        if form is None:
            return None
        # `model_dump(exclude_unset=True)` мог бы помочь, но мы хотим явное None
        # для completion_buttons/product_id чтобы можно было занулить.
        for attr in (
            "name",
            "description",
            "product_id",
            "success_message",
            "cancel_message",
            "completion_buttons",
        ):
            value = getattr(payload, attr)
            if value is not None:
                setattr(form, attr, value)
        if payload.fields is not None:
            await self.session.execute(
                delete(FormField).where(FormField.form_id == form_id)
            )
            await self.session.flush()
            await self._replace_fields(form_id, payload.fields)
        await self.session.flush()
        return await self.get_detail(form_id)

    async def delete(self, form_id: int) -> bool:
        form = await self.session.get(Form, form_id)
        if form is None:
            return False
        await self.session.delete(form)
        return True

    async def _replace_fields(self, form_id: int, fields: Iterable[FormFieldIn]) -> None:
        for f_idx, f_in in enumerate(fields):
            self.session.add(
                FormField(
                    form_id=form_id,
                    order_idx=f_in.order_idx if f_in.order_idx is not None else f_idx,
                    key=f_in.key,
                    question=f_in.question,
                    prefix=f_in.prefix,
                    field_type=f_in.field_type,
                    required=f_in.required,
                    max_length=f_in.max_length,
                )
            )
        await self.session.flush()
