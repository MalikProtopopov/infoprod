from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts
from app.db.session import SessionLocal
from app.models.bot import Bot as BotModel
from app.models.channel import Channel
from app.models.lead import Lead
from app.models.product import Product
from app.models.subscription import Subscription
from app.models.tracking_link import TrackingLink
from app.models.user import User
from app.services.step_flow import FlowMessage, FlowResult, StepFlowService
from app.services.tracking_links import TrackingLinksService

logger = logging.getLogger(__name__)

router = Router(name="public")

# TTL контекста ссылки между /start и нажатием «Оставить заявку»
CURRENT_LINK_TTL = timedelta(minutes=30)


async def _resolve_bot_id(session: AsyncSession, aiogram_bot: Bot) -> int | None:
    """Берём internal id нашего бота по его telegram_bot_id."""
    me = await aiogram_bot.get_me()
    row = (
        await session.execute(select(BotModel.id).where(BotModel.telegram_bot_id == me.id))
    ).scalar_one_or_none()
    return row


async def _upsert_user(
    session: AsyncSession, m: Message | CallbackQuery
) -> tuple[User, bool]:
    """Создаёт или обновляет пользователя. Возвращает (user, is_new)."""
    tg_user = m.from_user
    if tg_user is None:
        raise RuntimeError("from_user is empty")
    user = (
        await session.execute(select(User).where(User.telegram_user_id == tg_user.id))
    ).scalar_one_or_none()
    if user is None:
        user = User(
            telegram_user_id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
            last_name=tg_user.last_name,
            language_code=tg_user.language_code,
        )
        session.add(user)
        await session.flush()
        return user, True
    user.username = tg_user.username
    user.first_name = tg_user.first_name
    user.last_name = tg_user.last_name
    user.language_code = tg_user.language_code
    user.last_seen_at = datetime.now(tz=timezone.utc)
    return user, False


async def _set_first_touch(
    session: AsyncSession,
    *,
    user_id: int,
    bot_id: int | None,
    product_id: int | None,
    tracking_link: TrackingLink | None,
) -> None:
    """Заполнить first-touch поля. Идемпотентно — если уже было записано (first_bot_id IS NOT NULL),
    UPDATE не выполнится."""
    fields: dict = {}
    if bot_id is not None:
        fields["first_bot_id"] = bot_id
    if product_id is not None:
        fields["first_product_id"] = product_id
    if tracking_link is not None:
        fields["first_tracking_link_id"] = tracking_link.id
        fields["first_utm_source"] = tracking_link.utm_source
        fields["first_utm_medium"] = tracking_link.utm_medium
        fields["first_utm_campaign"] = tracking_link.utm_campaign
    if not fields:
        return
    await session.execute(
        update(User)
        .where(User.id == user_id, User.first_bot_id.is_(None))
        .values(**fields)
    )


async def _set_current_link(session: AsyncSession, user_id: int, tracking_link_id: int) -> None:
    await session.execute(
        update(User)
        .where(User.id == user_id)
        .values(
            current_tracking_link_id=tracking_link_id,
            current_link_set_at=datetime.now(tz=timezone.utc),
        )
    )


def _product_kb(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Оставить заявку", callback_data=f"lead:{product_id}")]
        ]
    )


