"""StepFlowService — state-machine для quiz/form шагов воронки.

Управляет жизненным циклом UserStepState:
  * quiz:  start → answer → answer → … → completed (с подсчётом score и
            доставкой вердикта по score)
  * form:  start → text-ответ → text-ответ → … → completed (создаёт Lead
            с extra_data)

Все возвращаемые «события» — это плоские dataclass-объекты, чтобы
вызывающий хэндлер сам отрисовал их в Telegram (мы не таскаем сюда
aiogram-зависимости).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.funnel_step import FunnelStep
from app.models.lead import Lead
from app.models.user_step_state import UserStepState

logger = logging.getLogger(__name__)


# ───────────────────────── Events ─────────────────────────


@dataclass
class FlowMessage:
    """Сообщение, которое хэндлер должен отправить юзеру.

    `buttons` — двумерный массив (как в FunnelStep.buttons): rows × buttons.
    Каждая кнопка: {"text": str, "url": str?, "callback_data": str?}.
    """

    text: str
    buttons: list[list[dict[str, Any]]] | None = None


@dataclass
class FlowResult:
    """Итог обработки одного callback/text-сообщения внутри quiz/form."""

    messages: list[FlowMessage] = field(default_factory=list)
    completed: bool = False
    cancelled: bool = False
    error: str | None = None
    # для form: id созданного Lead'а
    lead_id: int | None = None


# ───────────────────────── Service ─────────────────────────


class StepFlowService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ===== общие хелперы =====

    async def _cancel_active(self, user_id: int, mode: str) -> None:
        """Сбрасывает текущее активное состояние юзера в данном режиме.

        Нужно при повторном `quiz:start` / `form:start` той же модели —
        partial-unique-индекс не даст создать второй активный.
        """
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

    async def _get_step(self, step_id: int, kind: str) -> FunnelStep | None:
        step = await self.session.get(FunnelStep, step_id)
        if step is None or step.kind != kind or not step.is_active:
            return None
        return step

    # ===== QUIZ =====

    async def start_quiz(
        self, *, user_id: int, step_id: int, funnel_entry_id: int | None = None
    ) -> FlowResult:
        step = await self._get_step(step_id, "quiz")
        if step is None or not step.quiz_data:
            return FlowResult(error="quiz_not_found")
        questions = step.quiz_data.get("questions") or []
        if not questions:
            return FlowResult(error="quiz_empty")

        await self._cancel_active(user_id, "quiz")
        state = UserStepState(
            user_id=user_id,
            funnel_step_id=step_id,
            funnel_entry_id=funnel_entry_id,
            mode="quiz",
            current_idx=0,
            score=0,
            answers={"items": []},
            status="in_progress",
        )
        self.session.add(state)
        await self.session.flush()

        msg = self._quiz_question_message(state, questions, q_idx=0)
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
        if step is None or not step.quiz_data:
            return FlowResult(error="quiz_data_missing")
        questions = step.quiz_data.get("questions") or []
        q_idx = state.current_idx
        if q_idx >= len(questions):
            return FlowResult(error="quiz_overrun")
        question = questions[q_idx]
        options = question.get("options") or []
        if not (0 <= option_idx < len(options)):
            return FlowResult(error="bad_option")

        option = options[option_idx]
        option_score = int(option.get("score") or 0)
        # Иммутабельно — Postgres JSONB обновляет только при reassign.
        items = list((state.answers or {}).get("items") or [])
        items.append(
            {
                "q_idx": q_idx,
                "q": question.get("text"),
                "option_idx": option_idx,
                "option": option.get("text"),
                "score": option_score,
            }
        )
        state.answers = {"items": items}
        state.score = int(state.score or 0) + option_score
        state.current_idx = q_idx + 1
        state.updated_at = datetime.now(tz=timezone.utc)

        # Следующий вопрос?
        if state.current_idx < len(questions):
            msg = self._quiz_question_message(state, questions, q_idx=state.current_idx)
            return FlowResult(messages=[msg])

        # Финал — вердикт по score.
        verdict = self._pick_verdict(step.quiz_data, state.score or 0)
        state.status = "completed"
        state.completed_at = datetime.now(tz=timezone.utc)

        if verdict is None:
            return FlowResult(
                messages=[FlowMessage(text=f"Тест завершён. Балл: {state.score}.")],
                completed=True,
            )

        msg = FlowMessage(
            text=verdict.get("text") or "",
            buttons=self._verdict_buttons(verdict),
        )
        logger.info(
            "quiz.completed user_id=%s step_id=%s score=%s",
            user_id,
            step.id,
            state.score,
        )
        return FlowResult(messages=[msg], completed=True)

    def _quiz_question_message(
        self, state: UserStepState, questions: list[dict[str, Any]], q_idx: int
    ) -> FlowMessage:
        q = questions[q_idx]
        text_lines = []
        prefix = q.get("prefix")
        if prefix:
            text_lines.append(prefix)
        text_lines.append(q.get("text") or "")
        options = q.get("options") or []
        buttons: list[list[dict[str, Any]]] = []
        for i, opt in enumerate(options):
            buttons.append(
                [
                    {
                        "text": opt.get("text") or f"вариант {i + 1}",
                        "callback_data": f"qa:{state.id}:{i}",
                    }
                ]
            )
        return FlowMessage(text="\n\n".join(t for t in text_lines if t), buttons=buttons)

    def _pick_verdict(self, quiz_data: dict[str, Any], score: int) -> dict[str, Any] | None:
        verdicts = quiz_data.get("verdicts") or []
        # отсортируем по max_score ASC, возьмём первый, у которого score <= max_score
        sorted_v = sorted(verdicts, key=lambda v: v.get("max_score", 1_000_000))
        for v in sorted_v:
            if score <= int(v.get("max_score", 1_000_000)):
                return v
        return sorted_v[-1] if sorted_v else None

    def _verdict_buttons(self, verdict: dict[str, Any]) -> list[list[dict[str, Any]]] | None:
        btns = verdict.get("buttons") or verdict.get("button")
        if isinstance(btns, dict):
            return [[btns]]
        if isinstance(btns, list):
            # уже 2D?
            if btns and isinstance(btns[0], list):
                return btns
            return [btns]
        return None

    # ===== FORM =====

    async def start_form(
        self, *, user_id: int, step_id: int, funnel_entry_id: int | None = None
    ) -> FlowResult:
        step = await self._get_step(step_id, "form")
        if step is None or not step.form_data:
            return FlowResult(error="form_not_found")
        fields = step.form_data.get("fields") or []
        if not fields:
            return FlowResult(error="form_empty")

        await self._cancel_active(user_id, "form")
        state = UserStepState(
            user_id=user_id,
            funnel_step_id=step_id,
            funnel_entry_id=funnel_entry_id,
            mode="form",
            current_idx=0,
            answers={},
            status="in_progress",
        )
        self.session.add(state)
        await self.session.flush()

        msg = self._form_field_message(state, fields, idx=0)
        return FlowResult(messages=[msg])

    async def submit_form_text(
        self, *, user_id: int, text: str
    ) -> FlowResult:
        """Принять текстовый ответ от юзера на текущее поле активной формы.

        Если у юзера нет активной формы — возвращает FlowResult без сообщений
        (вызывающий должен трактовать это как «формы нет, продолжай обычную обработку»).
        """
        state = await self.get_active(user_id, "form")
        if state is None:
            return FlowResult()

        step = await self.session.get(FunnelStep, state.funnel_step_id)
        if step is None or not step.form_data:
            return FlowResult(error="form_data_missing")
        fields = step.form_data.get("fields") or []
        idx = state.current_idx
        if idx >= len(fields):
            return FlowResult(error="form_overrun")
        f = fields[idx]
        key = f.get("key") or f"field_{idx}"
        value = (text or "").strip()
        # «-» / «нет» считаем пустым ответом
        if value in {"-", "—", "нет", "no", "skip", "пропустить"}:
            if f.get("required", True):
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

        if f.get("required", True) and not value:
            return FlowResult(
                messages=[FlowMessage(text="пожалуйста, ответь текстом — это поле обязательно.")],
            )

        max_len = int(f.get("max_length") or 500)
        if len(value) > max_len:
            value = value[:max_len]

        answers = dict(state.answers or {})
        answers[key] = value
        state.answers = answers
        state.current_idx = idx + 1
        state.updated_at = datetime.now(tz=timezone.utc)

        if state.current_idx < len(fields):
            msg = self._form_field_message(state, fields, idx=state.current_idx)
            return FlowResult(messages=[msg])

        # Все поля собраны — создаём Lead, шлём success-сообщение.
        return await self._complete_form(state, step)

    async def cancel_form(self, *, user_id: int, state_id: int) -> FlowResult:
        state = await self.session.get(UserStepState, state_id)
        if state is None or state.user_id != user_id or state.mode != "form":
            return FlowResult(error="state_not_found")
        if state.status != "in_progress":
            return FlowResult(error="not_in_progress")
        state.status = "cancelled"
        state.completed_at = datetime.now(tz=timezone.utc)
        cancel_text = (state.answers or {}).get("__cancel_text") if False else None
        step = await self.session.get(FunnelStep, state.funnel_step_id)
        cancel_text = (
            (step.form_data or {}).get("cancel_message")
            if step is not None
            else None
        ) or "Отменено. Когда будешь готов — наберёшь /start."
        return FlowResult(messages=[FlowMessage(text=cancel_text)], cancelled=True)

    async def _complete_form(self, state: UserStepState, step: FunnelStep) -> FlowResult:
        form_data = step.form_data or {}
        answers = state.answers or {}

        # Создаём Lead
        product_id = form_data.get("product_id")
        lead = Lead(
            user_id=state.user_id,
            product_id=product_id,
            status="new",
            form_step_id=step.id,
            extra_data=answers,
        )
        self.session.add(lead)
        await self.session.flush()

        # NEW: autostart default-воронки продукта, если есть и юзер не в ней
        if product_id is not None:
            from app.models.product import Product

            product = await self.session.get(Product, product_id)
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

        success_text = (
            form_data.get("success_message")
            or "готово, заявка принята."
        )
        buttons = form_data.get("completion_buttons")
        if isinstance(buttons, list) and buttons and not isinstance(buttons[0], list):
            buttons = [buttons]

        logger.info(
            "form.completed user_id=%s step_id=%s lead_id=%s",
            state.user_id,
            step.id,
            lead.id,
        )
        return FlowResult(
            messages=[FlowMessage(text=success_text, buttons=buttons)],
            completed=True,
            lead_id=lead.id,
        )

    def _form_field_message(
        self, state: UserStepState, fields: list[dict[str, Any]], idx: int
    ) -> FlowMessage:
        f = fields[idx]
        total = len(fields)
        progress = f"{idx + 1}/{total}"
        prefix = f.get("prefix")
        head = f"{progress} · {prefix}" if prefix else progress
        question = f.get("question") or f.get("label") or f"поле {idx + 1}"
        text = f"{head}\n\n{question}"
        # Кнопка отмены формы — кроме первого поля можно и в первом, для простоты везде.
        buttons = [
            [
                {
                    "text": "❌ отменить",
                    "callback_data": f"form:cancel:{state.id}",
                }
            ]
        ]
        return FlowMessage(text=text, buttons=buttons)
