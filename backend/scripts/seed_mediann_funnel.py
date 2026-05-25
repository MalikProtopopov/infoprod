"""Сидер: воронка Mediann «Стартапы / MVP (AI)» (14-дневный пилот).

Идемпотентный. Создаёт/обновляет:
  * stub-канал "Mediann internal" (для FK Product → Channel),
  * продукт code='mediann_mvp_pilot',
  * lead_magnet "15 пунктов перед запуском MVP" (если задан --pdf),
  * воронку "Mediann · MVP pilot" со всеми шагами D0–D14 + quiz/form,
  * trigger-word "MVP" (case-insensitive).

Шаги quiz/form маркируются is_active=False — они не уходят в расписание,
а используются как «контейнеры» данных, на которые ссылаются inline-кнопки
сообщений-шагов (callback_data = quiz:start:{id} / form:start:{id}).

Запуск из контейнера:
    docker compose exec backend python -m scripts.seed_mediann_funnel \
        --pdf /var/lib/seeddata/15-pdf.pdf

Без --pdf скрипт всё равно создаст воронку, но шаг D0 пойдёт без PDF
(текст всё равно отправится).
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select, delete

from app.db.session import SessionLocal
from app.models.bot import Bot as BotModel
from app.models.channel import Channel
from app.models.funnel import Funnel
from app.models.funnel_step import FunnelStep
from app.models.funnel_trigger import FunnelTrigger
from app.models.product import Product
from app.services.step_media import StepMediaService

logger = logging.getLogger("seed_mediann")
logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s — %(message)s")


PRODUCT_CODE = "mediann_mvp_pilot"
PRODUCT_NAME = "Стартапы / MVP (AI)"
FUNNEL_NAME = "Mediann · MVP pilot"
CHANNEL_TITLE = "Mediann internal"
TRIGGERS = ["MVP", "mvp", "Mvp"]


# ───────────────────────── Templates ─────────────────────────


D0_TEXT = """привет. это бот mediann.

лови pdf «15 пунктов перед запуском mvp» — 20 минут чтения экономят 3 месяца, а часто и несколько миллионов.

сегодня прочитай только часть 1 — стратегия, 5 пунктов. завтра пришлю, как применить её к твоему проекту.

с 2022 мы вывели в прод 30+ проектов в 4 странах. знаем, на чём фаундеры горят чаще всего."""


D1_TEXT = """как читать эти 15 пунктов, чтобы не зря.

по каждому: что это → как проверить → типовая ошибка → что делают опытные. в конце — сводный чек-лист на одной странице. отмечай ✓ или ✗.

правило:
0–1 ✗ — ты готов делать mvp.
2–3 ✗ — есть слабые места, лучше разобрать до старта.
4+ ✗ — рано, сначала закрой пункты.

сколько у тебя уже закрыто?"""


D3_TEXT = """реальная история. без имён.

фаундер пришёл к нам после 4 месяцев с другой студией. $60k потрачено, кода почти нет, документации никакой, ключевые разрабы уже «в других проектах». мы сделали техаудит за 2 дня — и да, пришлось начинать заново.

ошибка была не в коде. он пропустил 3 пункта ещё до старта: не сформулировал гипотезу, не зафиксировал скоуп, не прописал ip и handoff в договоре.

сигналы провала видны уже ко второй неделе. не бойся менять подрядчика в середине — бойся остаться с мёртвым продуктом."""


D4_TEXT = """короткий тест: готов ли твой mvp к запуску.

5 вопросов, 1 минута. в конце — честный вердикт и что делать дальше. прямо здесь, без сбора почты.

это те же 5 точек, на которых валятся 9 из 10 проектов."""


D6_TEXT = """кейс. matchtender — ai-платформа для госзакупок.

ДО: менеджер собирал одно коммерческое предложение по тендеру 3–4 часа вручную. объём не рос без новых найма.

что сделали: два ai-агента — parseragent разбирает спецификацию (85%+ позиций), matcheragent подбирает товары из каталога (80%+ автоматом). 100+ rest-эндпоинтов, очереди, redis, мониторинг prometheus/grafana.

ПОСЛЕ: кп за ~45 минут вместо 3–4 часов. один менеджер закрывает объём троих. собрали за ~3 недели.

это не «сайт с кнопкой ии». это прод-архитектура под нагрузку."""


D8_TEXT = """как мы укладываем mvp в 30 дней — без магии, по процессу.

неделя 1 — discovery: user journey, архитектура, стек.
неделя 2 — бэкенд + авторизация.
неделя 3 — ключевой сценарий end-to-end.
неделя 4 — qa + деплой + мониторинг + доки.

