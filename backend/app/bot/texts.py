from __future__ import annotations

from datetime import datetime


WELCOME = (
    "Привет! 👋\n\n"
    "Через этот бот можно оформить доступ в закрытые каналы.\n"
    "Кнопка «🏠 Главное меню» внизу вернёт вас в каталог из любого места."
)

CATALOG_HEADER = "Выберите продукт из списка 👇"

NO_PRODUCTS = "Сейчас нет доступных продуктов. Загляните позже."

HELP = (
    "Команды:\n"
    "/start — начать и посмотреть каталог\n"
    "/my — мои подписки и сроки\n"
    "/help — эта справка\n\n"
    "Кнопка «🏠 Главное меню» внизу экрана вернёт вас в каталог из любого места."
)

NO_SUBSCRIPTIONS = "У вас пока нет активных подписок."

LEAD_SENT = (
    "✅ Спасибо за заявку!\n\n"
    "Администратор свяжется с вами в ближайшее время и пришлёт условия оплаты."
)

PRODUCT_NOT_FOUND = "Этот продукт сейчас недоступен."

LINK_EXPIRED_OR_INVALID = "Эта ссылка устарела или недоступна. Посмотрите наш каталог ниже."

CODE_WORD_ACCEPTED = "Принято, сейчас пришлю материалы."

UNSUBSCRIBED = (
    "🔕 Хорошо, больше не буду присылать напоминания.\n\n"
    "Если что — напишите /start или нажмите «🏠 Главное меню»."
)

FORM_CANCELLED_NAV = "Заполнение формы отменено."


def product_card(name: str, description: str | None, price_3m, price_6m, price_12m, currency: str) -> str:
    desc = (description or "").strip()
    parts = [f"<b>{_html_escape(name)}</b>"]
    if desc:
        parts.append(_html_escape(desc))

    # Скрываем периоды с ценой 0 — их считаем «не для продажи».
    price_lines: list[str] = []
    for months, price in ((3, price_3m), (6, price_6m), (12, price_12m)):
        if _price_is_positive(price):
            price_lines.append(f"{months} мес. — <b>{_fmt_price(price)} {currency}</b>")

    if price_lines:
        parts.append("")
        parts.extend(price_lines)
        parts.append("")
        parts.append("Нажмите «Оставить заявку», и администратор свяжется с вами.")
    else:
        # Все три периода нулевые — цены уточняет администратор.
        parts.append("")
        parts.append("Цена уточняется. Нажмите «Оставить заявку», и администратор свяжется с вами.")

    return "\n".join(parts)


def _price_is_positive(value) -> bool:
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def access_granted(channel_title: str, ends_at: datetime, invite_link: str) -> str:
    return (
        f"✅ Оплата принята.\n\n"
        f"Доступ к каналу «{channel_title}» открыт до {ends_at.strftime('%d.%m.%Y %H:%M')} UTC.\n"
        f"Ссылка‑приглашение (одноразовая):\n{invite_link}"
    )


def access_expired(channel_title: str) -> str:
    return (
        f"⏳ Срок доступа к каналу «{channel_title}» истёк.\n\n"
        f"Чтобы продлить доступ, нажмите /start и оставьте новую заявку — "
        f"администратор пришлёт реквизиты для оплаты."
    )


def my_subscriptions_line(channel_title: str, ends_at: datetime, status: str) -> str:
    status_label = {"active": "активна", "expired": "истекла", "revoked": "отозвана"}.get(status, status)
    return f"• «{channel_title}» — {status_label}, до {ends_at.strftime('%d.%m.%Y')}"


def _fmt_price(value) -> str:
    try:
        v = float(value)
    except Exception:
        return str(value)
    if v.is_integer():
        return f"{int(v):,}".replace(",", " ")
    return f"{v:,.2f}".replace(",", " ")


def _html_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
