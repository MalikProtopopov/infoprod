"""Общие хелперы бота: клавиатуры, upsert юзера, атрибуция, отправка flow.

Не содержит хендлеров — только переиспользуемые функции и константы.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from aiogram.enums import ParseMode
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
from app.core.features import is_enabled
from app.db.session import SessionLocal
from app.models.bot import Bot as BotModel
from app.models.product import Product
from app.models.tracking_link import TrackingLink
from app.models.user import User
from app.services.step_flow import FlowMessage

logger = logging.getLogger(__name__)

# TTL контекста ссылки между /start и нажатием «Оставить заявку»
CURRENT_LINK_TTL = timedelta(minutes=30)
# Текст кнопки reply-keyboard (должен совпадать с тем, что видит пользователь)
MAIN_MENU_BTN = "\U0001f3e0 Главное меню"

def _main_reply_kb() -> ReplyKeyboardMarkup:
    """Постоянная reply-клавиатура с кнопкой быстрого возврата в каталог."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=MAIN_MENU_BTN)]],
        resize_keyboard=True,
        is_persistent=True,
    )


def _nav_inline_kb() -> InlineKeyboardMarkup:
    """Минимальная inline-клавиатура с одной кнопкой «Главное меню»."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")]
        ]
    )


# Кеш telegram_bot_id → internal bots.id, чтобы не дёргать БД на каждый контакт.
_BOT_ID_CACHE: dict[int, int] = {}


async def _resolve_bot_id(session: AsyncSession, aiogram_bot: Bot) -> int | None:
    """Берём internal id нашего бота по его telegram_bot_id.

    aiogram_bot.id извлекается из токена синхронно (без сетевого get_me),
    поэтому вызов дешёвый; маппинг на наш bots.id кешируем."""
    tg_id = aiogram_bot.id
    cached = _BOT_ID_CACHE.get(tg_id)
    if cached is not None:
        return cached
    row = (
        await session.execute(select(BotModel.id).where(BotModel.telegram_bot_id == tg_id))
    ).scalar_one_or_none()
    if row is not None:
        _BOT_ID_CACHE[tg_id] = row
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
    is_new = user is None
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
    else:
        user.username = tg_user.username
        user.first_name = tg_user.first_name
        user.last_name = tg_user.last_name
        user.language_code = tg_user.language_code
        user.last_seen_at = datetime.now(tz=timezone.utc)

    # Фиксируем контакт с КОНКРЕТНЫМ ботом (мультибот). m.bot — текущий бот.
    aiogram_bot = getattr(m, "bot", None)
    if aiogram_bot is not None:
        bot_id = await _resolve_bot_id(session, aiogram_bot)
        if bot_id is not None:
            from app.services import user_bots
            await user_bots.touch(session, user_id=user.id, bot_id=bot_id)
    return user, is_new


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
    rows: list[list[InlineKeyboardButton]] = []
    # Кнопку «Оставить заявку» показываем только если фича leads включена,
    # иначе карточка вела бы в недоступный колбэк lead:.
    if is_enabled("leads"):
        rows.append(
            [InlineKeyboardButton(text="📝 Оставить заявку", callback_data=f"lead:{product_id}")]
        )
    rows.append([InlineKeyboardButton(text="‹ К каталогу", callback_data="menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _catalog_kb(products: list[Product]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for p in products:
        rows.append([InlineKeyboardButton(text=p.name, callback_data=f"prod:{p.id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _main_menu_kb() -> InlineKeyboardMarkup:
    """Главное меню (разделы). Сейчас — «Продукты»; расширяемо новыми секциями."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📦 Смотреть продукты", callback_data="menu:main")],
        ]
    )


async def _send_main_menu(target: Message, *, setup_nav: bool = True) -> None:
    """Приветствие + разделы при /start (welcome → меню → каталог)."""
    if setup_nav:
        await target.answer(texts.WELCOME, reply_markup=_main_reply_kb())
    await target.answer(texts.MENU_HEADER, reply_markup=_main_menu_kb())


async def _send_product_card(target: Message | CallbackQuery, product: Product) -> None:
    # Если задан стилизованный card_text — используем его (с цитатами/спойлерами),
    # иначе — сгенерированную карточку с ценами.
    text = getattr(product, "card_text", None) or texts.product_card(
        product.name,
        product.description,
        product.price_3m,
        product.price_6m,
        product.price_12m,
        product.currency,
    )
    msg = target if isinstance(target, Message) else target.message
    await msg.answer(text, reply_markup=_product_kb(product.id), parse_mode=ParseMode.HTML)