команда небольшая и senior: архитектор, бэкенд с опытом в llm-мультиагентных системах, мобильщик-лид. каждые 2 недели — рабочая сборка, не «к лету». каждый спринт — короткий отчёт: что готово / что не готово / что сдвинулось."""


D10_TEXT = """честно: фриланс vs штат vs студия — когда что.

фриланс — дёшево, но нет гарантий, доков и ответственности за результат.
штат — полный контроль, но месяцы на найм и зарплаты до того, как гипотеза подтвердилась.
студия (мы) — mvp за 30–60 дней, договор, прод-архитектура, код, который твой и который продолжат.

если нужно проверить гипотезу быстро и выйти в прод — это наш кейс. штат имеет смысл уже после того, как гипотеза подтвердилась.

разберём твой проект на 30-минутном аудите. бесплатно, без скрипта продаж. оставь заявку — свяжусь лично."""


D11_TEXT = """30+ проектов с 2022 — это не только ai. широта:

• yastvo — ai-нутрициолог: фото блюда → кбжу. убрали ручной ввод как класс, retention d7 ~32%.
• 911 service — выездной шиномонтаж: 1042 заказа за первый месяц, 0 звонков диспетчеру.
• likemenow — saas для smm: 30 000 пользователей за 45 дней.
• karjewy — ювелирный магазин: вернули 100% заявок, чек 100к–млн ₽.
• charex — обменник с aml: готов к 7 странам без передизайна.

берём ограниченное число проектов в работу одновременно. напиши — скажу, есть ли окно в этом месяце."""


D13_TEXT = """последнее сообщение от меня в этом боте.

я малик, отвечаю за продукт и веду клиентов в mediann. за 2 недели ты получил наш чек-лист, тест и пару кейсов. без давления: если сейчас не время — это нормально, вернись когда будет нужно.

но если дочитал до сюда — у тебя, скорее всего, есть продукт в голове и желание не слить деньги впустую. ровно для этого аудит и нужен. 30 минут, разберём твой случай, дам вилку и стек под задачу.

оставь заявку — дальше свяжусь лично. сообщений из бота больше не будет."""


D14_TEXT = """дверь закрыта, но не заперта.

остановил рассылку, чтобы не надоедать. если захочешь — подпишись на канал: там кейсы, разборы и процесс изнутри, без спама.

