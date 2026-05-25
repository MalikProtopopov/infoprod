"""QuizService — CRUD квиза с вложенными вопросами/опциями/вердиктами.

Семантика «целиком» для PATCH: если передан questions / verdicts —
старые удаляются и пересоздаются. Это проще для UI «edit & save».
Поскольку user_step_states.answers хранит снапшот вопросов/ответов
на момент прохождения, прошлые попытки читаются даже после полной
замены содержимого квиза.
"""
from __future__ import annotations

from typing import Iterable

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.quiz import Quiz, QuizOption, QuizQuestion, QuizVerdict
from app.models.user_step_state import UserStepState
from app.models.funnel_step import FunnelStep
from app.schemas.quiz import (
    QuizCreate,
    QuizQuestionIn,
    QuizUpdate,
    QuizVerdictIn,
)


class QuizService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_brief(self) -> list[dict]:
        """Список с агрегированными метриками (для админ-списка)."""
        rows = (
            await self.session.execute(
                select(Quiz).order_by(Quiz.id.desc())
            )
        ).scalars().all()
        if not rows:
            return []

        ids = [q.id for q in rows]

        # Вопросы / вердикты — кол-во
        q_counts = dict(
            (
                await self.session.execute(
                    select(QuizQuestion.quiz_id, func.count(QuizQuestion.id))
                    .where(QuizQuestion.quiz_id.in_(ids))
                    .group_by(QuizQuestion.quiz_id)
                )
            ).all()
        )
        v_counts = dict(
            (
                await self.session.execute(
                    select(QuizVerdict.quiz_id, func.count(QuizVerdict.id))
                    .where(QuizVerdict.quiz_id.in_(ids))
                    .group_by(QuizVerdict.quiz_id)
                )
            ).all()
        )

        # Попытки — total / completed. Join user_step_states → funnel_steps → quizzes.
        attempt_rows = (
            await self.session.execute(
                select(
                    FunnelStep.quiz_id,
                    UserStepState.status,
                    func.count(UserStepState.id),
                )
                .join(FunnelStep, FunnelStep.id == UserStepState.funnel_step_id)
                .where(
                    UserStepState.mode == "quiz",
                    FunnelStep.quiz_id.in_(ids),
                )
                .group_by(FunnelStep.quiz_id, UserStepState.status)
            )
        ).all()
        total_map: dict[int, int] = {}
        completed_map: dict[int, int] = {}
        for qid, status, cnt in attempt_rows:
            total_map[qid] = total_map.get(qid, 0) + cnt
            if status == "completed":
                completed_map[qid] = cnt

        return [
            {
                "id": q.id,
                "name": q.name,
                "description": q.description,
                "questions_count": q_counts.get(q.id, 0),
                "verdicts_count": v_counts.get(q.id, 0),
                "attempts_total": total_map.get(q.id, 0),
                "attempts_completed": completed_map.get(q.id, 0),
                "created_at": q.created_at,
            }
            for q in rows
        ]

    async def get_detail(self, quiz_id: int) -> Quiz | None:
        return (
            await self.session.execute(
                select(Quiz)
                .where(Quiz.id == quiz_id)
                .options(
                    selectinload(Quiz.questions).selectinload(QuizQuestion.options),
                    selectinload(Quiz.verdicts),
                )
            )
        ).scalar_one_or_none()

    async def create(self, payload: QuizCreate) -> Quiz:
        quiz = Quiz(name=payload.name, description=payload.description)
        self.session.add(quiz)
        await self.session.flush()

        await self._replace_questions(quiz.id, payload.questions)
        await self._replace_verdicts(quiz.id, payload.verdicts)
        await self.session.flush()
        # перезагружаем с relationships
        return await self.get_detail(quiz.id)  # type: ignore[return-value]

    async def update(self, quiz_id: int, payload: QuizUpdate) -> Quiz | None:
        quiz = await self.session.get(Quiz, quiz_id)
        if quiz is None:
            return None
        if payload.name is not None:
            quiz.name = payload.name
        if payload.description is not None:
            quiz.description = payload.description
        if payload.questions is not None:
            # Удаляем все старые вопросы (cascade грохнет опции)
            await self.session.execute(
                delete(QuizQuestion).where(QuizQuestion.quiz_id == quiz_id)
            )
            await self.session.flush()
            await self._replace_questions(quiz_id, payload.questions)
        if payload.verdicts is not None:
            await self.session.execute(
                delete(QuizVerdict).where(QuizVerdict.quiz_id == quiz_id)
            )
            await self.session.flush()
            await self._replace_verdicts(quiz_id, payload.verdicts)
        await self.session.flush()
        return await self.get_detail(quiz_id)

    async def delete(self, quiz_id: int) -> bool:
        quiz = await self.session.get(Quiz, quiz_id)
        if quiz is None:
            return False
        await self.session.delete(quiz)
        return True

    # ───── internal ─────

    async def _replace_questions(
        self, quiz_id: int, questions: Iterable[QuizQuestionIn]
    ) -> None:
        for q_idx, q_in in enumerate(questions):
            q = QuizQuestion(
                quiz_id=quiz_id,
                order_idx=q_in.order_idx if q_in.order_idx is not None else q_idx,
                text=q_in.text,
                prefix=q_in.prefix,
            )
            self.session.add(q)
            await self.session.flush()
            for o_idx, opt in enumerate(q_in.options):
                self.session.add(
                    QuizOption(
                        question_id=q.id,
                        order_idx=opt.order_idx if opt.order_idx is not None else o_idx,
                        text=opt.text,
                        score=opt.score,
                    )
                )
        await self.session.flush()

    async def _replace_verdicts(
        self, quiz_id: int, verdicts: Iterable[QuizVerdictIn]
    ) -> None:
        for v_idx, v_in in enumerate(verdicts):
            self.session.add(
                QuizVerdict(
                    quiz_id=quiz_id,
                    order_idx=v_in.order_idx if v_in.order_idx is not None else v_idx,
                    max_score=v_in.max_score,
                    text=v_in.text,
                    button_text=v_in.button_text,
                    button_action=v_in.button_action,
                )
            )
        await self.session.flush()
