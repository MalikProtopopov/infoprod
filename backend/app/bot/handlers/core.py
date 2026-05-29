"""Ядровые хендлеры: /start, /help, /my, каталог, навигация, текст."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts
from app.bot.handlers.common import (
    CURRENT_LINK_TTL,
    MAIN_MENU_BTN,
    _catalog_kb,
    _flow_buttons_to_markup,
    _flush_funnel_entry_now,
    _main_reply_kb,
    _nav_inline_kb,
    _resolve_active_entry_id,
    _resolve_bot_id,
    _send_flow_messages,
    _send_main_menu,
    _set_current_link,
    _set_first_touch,
    _upsert_user,
    present_product,
)
from app.core.features import is_enabled
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
router = Router(name="public_core")

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
            # Резолв slug → трекинг-ссылка только если фича включена; иначе arg
            # ещё может оказаться product.code (fallback ниже).
            if is_enabled("tracking_links"):
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
        new_entry_id: int | None = None
        if tracking_link and tracking_link.funnel_id and is_enabled("funnels"):
            from app.services.funnels import FunnelsService
            funnels = FunnelsService(session)
            entry = await funnels.start_for_user(
                user_id=user.id,
                funnel_id=tracking_link.funnel_id,
                source="tracking_link",
                source_ref=tracking_link.id,
            )
            new_entry_id = entry.id if entry is not None else None

        await session.commit()

        # Sync-flush D0 (если воронка только что стартовала). Шлём ДО показа
        # каталога/карточки — D0 это первое касание, юзер должен видеть его
        # первым.
        if new_entry_id is not None:
            await _flush_funnel_entry_now(new_entry_id)

        # Шаг 5: презентация продукта (deep-link) / меню / уведомление об устаревшей ссылке
        if product:
            await present_product(bot, m, product)
            return
        if arg:
            await m.answer(texts.LINK_EXPIRED_OR_INVALID)
        await _send_main_menu(m, setup_nav=True)


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
    await _send_main_menu(m, setup_nav=True)


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
            await m.answer(texts.NO_SUBSCRIPTIONS, reply_markup=_nav_inline_kb())
            return
        lines = [texts.my_subscriptions_line(ch.title, sub.ends_at, sub.status) for sub, ch in rows]
        await m.answer(
            "Ваши активные подписки:\n" + "\n".join(lines),
            reply_markup=_nav_inline_kb(),
        )


@router.callback_query(F.data.startswith("prod:"))
async def cb_product(cb: CallbackQuery, bot: Bot) -> None:
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
    await cb.answer()  # закрываем «часики» до (возможно долгой) презентации
    await present_product(bot, cb, product)


@router.message(F.text & ~F.text.startswith("/"))
async def on_text_message(m: Message, bot: Bot) -> None:
    """Резолв активной формы → кодовые слова → пропуск.

    Приоритет 0: reply-кнопка «🏠 Главное меню» — отменяет активную форму
    и возвращает каталог из любого контекста.
    """
    text = (m.text or "").strip()
    if not text:
        return

    # ── 0) Постоянная кнопка навигации ──────────────────────────────────────
    if text == MAIN_MENU_BTN:
        async with SessionLocal() as session:
            user, is_new = await _upsert_user(session, m)
            if is_new:
                our_bot_id = await _resolve_bot_id(session, bot)
                await _set_first_touch(
                    session, user_id=user.id, bot_id=our_bot_id,
                    product_id=None, tracking_link=None,
                )
            flow = StepFlowService(session)
            # Отменяем любую активную форму — пользователь явно хочет выйти
            active_form = await flow.get_active(user.id, "form")
            if active_form is not None:
                await flow.cancel_form(user_id=user.id, state_id=active_form.id)
                await m.answer(texts.FORM_CANCELLED_NAV)
            await session.commit()
            products = (
                await session.execute(
                    select(Product).where(Product.is_active.is_(True)).order_by(Product.id.desc())
                )
            ).scalars().all()
        await m.answer(texts.CATALOG_HEADER, reply_markup=_catalog_kb(list(products)))
        return

    async with SessionLocal() as session:
        user, is_new = await _upsert_user(session, m)
        our_bot_id = await _resolve_bot_id(session, bot)
        if is_new:
            await _set_first_touch(
                session, user_id=user.id, bot_id=our_bot_id,
                product_id=None, tracking_link=None,
            )
        # Лог входящего сообщения (чат в админке)
        if our_bot_id is not None:
            from app.services import messages as messages_svc
            await messages_svc.log(
                session, user_id=user.id, bot_id=our_bot_id,
                direction="in", text=text,
            )

        # 1) Активная форма у юзера? Тогда трактуем текст как ответ.
        flow = StepFlowService(session)
        if is_enabled("forms"):
            active_form = await flow.get_active(user.id, "form")
            if active_form is not None:
                result = await flow.submit_form_text(user_id=user.id, text=text)
                await session.commit()
                if result.messages:
                    await _send_flow_messages(m, result.messages)
                return

        # 2) Триггер-слово (только короткие тексты)
        if not is_enabled("funnel_triggers"):
            await session.commit()
            return
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
        new_entry_id: int | None = None
        if existing is None:
            new_entry = await funnels.start_for_user(
                user_id=user.id,
                funnel_id=trigger.funnel_id,
                source="code_word",
                source_ref=trigger.id,
            )
            new_entry_id = new_entry.id if new_entry is not None else None
            await triggers.increment_use_count(trigger.id)
        await session.commit()

    # Sync-доставка шагов с delay=0 (типично — D0). Если что-то отправилось,
    # `CODE_WORD_ACCEPTED` спойлерит начало воронки и больше не нужен.
    sent = 0
    if new_entry_id is not None:
        sent = await _flush_funnel_entry_now(new_entry_id)
    if sent == 0:
        await m.answer(texts.CODE_WORD_ACCEPTED)


@router.callback_query(F.data == "menu:main")
async def cb_main_menu(cb: CallbackQuery) -> None:
    """Показать каталог продуктов (то же, что /start без параметров).

    Reply-клавиатура уже должна быть у пользователя после первого /start;
    здесь достаточно показать только inline-каталог.
    """
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
        await cb.message.answer(texts.CATALOG_HEADER, reply_markup=_catalog_kb(list(products)))
    await cb.answer()


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

    await cb.message.answer(texts.UNSUBSCRIBED, reply_markup=_nav_inline_kb())
    await cb.answer()