→ @medianndev
когда будешь готов к разбору — ты знаешь, где нас найти. work@mediann.dev"""


# ───────────────────────── Quiz / Form data ─────────────────────────


QUIZ_DATA: dict[str, Any] = {
    "questions": [
        {
            "prefix": "тест: 5 вопросов · вопрос 1/5",
            "text": (
                "можешь сказать гипотезу вслух за 10 секунд: "
                "«если [решение] → пользователь [действие] → это даст [измеримый результат]»?"
            ),
            "options": [
                {"text": "✓ да", "score": 0},
                {"text": "✗ нет", "score": 1},
            ],
        },
        {
            "prefix": "вопрос 2/5",
            "text": "у тебя есть метрика успеха = число + срок + сегмент (а не «всем понравится»)?",
            "options": [
                {"text": "✓ да", "score": 0},
                {"text": "✗ нет", "score": 1},
            ],
        },
        {
            "prefix": "вопрос 3/5",
            "text": "можешь назвать 5 конкретных людей, которые попробуют продукт первыми?",
            "options": [
                {"text": "✓ да", "score": 0},
                {"text": "✗ нет", "score": 1},
            ],
        },
        {
            "prefix": "вопрос 4/5",
            "text": "скоуп разбит на mvp / v1 / v2 и ты готов резать лишние фичи?",
            "options": [
                {"text": "✓ да", "score": 0},
                {"text": "✗ нет", "score": 1},
            ],
        },
        {
            "prefix": "вопрос 5/5",
            "text": "знаешь, сколько готов потерять, если гипотеза не взлетит, и заложен ли 10% буфер?",
            "options": [
                {"text": "✓ да", "score": 0},
                {"text": "✗ нет", "score": 1},
            ],
        },
    ],
    # verdicts[].max_score — берётся первый, у которого score <= max_score
    # buttons.callback_data будет проставлен после создания form-шага
    "verdicts": [
        {
            "max_score": 1,
            "text": (
                "результат: 0–1 минус. ты готов делать mvp.\n\n"
                "следующий шаг — зафиксировать скоуп и вилку. оставь заявку — "
                "за 30 минут дам стек и план под задачу."
            ),
            "button": {"text": "оставить заявку →", "callback_data": "form:start:FORM_STEP_ID"},
        },
        {
            "max_score": 3,
            "text": (
                "результат: 2–3 минуса. идея живая, но есть слабые места — "
                "на них обычно и теряют деньги.\n\n"
                "ровно их разбираем на аудите. бесплатно, без продажи. "
                "придёшь — выйдешь с конкретным планом."
            ),
            "button": {"text": "разобрать слабые места →", "callback_data": "form:start:FORM_STEP_ID"},
        },
        {
            "max_score": 999,
            "text": (
                "результат: 4+ минусов. запускаться сейчас — риск слить бюджет. "
                "сначала закрой пункты из pdf (часть 1).\n\n"
                "хочешь — на аудите за 30 минут поможем расставить приоритеты, "
                "с чего начать. без обязательств."
            ),
            "button": {"text": "получить приоритеты →", "callback_data": "form:start:FORM_STEP_ID"},
        },
    ],
}


def _form_data(product_id: int) -> dict[str, Any]:
    return {
        "product_id": product_id,
        "fields": [
            {
                "key": "name",
                "question": "как зовут?",
                "required": True,
                "max_length": 120,
            },
            {
                "key": "stage",
                "question": (
                    "что за продукт и на какой стадии?\n"
                    "(идея / прототип / есть mvp — коротко)"
                ),
                "required": True,
                "max_length": 300,
            },
            {
                "key": "problem",
                "question": "что не получается прямо сейчас? пара предложений.",
                "required": True,
                "max_length": 500,
            },
            {
                "key": "contact",
                "question": "как удобнее связаться? telegram-ник или телефон.",
                "required": True,
                "max_length": 120,
            },
            {
                "key": "link",
                "question": (
                    "ссылка на лендинг / прототип / notion — если есть.\n"
                    "(можно пропустить — отправь «-»)"
                ),
                "required": False,
                "max_length": 300,
            },
        ],
        "success_message": (
            "готово. малик свяжется с тобой лично в течение 24 часов — "
            "назначим время разбора.\n\n"
            "а пока можешь подготовиться: открой ссылку на прототип (если есть), "
            "пример конкурента, который нравится, и держи в голове 1 цифру — "
            "сколько готов вложить в проверку гипотезы."
        ),
        "cancel_message": (
            "отменено. вернись когда будешь готов — наберёшь /start, "
            "и мы продолжим оттуда же."
        ),
        "completion_buttons": [
            [{"text": "🏠 главное меню", "callback_data": "menu:main"}],
        ],
    }


# ───────────────────────── Helpers ─────────────────────────


async def _ensure_channel(session) -> Channel:
    """Гарантирует наличие stub-канала для FK Product → Channel.

    Если есть хотя бы один канал — берём первый. Иначе создаём stub,
    привязав к первому активному боту (или, если ботов нет, создаём
    placeholder-бот).
    """
    ch = (await session.execute(select(Channel).order_by(Channel.id).limit(1))).scalar_one_or_none()
    if ch is not None:
        return ch

    bot_row = (
        await session.execute(select(BotModel).order_by(BotModel.id).limit(1))
    ).scalar_one_or_none()
    if bot_row is None:
        logger.error(
            "В БД нет ни одного бота — нельзя создать stub-канал. "
            "Создайте бот в админке и перезапустите seed."
        )
        raise SystemExit(1)

    ch = Channel(
        telegram_chat_id=-100000000 - bot_row.id,  # уникальный отрицательный
        title=CHANNEL_TITLE,
        bot_id=bot_row.id,
    )
    session.add(ch)
    await session.flush()
    logger.info("created stub channel id=%s", ch.id)
    return ch


async def _ensure_product(session, channel_id: int) -> Product:
    p = (
        await session.execute(select(Product).where(Product.code == PRODUCT_CODE))
    ).scalar_one_or_none()
    if p is not None:
        # обновим имя/canal на актуальные
        p.name = PRODUCT_NAME
        p.is_active = True
        return p
    p = Product(
        code=PRODUCT_CODE,
        name=PRODUCT_NAME,
        description=(
            "Mediann — разработка под ключ. Пилот: стартапы / MVP с AI-логикой. "
            "Бесплатный 30-минутный аудит → ТЗ → проект."
        ),
        channel_id=channel_id,
        price_3m=0,
        price_6m=0,
        price_12m=0,
        currency="RUB",
        is_active=True,
    )
    session.add(p)
    await session.flush()
    logger.info("created product %s id=%s", PRODUCT_CODE, p.id)
    return p


async def _clear_existing_funnel(session) -> None:
    """Удаляем старый seed-funnel (cascade → steps, step_media, scheduled, entries)."""
    funnels = (
        await session.execute(select(Funnel).where(Funnel.name == FUNNEL_NAME))
    ).scalars().all()
    for f in funnels:
        await session.execute(delete(Funnel).where(Funnel.id == f.id))
        logger.info("deleted existing funnel id=%s name=%s", f.id, f.name)


async def _create_funnel(session, product_id: int, bot_id: int | None) -> Funnel:
    funnel = Funnel(
        name=FUNNEL_NAME,
        description="14-дневный пилот Mediann · стартапы/MVP. Quiz на D4, форма-заявка как конвертер.",
        product_id=product_id,
        bot_id=bot_id,
        ttl_days=30,
        cancel_on_payment=False,
        is_active=True,
    )
    session.add(funnel)
    await session.flush()
    logger.info("created funnel id=%s", funnel.id)
    return funnel


def _btn_url(text: str, url: str) -> dict[str, Any]:
    return {"text": text, "url": url}


def _btn_cb(text: str, callback_data: str) -> dict[str, Any]:
    return {"text": text, "callback_data": callback_data}


async def _create_step(
    session,
    funnel_id: int,
    *,
    order_idx: int,
    delay_minutes: int,
    text: str,
    kind: str = "message",
    is_active: bool = True,
    buttons: list[list[dict[str, Any]]] | None = None,
    quiz_data: dict[str, Any] | None = None,
    form_data: dict[str, Any] | None = None,
) -> FunnelStep:
    step = FunnelStep(
        funnel_id=funnel_id,
        order_idx=order_idx,
        delay_minutes=delay_minutes,
        message_text=text,
        parse_mode=None,  # plain text, без HTML — наши тексты в lower-case без тегов
        buttons=buttons,
        is_active=is_active,
        kind=kind,
        quiz_data=quiz_data,
        form_data=form_data,
    )
    session.add(step)
    await session.flush()
    return step


async def _upsert_trigger(session, funnel_id: int, word: str) -> None:
    word_lc = word.strip().lower()
    existing = (
        await session.execute(
            select(FunnelTrigger).where(FunnelTrigger.word == word_lc)
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.funnel_id = funnel_id
        existing.is_active = True
        return
    session.add(
        FunnelTrigger(word=word_lc, funnel_id=funnel_id, is_active=True)
    )


async def _attach_pdf_to_step(session, step_id: int, pdf_path: Path) -> None:
    if not pdf_path.exists():
        logger.warning("PDF не найден по пути %s — пропускаем загрузку", pdf_path)
        return
    content = pdf_path.read_bytes()
    svc = StepMediaService(session)
    media = await svc.upload(
        step_id=step_id,
        content=content,
        original_filename=pdf_path.name,
        declared_mime="application/pdf",
        caption=None,
    )
    logger.info(
        "attached PDF to step %s as media_id=%s size=%s",
        step_id,
        media.id,
        media.file_size,
    )


# ───────────────────────── Main ─────────────────────────


async def main(pdf_path: Path | None) -> None:
    async with SessionLocal() as session:
        channel = await _ensure_channel(session)

        # Используем bot_id канала для воронки (1 бот = 1 проект)
        bot_id = channel.bot_id

        product = await _ensure_product(session, channel.id)

        await _clear_existing_funnel(session)
        funnel = await _create_funnel(session, product.id, bot_id)

        # Создаём шаги. order_idx — порядок в админке. delay_minutes —
        # отсчёт от старта entry для message-шагов.
        # quiz/form-шаги — контейнеры данных, is_active=False, не уходят
        # в расписание.

        # 1) Сначала создаём FORM-step (нужен ID для callback'ов из quiz и других CTA).
        form_step = await _create_step(
            session,
            funnel.id,
            order_idx=100,
            delay_minutes=0,
            text="(контейнер формы — не отправляется напрямую)",
            kind="form",
            is_active=False,
            form_data=_form_data(product.id),
        )
        form_cb = f"form:start:{form_step.id}"
        logger.info("created FORM step id=%s", form_step.id)

        # 2) QUIZ-step (ID нужен для callback из D4).
        quiz_data = _patch_quiz_form_refs(QUIZ_DATA, form_step.id)
        quiz_step = await _create_step(
            session,
            funnel.id,
            order_idx=101,
            delay_minutes=0,
            text="(контейнер квиза — не отправляется напрямую)",
            kind="quiz",
            is_active=False,
            quiz_data=quiz_data,
        )
        quiz_cb = f"quiz:start:{quiz_step.id}"
        logger.info("created QUIZ step id=%s", quiz_step.id)

        # 3) Message-шаги по дням.
        # D0 (мгновенно при подписке)
        d0 = await _create_step(
            session, funnel.id,
            order_idx=0, delay_minutes=0, text=D0_TEXT,
        )

        # D1: +1 день. Без кнопок — просто текстовый вопрос.
        await _create_step(
            session, funnel.id,
            order_idx=1, delay_minutes=60 * 24, text=D1_TEXT,
        )

        # D3: +3 дня.
        await _create_step(
            session, funnel.id,
            order_idx=2, delay_minutes=60 * 24 * 3, text=D3_TEXT,
        )

        # D4: +4 дня → запуск квиза
        await _create_step(
            session, funnel.id,
            order_idx=3, delay_minutes=60 * 24 * 4, text=D4_TEXT,
            buttons=[[_btn_cb("начать тест →", quiz_cb)]],
        )

        # D6: +6 дней → soft CTA
        await _create_step(
            session, funnel.id,
            order_idx=4, delay_minutes=60 * 24 * 6, text=D6_TEXT,
            buttons=[[_btn_cb("хочу так же — оставить заявку →", form_cb)]],
        )

        # D8: +8 дней
        await _create_step(
            session, funnel.id,
            order_idx=5, delay_minutes=60 * 24 * 8, text=D8_TEXT,
            buttons=[[_btn_url("показать полный pipeline →", "https://mediann.dev/portfolio")]],
        )

        # D10: +10 дней → hard CTA
        await _create_step(
            session, funnel.id,
            order_idx=6, delay_minutes=60 * 24 * 10, text=D10_TEXT,
            buttons=[[_btn_cb("оставить заявку на разбор →", form_cb)]],
        )

        # D11: +11 дней → галерея + дефицит
        await _create_step(
            session, funnel.id,
            order_idx=7, delay_minutes=60 * 24 * 11, text=D11_TEXT,
            buttons=[[_btn_cb("оставить заявку на разбор →", form_cb)]],
        )

        # D13: +13 дней — личное от Малика
        await _create_step(
            session, funnel.id,
            order_idx=8, delay_minutes=60 * 24 * 13, text=D13_TEXT,
            buttons=[[_btn_cb("оставить заявку на разбор →", form_cb)]],
        )

        # D14: +14 дней — финал
        await _create_step(
            session, funnel.id,
            order_idx=9, delay_minutes=60 * 24 * 14, text=D14_TEXT,
            buttons=[[_btn_url("подписаться на канал →", "https://t.me/medianndev")]],
        )

        # 4) PDF на D0
        if pdf_path is not None:
            await _attach_pdf_to_step(session, d0.id, pdf_path)

        # 5) Триггер-слово "MVP" (несколько кейсов, все в lower)
        for w in TRIGGERS:
            await _upsert_trigger(session, funnel.id, w)

        await session.commit()

        logger.info("=" * 60)
        logger.info("Воронка собрана. funnel_id=%s product_id=%s", funnel.id, product.id)
        logger.info("Quiz step id: %s  (cb: %s)", quiz_step.id, quiz_cb)
        logger.info("Form step id: %s  (cb: %s)", form_step.id, form_cb)
        logger.info("Триггер-слово: «MVP» (и любой регистр)")
        logger.info("=" * 60)


def _patch_quiz_form_refs(quiz_data: dict[str, Any], form_step_id: int) -> dict[str, Any]:
    """Подставить актуальный form_step_id в callback_data вердиктов квиза."""
    import copy

    qd = copy.deepcopy(quiz_data)
    for v in qd.get("verdicts") or []:
        btn = v.get("button")
        if isinstance(btn, dict) and btn.get("callback_data") == "form:start:FORM_STEP_ID":
            btn["callback_data"] = f"form:start:{form_step_id}"
    return qd


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Сидер воронки Mediann · MVP pilot")
    parser.add_argument(
        "--pdf",
        type=str,
        default=os.environ.get("MEDIANN_PDF_PATH"),
        help=(
            "Абсолютный путь к PDF «15 пунктов перед запуском MVP». "
            "Если не задан — D0 будет без PDF."
        ),
    )
    args = parser.parse_args()
    pdf_arg = Path(args.pdf) if args.pdf else None
    try:
        asyncio.run(main(pdf_arg))
    except KeyboardInterrupt:
        sys.exit(1)