async def present_product(bot: Bot, target: Message | CallbackQuery, product: Product) -> None:
    """Презентация продукта: сначала контент-блоки (кружок/видео/галерея/голос),
    затем карточка с ценами и CTA «Оставить заявку». Эффект «живого» менеджера."""
    from app.bot.presentation import send_presentation

    # В личке chat_id == from_user.id; так не зависим от структуры message.
    chat_id = target.from_user.id
    try:
        await send_presentation(bot, chat_id, product)
    except Exception:  # noqa: BLE001 — презентация best-effort, карточку покажем всё равно
        logger.warning("present_product.presentation_failed product_id=%s", product.id)
    await _send_product_card(target, product)


async def _send_catalog(target: Message, products: list[Product], *, setup_nav: bool = False) -> None:
    """Показать каталог продуктов.

    setup_nav=True — отправить два сообщения: сначала WELCOME с reply-клавиатурой
    (устанавливает постоянную кнопку «🏠 Главное меню»), затем сам каталог.
    Используется при /start и аналогичных точках входа, где пользователь видит
    бот впервые или сбросил контекст.
    При setup_nav=False — одно сообщение с inline-каталогом (для навигации изнутри бота).
    """
    if not products:
        await target.answer(texts.NO_PRODUCTS)
        return
    if setup_nav:
        # Устанавливаем reply-клавиатуру на приветственном сообщении,
        # а каталог шлём отдельным — иначе нельзя совместить оба reply_markup.
        await target.answer(texts.WELCOME, reply_markup=_main_reply_kb())
        await target.answer(texts.CATALOG_HEADER, reply_markup=_catalog_kb(products))
    else:
        await target.answer(texts.CATALOG_HEADER, reply_markup=_catalog_kb(products))


def _flow_buttons_to_markup(
    buttons: list[list[dict]] | None,
    *,
    append_main_menu: bool = False,
) -> InlineKeyboardMarkup | None:
    """Преобразует двумерный массив кнопок (формат FunnelStep.buttons /
    FlowMessage.buttons) в aiogram InlineKeyboardMarkup.

    append_main_menu=True — добавляет кнопку «🏠 Главное меню» последней строкой,
    если её ещё нет среди существующих кнопок. Возвращает None, если кнопок нет."""
    rows: list[list[InlineKeyboardButton]] = []
    has_main_menu = False
    if buttons:
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
                if cd == "menu:main":
                    has_main_menu = True
                if url:
                    line.append(InlineKeyboardButton(text=text, url=url))
                elif cd:
                    line.append(InlineKeyboardButton(text=text, callback_data=cd))
            if line:
                rows.append(line)
    if append_main_menu and not has_main_menu:
        rows.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


async def _send_flow_messages(
    target: Message,
    msgs: list[FlowMessage],
    *,
    append_main_menu: bool = True,
) -> None:
    """Отправить список FlowMessage пользователю.

    append_main_menu=True (по умолчанию) — к каждому сообщению добавляется
    кнопка «🏠 Главное меню» если её ещё нет. Это даёт пользователю
    способ выйти из любой воронки / квиза / формы без знания команд.
    """
    for msg in msgs:
        kb = _flow_buttons_to_markup(msg.buttons, append_main_menu=append_main_menu)
        await target.answer(msg.text, reply_markup=kb, parse_mode=ParseMode.HTML)


async def _flush_funnel_entry_now(entry_id: int) -> int:
    """Немедленно отправить все scheduled_messages этого entry, у которых
    scheduled_at <= сейчас (типично — шаг D0 с delay=0).

    Открываем отдельную сессию: пред-отправочная транзакция уже должна
    быть закоммичена в вызывающем коде. Возвращаем кол-во отправленных
    шагов — чтобы вызывающий мог решить, стоит ли слать сопутствующее
    подтверждение типа CODE_WORD_ACCEPTED.

    Ошибки сессии не пропускаем наверх — это best-effort, плохой случай
    подберёт обычный scheduler-тик.
    """
    from app.workers.scheduled_messages import process_due_messages

    try:
        async with SessionLocal() as session:
            stats = await process_due_messages(session, entry_id=entry_id)
            return int(stats.get("sent") or 0)
    except Exception:
        logger.exception("flush_funnel_entry_now.failed entry_id=%s", entry_id)
        return 0


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

