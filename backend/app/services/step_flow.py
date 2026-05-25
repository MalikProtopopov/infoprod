"""StepFlowService — state-machine для quiz/form шагов воронки.

Источник правды — реляционные модели Quiz/QuizQuestion/QuizOption/QuizVerdict
и Form/FormField. Шаг воронки ссылается на квиз/форму через
funnel_steps.quiz_id / form_id.

Все возвращаемые «события» — плоские dataclass-объекты, чтобы вызывающий
хэндлер сам отрисовал их в Telegram (мы не таскаем сюда aiogram-зависимости).

user_step_states.answers хранят **снапшот** ответов в момент прохождения
(включая тексты вопросов/опций) — это позволяет редактировать или удалять
квиз/форму без потери истории прошлых попыток.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.form import Form, FormField
from app.models.funnel_step import FunnelStep
from app.models.lead import Lead
from app.models.quiz import Quiz, QuizOption, QuizQuestion, QuizVerdict
from app.models.user_step_state import UserStepState

logger = logging.getLogger(__name__)


# ───────────────────────── Events ─────────────────────────


@dataclass
class FlowMessage:
    text: str
    buttons: list[list[dict[str, Any]]] | None = None


@dataclass
class FlowResult:
    messages: list[FlowMessage] = field(default_factory=list)
    completed: bool = False
    cancelled: bool = False
    error: str | None = None
    lead_id: int | None = None


# ───────────────────────── Service ─────────────────────────


class StepFlowService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ===== общие хелперы =====

    async def _cancel_active(self, user_id: int, mode: str) -> None:
        now = datetime.now(tz=timezone.utc)
        await self.session.execute(
            update(UserStepState)
            .where(
                UserStepState.user_id == user_id,
                UserStepState.mode == mode,
                UserStepState.status == "in_progress",
            )
            .values(status="cancelled", completed_at=now)
        )

    async def get_active(self, user_id: int, mode: str) -> UserStepState | None:
        return (
            await self.session.execute(
                select(UserStepState).where(
                    UserStepState.user_id == user_id,
                    UserStepState.mode == mode,
                    UserStepState.status == "in_progress",
                )
            )
        ).scalar_one_or_none()

    async def _load_step_for(
        self, step_id: int, kind: str
    ) -> FunnelStep | None:
        step = await self.session.get(FunnelStep, step_id)
        if step is None or step.kind != kind or not step.is_active:
            return None
        return step

    # ===== QUIZ =====

    async def _load_quiz(self, quiz_id: int) -> Quiz | None:
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

    async def start_quiz(
        self, *, user_id: int, step_id: int, funnel_entry_id: int | None = None
    ) -> FlowResult:
        # Шаг-контейнер: kind='quiz', но is_active=False (он не уходит в расписание).
        # Поэтому используем прямую загрузку, без проверки is_active.
        step = await self.session.get(FunnelStep, step_id)
        if step is None or step.kind != "quiz" or step.quiz_id is None:
            return FlowResult(error="quiz_not_found")
        quiz = await self._load_quiz(step.quiz_id)
        if quiz is None or not quiz.questions:
            return FlowResult(error="quiz_empty")

        await self._cancel_active(user_id, "quiz")
        state = UserStepState(
            user_id=user_id,
            funnel_step_id=step_id,
            funnel_entry_id=funnel_entry_id,
            mode="quiz",
            current_idx=0,
            score=0,
            answers={"items": [], "quiz_id": quiz.id, "quiz_name": quiz.name},
            status="in_progress",
        )
        self.session.add(state)
        await self.session.flush()

        msg = self._quiz_question_message(state.id, quiz.questions, q_idx=0)
        return FlowResult(messages=[msg])

    async def answer_quiz(
        self, *, user_id: int, state_id: int, option_idx: int
    ) -> FlowResult:
        state = await self.session.get(UserStepState, state_id)
        if state is None or state.user_id != user_id or state.mode != "quiz":
            return FlowResult(error="state_not_found")
        if state.status != "in_progress":
            return FlowResult(error="not_in_progress")

        step = await self.session.get(FunnelStep, state.funnel_step_id)
        if step is None or step.quiz_id is None:
            return FlowResult(error="quiz_data_missing")
        quiz = await self._load_quiz(step.quiz_id)
        if quiz is None or not quiz.questions:
            return FlowResult(error="quiz_data_missing")

        q_idx = state.current_idx
        if q_idx >= len(quiz.questions):
            return FlowResult(error="quiz_overrun")
        question = quiz.questions[q_idx]
        options = question.options
        if not (0 <= option_idx < len(options)):
            return FlowResult(error="bad_option")

        option = options[option_idx]
        items = list((state.answers or {}).get("items") or [])
        items.append(
            {
                "q_idx": q_idx,
                "question_id": question.id,
                "q": question.text,
                "option_idx": option_idx,
                "option_id": option.id,
                "option": option.text,
                "score": option.score,
            }
        )
        new_answers = dict(state.answers or {})
        new_answers["items"] = items
        state.answers = new_answers
        state.score = int(state.score or 0) + int(option.score)
        state.current_idx = q_idx + 1
        state.updated_at = datetime.now(tz=timezone.utc)

        if state.current_idx < len(quiz.questions):
            msg = self._quiz_question_message(
                state.id, quiz.questions, q_idx=state.current_idx
            )
            return FlowResult(messages=[msg])

        # Финал — вердикт по score.
        verdict = self._pick_verdict(quiz.verdicts, state.score or 0)
        state.status = "completed"
        state.completed_at = datetime.now(tz=timezone.utc)

        if verdict is None:
            return FlowResult(
                messages=[FlowMessage(text=f"Тест завершён. Балл: {state.score}.")],
                completed=True,
            )

        msg = FlowMessage(
            text=verdict.text,
            buttons=self._verdict_buttons(verdict),
        )
        logger.info(
            "quiz.completed user_id=%s quiz_id=%s score=%s",
            user_id,
            quiz.id,
            state.score,
        )
        return FlowResult(messages=[msg], completed=True)

    def _quiz_question_message(
        self, state_id: int, questions: list[QuizQuestion], q_idx: int
    ) -> FlowMessage:
        q = questions[q_idx]
        text_lines: list[str] = []
        if q.prefix:
            text_lines.append(q.prefix)
        text_lines.append(q.text)
        buttons: list[list[dict[str, Any]]] = []
        for i, opt in enumerate(q.options):
            buttons.append(
                [
                    {
                        "text": opt.text,
                        "callback_data": f"qa:{state_id}:{i}",
                    }
                ]
            )
        return FlowMessage(text="\n\n".join(t for t in text_lines if t), buttons=buttons)

    def _pick_verdict(
        self, verdicts: list[QuizVerdict], score: int
    ) -> QuizVerdict | None:
        # отсортируем по max_score ASC, возьмём первый, у которого score <= max_score
        sorted_v = sorted(verdicts, key=lambda v: v.max_score)
        for v in sorted_v:
            if score <= v.max_score:
                return v
        return sorted_v[-1] if sorted_v else None

    def _verdict_buttons(
        self, verdict: QuizVerdict
    ) -> list[list[dict[str, Any]]] | None:
        if not verdict.button_text or not verdict.button_action:
            return None
        # Если в action есть '://' — это URL, иначе callback_data
        if "://" in verdict.button_action:
            return [[{"text": verdict.button_text, "url": verdict.button_action}]]
        return [
            [
                {
                    "text": verdict.button_text,
                    "callback_data": verdict.button_action,
                }
            ]
        ]

    # ===== FORM =====

    async def _load_form(self, form_id: int) -> Form | None:
        return (
            await self.session.execute(
                select(Form)
                .where(Form.id == form_id)
                .options(selectinload(Form.fields))
            )
        ).scalar_one_or_none()

    async def start_form(
        self, *, user_id: int, step_id: int, funnel_entry_id: int | None = None
    ) -> FlowResult:
        step = await self.session.get(FunnelStep, step_id)
        if step is None or step.kind != "form" or step.form_id is None:
            return FlowResult(error="form_not_found")
        form = await self._load_form(step.form_id)
        if form is None or not form.fields:
            return FlowResult(error="form_empty")

        await self._cancel_active(user_id, "form")
        state = UserStepState(
            user_id=user_id,
            funnel_step_id=step_id,
            funnel_entry_id=funnel_entry_id,
            mode="form",
            current_idx=0,
            answers={"form_id": form.id, "form_name": form.name},
            status="in_progress",
        )
        self.session.add(state)
        await self.session.flush()

        msg = self._form_field_message(state.id, form.fields, idx=0)
        return FlowResult(messages=[msg])

    async def submit_form_text(
        self, *, user_id: int, text: str
    ) -> FlowResult:
        state = await self.get_active(user_id, "form")
        if state is None:
            return FlowResult()

        step = await self.session.get(FunnelStep, state.funnel_step_id)
        if step is None or step.form_id is None:
            return FlowResult(error="form_data_missing")
        form = await self._load_form(step.form_id)
        if form is None or not form.fields:
            return FlowResult(error="form_data_missing")

        idx = state.current_idx
        if idx >= len(form.fields):
            return FlowResult(error="form_overrun")
        f = form.fields[idx]
        value = (text or "").strip()

        if value in {"-", "—", "нет", "no", "skip", "пропустить"}:
            if f.required:
                return FlowResult(
                    messages=[
                        FlowMessage(
                            text=(
                                "это поле обязательно. ответь по существу — "
                                "потом сможем продолжить."
                            )
                        )
                    ]
                )
            value = ""

        if f.required and not value:
            return FlowResult(
                messages=[
                    FlowMessage(
                        text="пожалуйста, ответь текстом — это поле обязательно."
                    )
                ],
            )

        if len(value) > f.max_length:
            value = value[: f.max_length]

        answers = dict(state.answers or {})
        answers[f.key] = value
        # Параллельно сохраняем «снимок» вопроса для аналитики
        snapshots = list(answers.get("__snapshots") or [])
        snapshots.append(
            {
                "field_id": f.id,
                "key": f.key,
                "question": f.question,
                "answer": value,
            }
        )
        answers["__snapshots"] = snapshots
        state.answers = answers
        state.current_idx = idx + 1
        state.updated_at = datetime.now(tz=timezone.utc)

        if state.current_idx < len(form.fields):
            msg = self._form_field_message(
                state.id, form.fields, idx=state.current_idx
            )
            return FlowResult(messages=[msg])

        return await self._complete_form(state, form)

    async def cancel_form(self, *, user_id: int, state_id: int) -> FlowResult:
        state = await self.session.get(UserStepState, state_id)
        if state is None or state.user_id != user_id or state.mode != "form":
            return FlowResult(error="state_not_found")
        if state.status != "in_progress":
            return FlowResult(error="not_in_progress")
        state.status = "cancelled"
        state.completed_at = datetime.now(tz=timezone.utc)
        step = await self.session.get(FunnelStep, state.funnel_step_id)
        cancel_text = None
        if step is not None and step.form_id is not None:
            form = await self.session.get(Form, step.form_id)
            if form is not None:
                cancel_text = form.cancel_message
        if not cancel_text:
            cancel_text = "Отменено. Когда будешь готов — наберёшь /start."
        return FlowResult(messages=[FlowMessage(text=cancel_text)], cancelled=True)

    async def _complete_form(self, state: UserStepState, form: Form) -> FlowResult:
        # Чистим technical keys из answers перед сохранением в Lead — оставляем
        # только user-видимые поля (по ключам формы) + __snapshots для истории.
        raw_answers = dict(state.answers or {})
        clean_answers: dict[str, Any] = {}
        for f in form.fields:
            if f.key in raw_answers:
                clean_answers[f.key] = raw_answers[f.key]

        extra_payload = {
            "answers": clean_answers,
            "form_id": form.id,
            "form_name": form.name,
            "snapshots": raw_answers.get("__snapshots") or [],
        }

        lead = Lead(
            user_id=state.user_id,
            product_id=form.product_id,
            status="new",
            form_step_id=state.funnel_step_id,
            extra_data=extra_payload,
        )
        self.session.add(lead)
        await self.session.flush()

        if form.product_id is not None:
            from app.models.product import Product

            product = await self.session.get(Product, form.product_id)
            if product is not None and getattr(product, "default_funnel_id", None):
                from app.services.funnels import FunnelsService

                funnels = FunnelsService(self.session)
                await funnels.start_for_user(
                    user_id=state.user_id,
                    funnel_id=product.default_funnel_id,
                    source="form_submission",
                    source_ref=lead.id,
                )

        state.status = "completed"
        state.completed_at = datetime.now(tz=timezone.utc)

        success_text = form.success_message or "готово, заявка принята."
        buttons = form.completion_buttons
        if isinstance(buttons, list) and buttons and not isinstance(buttons[0], list):
            buttons = [buttons]

        logger.info(
            "form.completed user_id=%s form_id=%s lead_id=%s",
            state.user_id,
            form.id,
            lead.id,
        )
        return FlowResult(
            messages=[FlowMessage(text=success_text, buttons=buttons)],
            completed=True,
            lead_id=lead.id,
        )

    def _form_field_message(
        self, state_id: int, fields: list[FormField], idx: int
    ) -> FlowMessage:
        f = fields[idx]
        total = len(fields)
        progress = f"{idx + 1}/{total}"
        head = f"{progress} · {f.prefix}" if f.prefix else progress
        text = f"{head}\n\n{f.question}"
        buttons = [
            [
                {
                    "text": "❌ отменить",
                    "callback_data": f"form:cancel:{state_id}",
                }
            ]
        ]
        return FlowMessage(text=text, buttons=buttons)
