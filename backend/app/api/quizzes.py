"""API /api/quizzes — список, создание, детальный read/update/delete."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_admin, get_session
from app.models.admin import Admin
from app.schemas.quiz import (
    QuizBriefOut,
    QuizCreate,
    QuizDetailOut,
    QuizUpdate,
)
from app.services.quizzes import QuizService

router = APIRouter(prefix="/quizzes", tags=["quizzes"])


@router.get("", response_model=list[QuizBriefOut])
async def list_quizzes(
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> list[QuizBriefOut]:
    svc = QuizService(session)
    rows = await svc.list_brief()
    return [QuizBriefOut(**r) for r in rows]


@router.post("", response_model=QuizDetailOut, status_code=201)
async def create_quiz(
    payload: QuizCreate,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> QuizDetailOut:
    svc = QuizService(session)
    quiz = await svc.create(payload)
    await session.commit()
    return QuizDetailOut.model_validate(quiz)


@router.get("/{quiz_id}", response_model=QuizDetailOut)
async def get_quiz(
    quiz_id: int,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> QuizDetailOut:
    svc = QuizService(session)
    quiz = await svc.get_detail(quiz_id)
    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return QuizDetailOut.model_validate(quiz)


@router.patch("/{quiz_id}", response_model=QuizDetailOut)
async def update_quiz(
    quiz_id: int,
    payload: QuizUpdate,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> QuizDetailOut:
    svc = QuizService(session)
    quiz = await svc.update(quiz_id, payload)
    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")
    await session.commit()
    return QuizDetailOut.model_validate(quiz)


@router.delete("/{quiz_id}", status_code=204, response_class=Response)
async def delete_quiz(
    quiz_id: int,
    _: Admin = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> Response:
    svc = QuizService(session)
    ok = await svc.delete(quiz_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Quiz not found")
    await session.commit()
    return Response(status_code=204)