def _catalog_kb(products: list[Product]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for p in products:
        rows.append([InlineKeyboardButton(text=p.name, callback_data=f"prod:{p.id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _send_product_card(target: Message | CallbackQuery, product: Product) -> None:
    text = texts.product_card(
        product.name,
        product.description,
        product.price_3m,
        product.price_6m,
        product.price_12m,
        product.currency,
    )
    msg = target if isinstance(target, Message) else target.message
    await msg.answer(text, reply_markup=_product_kb(product.id), parse_mode=ParseMode.HTML)


async def _send_catalog(target: Message, products: list[Product]) -> None:
    if not products:
        await target.answer(texts.NO_PRODUCTS)
        return
    await target.answer(texts.WELCOME, reply_markup=_catalog_kb(products))


# ===================== /start =====================

@router.message(CommandStart(deep_link=True))
async def start_with_arg(m: Message, command: CommandObject, bot: Bot) -> None:
    arg = (command.args or "").strip()
    async with SessionLocal() as session:
        tl_service = TrackingLinksService(session)
        our_bot_id = await _resolve_bot_id(session, bot)

        # Шаг 1: резолв — приоритет slug, fallback на product.code
        tracking_link: TrackingLink | None = None
        product: Product | None = None

        if arg:
            tracking_link = await tl_service.find_by_slug(arg)
            if tracking_link and tracking_link.is_active:
                product = (
                    await session.execute(
                        select(Product).where(
                            Product.id == tracking_link.product_id,
                            Product.is_active.is_(True),
                        )
                    )
                ).scalar_one_or_none()
                # клик считаем всегда, даже если продукт уже неактивен
                await tl_service.increment_click_count(tracking_link.id)
            else:
                tracking_link = None
                product = (
                    await session.execute(
                        select(Product).where(
                            Product.code == arg, Product.is_active.is_(True)
                        )
                    )
                ).scalar_one_or_none()

        # Шаг 2: upsert пользователя
        user, is_new = await _upsert_user(session, m)

        # Шаг 3: first-touch (только при создании)
        if is_new:
            await _set_first_touch(
                session,
                user_id=user.id,
                bot_id=our_bot_id,
                product_id=product.id if product else None,
                tracking_link=tracking_link,
            )
            if tracking_link:
                await tl_service.increment_unique_users(tracking_link.id)

        # Шаг 4: current_link (для будущей заявки) — только если link валиден
        if tracking_link:
            await _set_current_link(session, user.id, tracking_link.id)

        # Шаг 4b: запуск воронки, если у tracking_link есть funnel_id
        if tracking_link and tracking_link.funnel_id:
            from app.services.funnels import FunnelsService
            funnels = FunnelsService(session)
            await funnels.start_for_user(
                user_id=user.id,
                funnel_id=tracking_link.funnel_id,
                source="tracking_link",
                source_ref=tracking_link.id,
            )

        await session.commit()

        # Шаг 5: показать карточку / каталог / уведомление об устаревшей ссылке
        if product:
            await _send_product_card(m, product)
            return
        if arg:
            await m.answer(texts.LINK_EXPIRED_OR_INVALID)
        products = (
            await session.execute(
                select(Product).where(Product.is_active.is_(True)).order_by(Product.id.desc())
            )
        ).scalars().all()
        await _send_catalog(m, products)


@router.message(CommandStart())
async def start_plain(m: Message, bot: Bot) -> None:
    async with SessionLocal() as session:
        our_bot_id = await _resolve_bot_id(session, bot)
        user, is_new = await _upsert_user(session, m)
        if is_new:
            await _set_first_touch(
                session,
                user_id=user.id,
                bot_id=our_bot_id,
                product_id=None,
                tracking_link=None,
            )
        await session.commit()

        products = (
            await session.execute(
                select(Product).where(Product.is_active.is_(True)).order_by(Product.id.desc())
            )
        ).scalars().all()
    await _send_catalog(m, products)


# ===================== /help, /my =====================

@router.message(Command("help"))
async def cmd_help(m: Message) -> None:
    await m.answer(texts.HELP)


@router.message(Command("my"))
async def cmd_my(m: Message) -> None:
    async with SessionLocal() as session:
        user = (
            await session.execute(
                select(User).where(User.telegram_user_id == m.from_user.id)
            )
        ).scalar_one_or_none()
        if not user:
            await m.answer(texts.NO_SUBSCRIPTIONS)
            return
        rows = (
            await session.execute(
                select(Subscription, Channel)
                .join(Channel, Channel.id == Subscription.channel_id)
                .where(Subscription.user_id == user.id, Subscription.status == "active")
                .order_by(Subscription.ends_at.desc())
            )
        ).all()
        if not rows:
            await m.answer(texts.NO_SUBSCRIPTIONS)
            return
        lines = [texts.my_subscriptions_line(ch.title, sub.ends_at, sub.status) for sub, ch in rows]
        await m.answer("Ваши активные подписки:\n" + "\n".join(lines))


# ===================== Callbacks =====================

@router.callback_query(F.data.startswith("prod:"))
async def cb_product(cb: CallbackQuery) -> None:
    product_id = int(cb.data.split(":", 1)[1])
    async with SessionLocal() as session:
        await _upsert_user(session, cb)
        await session.commit()
        product = (
            await session.execute(
                select(Product).where(Product.id == product_id, Product.is_active.is_(True))
            )
        ).scalar_one_or_none()
        if not product:
            await cb.answer(texts.PRODUCT_NOT_FOUND, show_alert=True)
            return
        await _send_product_card(cb, product)
        await cb.answer()


@router.callback_query(F.data.startswith("lead:"))
async def cb_lead(cb: CallbackQuery) -> None:
    product_id = int(cb.data.split(":", 1)[1])
    async with SessionLocal() as session:
        user, _ = await _upsert_user(session, cb)
        product = (
            await session.execute(
                select(Product).where(Product.id == product_id, Product.is_active.is_(True))
            )
        ).scalar_one_or_none()
        if not product:
            await cb.answer(texts.PRODUCT_NOT_FOUND, show_alert=True)
            return

        # Берём current_tracking_link если контекст свежий (TTL 30 мин)
        tracking_link: TrackingLink | None = None
        if user.current_tracking_link_id and user.current_link_set_at:
            now = datetime.now(tz=timezone.utc)
            set_at = user.current_link_set_at
            if set_at.tzinfo is None:
                set_at = set_at.replace(tzinfo=timezone.utc)
            if (now - set_at) <= CURRENT_LINK_TTL:
                tracking_link = await session.get(TrackingLink, user.current_tracking_link_id)
                # деактивированная ссылка не наследуется в lead — но click_count уже зафиксирован
                if tracking_link and not tracking_link.is_active:
                    tracking_link = None

        lead = Lead(
            user_id=user.id,
            product_id=product.id,
            status="new",
            tracking_link_id=tracking_link.id if tracking_link else None,
            utm_source=tracking_link.utm_source if tracking_link else None,
            utm_medium=tracking_link.utm_medium if tracking_link else None,
            utm_campaign=tracking_link.utm_campaign if tracking_link else None,
        )
        session.add(lead)
        await session.flush()

        # NEW: автозапуск default-воронки продукта
        if product.default_funnel_id:
            from app.services.funnels import FunnelsService
            funnels = FunnelsService(session)
            await funnels.start_for_user(
                user_id=user.id,
                funnel_id=product.default_funnel_id,
                source="lead_created",
                source_ref=lead.id,
            )

        await session.commit()

    await cb.message.answer(texts.LEAD_SENT)
    await cb.answer("Заявка отправлена")


# ===================== Кодовые слова (текстовые сообщения) =====================


def _flow_buttons_to_markup(
    buttons: list[list[dict]] | None,
) -> InlineKeyboardMarkup | None:
    """Преобразует двумерный массив кнопок (формат FunnelStep.buttons /
    FlowMessage.buttons) в aiogram InlineKeyboardMarkup. Возвращает None,
    если кнопок нет."""
    if not buttons:
        return None
    rows: list[list[InlineKeyboardButton]] = []
    for row in buttons:
        if not row:
            continue
        line: list[InlineKeyboardButton] = []
        for b in row:
            text = (b.get("text") or "").strip()
            if not text:
                continue
            url = b.get("url")
            cd = b.get("callback_data")
            if url:
                line.append(InlineKeyboardButton(text=text, url=url))
            elif cd:
                line.append(InlineKeyboardButton(text=text, callback_data=cd))
        if line:
            rows.append(line)
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


async def _send_flow_messages(target: Message, msgs: list[FlowMessage]) -> None:
    for msg in msgs:
        kb = _flow_buttons_to_markup(msg.buttons)
        await target.answer(msg.text, reply_markup=kb, parse_mode=ParseMode.HTML)


@router.message(F.text & ~F.text.startswith("/"))
async def on_text_message(m: Message, bot: Bot) -> None:
    """Резолв активной формы → кодовые слова → пропуск."""
    text = (m.text or "").strip()
    if not text:
        return

    async with SessionLocal() as session:
        user, is_new = await _upsert_user(session, m)
        if is_new:
            our_bot_id = await _resolve_bot_id(session, bot)
            await _set_first_touch(
                session, user_id=user.id, bot_id=our_bot_id,
                product_id=None, tracking_link=None,
            )

        # 1) Активная форма у юзера? Тогда трактуем текст как ответ.
        flow = StepFlowService(session)
        active_form = await flow.get_active(user.id, "form")
        if active_form is not None:
            result = await flow.submit_form_text(user_id=user.id, text=text)
            await session.commit()
            if result.messages:
                await _send_flow_messages(m, result.messages)
            return

        # 2) Триггер-слово (только короткие тексты)
        if len(text) > 64:
            await session.commit()
            return
        from app.services.funnel_triggers import FunnelTriggersService
        from app.services.funnels import FunnelsService

        triggers = FunnelTriggersService(session)
        trigger = await triggers.find_by_word(text)
        if trigger is None:
            await session.commit()
            return

        funnels = FunnelsService(session)
        existing = await funnels.find_active_entry(
            user_id=user.id, funnel_id=trigger.funnel_id,
        )
        if existing is None:
            await funnels.start_for_user(
                user_id=user.id,
                funnel_id=trigger.funnel_id,
                source="code_word",
                source_ref=trigger.id,
            )
            await triggers.increment_use_count(trigger.id)
        await session.commit()

    await m.answer(texts.CODE_WORD_ACCEPTED)


# ===================== Главное меню =====================

@router.callback_query(F.data == "menu:main")
async def cb_main_menu(cb: CallbackQuery) -> None:
    """Показать каталог продуктов (то же, что /start без параметров)."""
    async with SessionLocal() as session:
        await _upsert_user(session, cb)
        await session.commit()
        products = (
            await session.execute(
                select(Product).where(Product.is_active.is_(True)).order_by(Product.id)
            )
        ).scalars().all()
    if not products:
        await cb.message.answer(texts.NO_PRODUCTS)
    else:
        await cb.message.answer(texts.WELCOME, reply_markup=_catalog_kb(list(products)))
    await cb.answer()


# ===================== Запуск воронки из кнопки =====================

@router.callback_query(F.data.startswith("funnel:start:"))
async def cb_funnel_start(cb: CallbackQuery) -> None:
    """Запустить указанную воронку для текущего юзера.

    Идемпотентно: если юзер уже в этой воронке (status='active') — повторно
    не стартует, отвечаем подтверждением.
    """
    try:
        funnel_id = int(cb.data.split(":", 2)[2])
    except (ValueError, IndexError):
        await cb.answer("Воронка не найдена", show_alert=True)
        return

    async with SessionLocal() as session:
        user, _ = await _upsert_user(session, cb)
        from app.services.funnels import FunnelsService
        funnels = FunnelsService(session)
        existing = await funnels.find_active_entry(user_id=user.id, funnel_id=funnel_id)
        if existing is None:
            entry = await funnels.start_for_user(
                user_id=user.id,
                funnel_id=funnel_id,
                source="button_click",
                source_ref=None,
            )
            if entry is None:
                await session.rollback()
                await cb.answer("Не удалось запустить воронку", show_alert=True)
                return
        await session.commit()

    await cb.answer("Подписал вас на серию сообщений ✓")


# ===================== Quiz / Form state machines =====================


async def _resolve_active_entry_id(
    session: AsyncSession, *, user_id: int, step_id: int
) -> int | None:
    """Найти активный funnel_entry юзера для воронки, которой принадлежит step.

    Это связь от состояния квиза/формы к конкретной подписке в воронке,
    чтобы потом можно было считать конверсии в аналитике.
    """
    from app.models.funnel_entry import FunnelEntry
    from app.models.funnel_step import FunnelStep as _FS

    funnel_id_row = (
        await session.execute(select(_FS.funnel_id).where(_FS.id == step_id))
    ).scalar_one_or_none()
    if funnel_id_row is None:
        return None
    return (
        await session.execute(
            select(FunnelEntry.id).where(
                FunnelEntry.user_id == user_id,
                FunnelEntry.funnel_id == funnel_id_row,
                FunnelEntry.status == "active",
            )
        )
    ).scalar_one_or_none()


@router.callback_query(F.data.startswith("quiz:start:"))
async def cb_quiz_start(cb: CallbackQuery) -> None:
    try:
        step_id = int(cb.data.split(":", 2)[2])
    except (ValueError, IndexError):
        await cb.answer("Не нашёл квиз", show_alert=True)
        return
    async with SessionLocal() as session:
        user, _ = await _upsert_user(session, cb)
        entry_id = await _resolve_active_entry_id(session, user_id=user.id, step_id=step_id)
        flow = StepFlowService(session)
        result = await flow.start_quiz(
            user_id=user.id, step_id=step_id, funnel_entry_id=entry_id,
        )
        await session.commit()
    if result.error:
        await cb.answer("Квиз сейчас недоступен", show_alert=True)
        return
    if result.messages:
        await _send_flow_messages(cb.message, result.messages)
    await cb.answer()


@router.callback_query(F.data.startswith("qa:"))
async def cb_quiz_answer(cb: CallbackQuery) -> None:
    parts = cb.data.split(":")
    if len(parts) != 3:
        await cb.answer()
        return
    try:
        state_id = int(parts[1])
        option_idx = int(parts[2])
    except ValueError:
        await cb.answer()
        return
    async with SessionLocal() as session:
        user, _ = await _upsert_user(session, cb)
        flow = StepFlowService(session)
        result = await flow.answer_quiz(
            user_id=user.id, state_id=state_id, option_idx=option_idx,
        )
        await session.commit()
    if result.error == "state_not_found" or result.error == "not_in_progress":
        await cb.answer("Этот тест уже не активен", show_alert=True)
        return
    if result.error:
        await cb.answer("Не удалось обработать ответ", show_alert=True)
        return
    if result.messages:
        await _send_flow_messages(cb.message, result.messages)
    await cb.answer()


@router.callback_query(F.data.startswith("form:start:"))
async def cb_form_start(cb: CallbackQuery) -> None:
    try:
        step_id = int(cb.data.split(":", 2)[2])
    except (ValueError, IndexError):
        await cb.answer("Не нашёл форму", show_alert=True)
        return
    async with SessionLocal() as session:
        user, _ = await _upsert_user(session, cb)
        entry_id = await _resolve_active_entry_id(session, user_id=user.id, step_id=step_id)
        flow = StepFlowService(session)
        result = await flow.start_form(
            user_id=user.id, step_id=step_id, funnel_entry_id=entry_id,
        )
        await session.commit()
    if result.error:
        await cb.answer("Форма сейчас недоступна", show_alert=True)
        return
    if result.messages:
        await _send_flow_messages(cb.message, result.messages)
    await cb.answer()


@router.callback_query(F.data.startswith("form:cancel:"))
async def cb_form_cancel(cb: CallbackQuery) -> None:
    try:
        state_id = int(cb.data.split(":", 2)[2])
    except (ValueError, IndexError):
        await cb.answer()
        return
    async with SessionLocal() as session:
        user, _ = await _upsert_user(session, cb)
        flow = StepFlowService(session)
        result = await flow.cancel_form(user_id=user.id, state_id=state_id)
        await session.commit()
    if result.messages:
        await _send_flow_messages(cb.message, result.messages)
    await cb.answer()


# ===================== Отписка от напоминаний =====================

@router.callback_query(F.data == "unsubscribe_notifications")
async def cb_unsubscribe(cb: CallbackQuery) -> None:
    async with SessionLocal() as session:
        user = (
            await session.execute(
                select(User).where(User.telegram_user_id == cb.from_user.id)
            )
        ).scalar_one_or_none()
        if user is None:
            await cb.answer()
            return
        user.notifications_enabled = False
        await session.commit()

    await cb.message.answer(texts.UNSUBSCRIBED)
    await cb.answer()


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(router)
    return dp
