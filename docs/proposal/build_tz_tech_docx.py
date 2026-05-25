"""
Технический ТЗ для Core: БД + API + Дизайн в одном документе.

Запуск:
  python3 docs/proposal/build_tz_tech_docx.py

Выход:
  docs/proposal/Grammy_TZ_Tech.docx
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

OUT_DOCX = Path(__file__).resolve().parent / "Grammy_TZ_Tech.docx"

INDIGO = RGBColor(0x4F, 0x46, 0xE5)
INK = RGBColor(0x1E, 0x1B, 0x4B)
MUTED = RGBColor(0x6B, 0x72, 0x80)
GREEN = RGBColor(0x05, 0x96, 0x69)
ROSE = RGBColor(0xE1, 0x1D, 0x48)


# ─────────────────────────────────────────────────────────────────────────────
# Данные: БД
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Field:
    name: str
    type: str
    nullable: bool = False
    note: str = ""


@dataclass
class Table:
    name: str
    desc: str
    fields: List[Field]
    indexes: List[str] = field(default_factory=list)
    fks: List[str] = field(default_factory=list)


TABLES = [
    Table(
        name="admins",
        desc="Пользователи админ-панели (admin / manager). Один из них создаётся автоматически при первой миграции.",
        fields=[
            Field("id", "BIGINT PK", note="автоинкремент"),
            Field("username", "TEXT UNIQUE", note="логин"),
            Field("password_hash", "TEXT", note="bcrypt-хэш"),
            Field("role", "VARCHAR(16)", note="admin | manager"),
            Field("created_at", "TIMESTAMPTZ", note="DEFAULT now()"),
        ],
        indexes=["UNIQUE (username)"],
    ),
    Table(
        name="bots",
        desc="Telegram-боты, подключённые к системе. У каждого свой токен и polling-задача.",
        fields=[
            Field("id", "BIGINT PK"),
            Field("token", "TEXT", note="bot token из @BotFather"),
            Field("telegram_bot_id", "BIGINT", note="ID бота в Telegram"),
            Field("username", "TEXT", note="@username бота"),
            Field("title", "TEXT", note="отображаемое имя"),
            Field("is_active", "BOOLEAN", note="DEFAULT true"),
            Field("created_at", "TIMESTAMPTZ", note="DEFAULT now()"),
        ],
        indexes=["UNIQUE (telegram_bot_id)"],
    ),
    Table(
        name="channels",
        desc="Закрытые Telegram-каналы, в которые выдаётся доступ по подписке.",
        fields=[
            Field("id", "BIGINT PK"),
            Field("telegram_chat_id", "BIGINT", note="ID канала в Telegram (отрицательное)"),
            Field("title", "TEXT", note="название канала"),
            Field("username", "TEXT", True, "опц. @username"),
            Field("bot_id", "BIGINT FK→bots.id", note="бот-админ канала"),
            Field("created_at", "TIMESTAMPTZ"),
        ],
        indexes=["UNIQUE (telegram_chat_id)", "INDEX (bot_id)"],
        fks=["bot_id → bots.id ON DELETE RESTRICT"],
    ),
    Table(
        name="products",
        desc="Продаваемые продукты. У каждого — цены на 3, 6 и 12 месяцев, привязка к каналу.",
        fields=[
            Field("id", "BIGINT PK"),
            Field("code", "VARCHAR(64) UNIQUE", note="для deep-link /start={code}"),
            Field("name", "TEXT"),
            Field("description", "TEXT", True),
            Field("cover_url", "TEXT", True, "опц. ссылка на обложку"),
            Field("price_3m", "NUMERIC(10,2)", note="цена за 3 мес"),
            Field("price_6m", "NUMERIC(10,2)", note="цена за 6 мес"),
            Field("price_12m", "NUMERIC(10,2)", note="цена за 12 мес"),
            Field("currency", "VARCHAR(3)", note="RUB / USD / EUR"),
            Field("channel_id", "BIGINT FK→channels.id"),
            Field("is_active", "BOOLEAN", note="DEFAULT true"),
            Field("created_at", "TIMESTAMPTZ"),
        ],
        indexes=["UNIQUE (code)", "INDEX (channel_id)", "INDEX (is_active)"],
        fks=["channel_id → channels.id ON DELETE RESTRICT"],
    ),
    Table(
        name="users",
        desc="Telegram-пользователи (клиенты). Создаются при первом /start, дополняются менеджером.",
        fields=[
            Field("id", "BIGINT PK"),
            Field("telegram_user_id", "BIGINT UNIQUE", note="из Telegram"),
            Field("username", "TEXT", True, "@username из Telegram"),
            Field("first_name", "TEXT", True),
            Field("last_name", "TEXT", True),
            Field("email", "TEXT", True, "дополняется менеджером"),
            Field("phone", "TEXT", True, "дополняется менеджером"),
            Field("notes", "TEXT", True, "заметки менеджера"),
            Field("notifications_enabled", "BOOLEAN", note="DEFAULT true, юзер может отключить"),
            Field("first_seen_at", "TIMESTAMPTZ", note="DEFAULT now()"),
            Field("last_seen_at", "TIMESTAMPTZ", True),
        ],
        indexes=["UNIQUE (telegram_user_id)", "INDEX (username)", "INDEX gin trigram (first_name, last_name)"],
    ),
    Table(
        name="leads",
        desc="Заявки клиентов на продукт. Создаются из бота кнопкой «Оставить заявку».",
        fields=[
            Field("id", "BIGINT PK"),
            Field("user_id", "BIGINT FK→users.id"),
            Field("product_id", "BIGINT FK→products.id"),
            Field("status", "VARCHAR(16)", note="new | contacted | paid | closed"),
            Field("created_at", "TIMESTAMPTZ"),
            Field("contacted_at", "TIMESTAMPTZ", True),
            Field("paid_at", "TIMESTAMPTZ", True),
            Field("closed_at", "TIMESTAMPTZ", True),
        ],
        indexes=["INDEX (status, created_at DESC)", "INDEX (user_id, product_id)"],
        fks=["user_id → users.id ON DELETE CASCADE",
             "product_id → products.id ON DELETE CASCADE"],
    ),
    Table(
        name="payments",
        desc="Платежи клиентов. Создаются менеджером вручную. Каждый платёж порождает/продлевает подписку.",
        fields=[
            Field("id", "BIGINT PK"),
            Field("user_id", "BIGINT FK→users.id"),
            Field("product_id", "BIGINT FK→products.id"),
            Field("admin_id", "BIGINT FK→admins.id", True, "кто провёл"),
            Field("period_months", "SMALLINT", note="3 | 6 | 12"),
            Field("amount", "NUMERIC(10,2)"),
            Field("currency", "VARCHAR(3)"),
            Field("note", "TEXT", True),
            Field("created_at", "TIMESTAMPTZ"),
        ],
        indexes=["INDEX (user_id, product_id)", "INDEX (created_at DESC)"],
        fks=["user_id → users.id ON DELETE RESTRICT",
             "product_id → products.id ON DELETE RESTRICT",
             "admin_id → admins.id ON DELETE SET NULL"],
    ),
    Table(
        name="subscriptions",
        desc="Активные подписки клиентов на каналы. Создаются по платежу, истекают по ends_at, отзываются вручную или worker'ом.",
        fields=[
            Field("id", "BIGINT PK"),
            Field("user_id", "BIGINT FK→users.id"),
            Field("channel_id", "BIGINT FK→channels.id"),
            Field("product_id", "BIGINT FK→products.id"),
            Field("payment_id", "BIGINT FK→payments.id", True, "последний платёж"),
            Field("starts_at", "TIMESTAMPTZ"),
            Field("ends_at", "TIMESTAMPTZ"),
            Field("status", "VARCHAR(16)", note="active | expired | revoked"),
            Field("invite_link", "TEXT", True, "одноразовая ссылка-приглашение"),
            Field("created_at", "TIMESTAMPTZ"),
            Field("revoked_at", "TIMESTAMPTZ", True),
        ],
        indexes=["INDEX (status, ends_at)", "INDEX (user_id, channel_id, status)"],
        fks=["user_id → users.id ON DELETE RESTRICT",
             "channel_id → channels.id ON DELETE RESTRICT",
             "product_id → products.id ON DELETE RESTRICT",
             "payment_id → payments.id ON DELETE SET NULL"],
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# Данные: API
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Endpoint:
    method: str
    path: str
    desc: str
    access: str           # "Публ." / "Admin" / "Admin+Mgr"
    request: str = ""     # описание тела/параметров
    response: str = ""    # успешный ответ
    errors: str = ""      # частые ошибки


@dataclass
class ApiGroup:
    title: str
    prefix: str
    desc: str
    endpoints: List[Endpoint]


API_GROUPS: List[ApiGroup] = [
    ApiGroup(
        title="Аутентификация и роли",
        prefix="/api/auth, /api/admin",
        desc="Вход в админ-панель. JWT в HttpOnly cookie, TTL 7 дней. Защита от подбора пароля: 10 попыток за 60 сек по IP.",
        endpoints=[
            Endpoint("POST", "/api/auth/login",
                     "Войти по логину и паролю",
                     "Публ. (rate-limited)",
                     "{ username: str, password: str }",
                     "200: устанавливает HttpOnly Secure cookie access_token. Тело { id, username, role }",
                     "401 — неверные креды; 429 — превышен лимит попыток"),
            Endpoint("POST", "/api/auth/logout",
                     "Выйти, удалить cookie",
                     "Admin+Mgr",
                     "—", "204 No Content",
                     "—"),
            Endpoint("GET", "/api/auth/me",
                     "Получить текущего администратора",
                     "Admin+Mgr",
                     "—", "200: { id, username, role }",
                     "401 — нет/истёк токен"),
            Endpoint("POST", "/api/admin/password",
                     "Сменить пароль",
                     "Admin+Mgr",
                     "{ old_password: str, new_password: str }",
                     "204",
                     "400 — старый пароль неверный; 422 — новый слабее политики"),
        ],
    ),
    ApiGroup(
        title="Боты, каналы, продукты (каталог)",
        prefix="/api/bots, /api/channels, /api/products",
        desc="CRUD сущностей каталога. Удаление — только Admin.",
        endpoints=[
            Endpoint("GET", "/api/bots", "Список ботов с числом каналов и продуктов", "Admin+Mgr",
                     "—", "200: [{ id, username, channels_count, products_count, is_active }]", "—"),
            Endpoint("POST", "/api/bots", "Подключить нового бота по токену", "Admin",
                     "{ token: str }",
                     "201: { id, username, telegram_bot_id, ... }",
                     "400 — невалидный токен (getMe не прошёл); 409 — бот уже подключён"),
            Endpoint("PATCH", "/api/bots/{id}", "Обновить (is_active, title)", "Admin",
                     "{ is_active?: bool, title?: str }",
                     "200: обновлённый объект", "404"),
            Endpoint("DELETE", "/api/bots/{id}", "Удалить бота", "Admin",
                     "—", "204",
                     "409 — есть связанные каналы/продукты (RESTRICT)"),
            Endpoint("GET", "/api/channels", "Список каналов", "Admin+Mgr",
                     "—", "200: [{ id, title, bot_username, products_count, active_subs_count }]", "—"),
            Endpoint("POST", "/api/channels", "Подключить канал", "Admin",
                     "{ bot_id, telegram_chat_id, title? }",
                     "201", "400 — бот не админ канала или нет прав invite"),
            Endpoint("DELETE", "/api/channels/{id}", "Удалить канал", "Admin",
                     "—", "204", "409 — есть продукты/подписки"),
            Endpoint("GET", "/api/products", "Список продуктов", "Admin+Mgr",
                     "filter: ?is_active, ?channel_id",
                     "200: [{ id, code, name, prices, channel_title, active_subs_count }]", "—"),
            Endpoint("POST", "/api/products", "Создать продукт", "Admin",
                     "{ code, name, channel_id, currency, price_3m, price_6m, price_12m }",
                     "201",
                     "409 — code занят"),
            Endpoint("PATCH", "/api/products/{id}", "Обновить", "Admin+Mgr",
                     "любые поля кроме code", "200", "404"),
            Endpoint("DELETE", "/api/products/{id}", "Удалить", "Admin",
                     "—", "204", "409 — есть подписки/платежи"),
        ],
    ),
    ApiGroup(
        title="Пользователи (клиенты)",
        prefix="/api/users",
        desc="Поиск и редактирование контактов клиентов.",
        endpoints=[
            Endpoint("GET", "/api/users", "Поиск пользователей", "Admin+Mgr",
                     "?q=поиск&limit=50&offset=0",
                     "200: { items: [...], total: int }",
                     "—"),
            Endpoint("GET", "/api/users/{id}", "Профиль клиента с историей", "Admin+Mgr",
                     "—",
                     "200: { user, leads[], payments[], subscriptions[] }",
                     "404"),
            Endpoint("PATCH", "/api/users/{id}", "Обновить контакты/заметку", "Admin+Mgr",
                     "{ email?, phone?, notes? }",
                     "200", "404"),
        ],
    ),
    ApiGroup(
        title="Заявки (leads)",
        prefix="/api/leads",
        desc="Заявки от клиентов из бота. Менеджер ведёт по статусам.",
        endpoints=[
            Endpoint("GET", "/api/leads", "Список заявок с фильтром", "Admin+Mgr",
                     "?status=new&limit=100&offset=0",
                     "200: [{ id, user, product, status, created_at, ...timestamps }]",
                     "—"),
            Endpoint("GET", "/api/leads/{id}", "Детали заявки", "Admin+Mgr",
                     "—", "200: { lead, user (full), product (full) }", "404"),
            Endpoint("PATCH", "/api/leads/{id}", "Изменить статус", "Admin+Mgr",
                     "{ status: new|contacted|paid|closed }",
                     "200 (timestamp проставляется автоматически)",
                     "422 — нельзя откатить closed→new"),
            Endpoint("DELETE", "/api/leads/{id}", "Удалить заявку", "Admin",
                     "—", "204", "—"),
        ],
    ),
    ApiGroup(
        title="Платежи",
        prefix="/api/payments",
        desc="Платежи создаются вручную менеджером. Каждый платёж порождает/продлевает подписку, выдаёт invite-ссылку.",
        endpoints=[
            Endpoint("GET", "/api/payments", "Список платежей", "Admin+Mgr",
                     "?from=&to=&product_id=",
                     "200: [{ id, user, product, period_months, amount, created_at }]",
                     "—"),
            Endpoint("POST", "/api/payments", "Создать платёж", "Admin+Mgr",
                     "{ user_id, product_id, period_months, amount, currency, note? }",
                     "201: { id, ... }. Сайд-эффекты: создана/продлена subscription, "
                     "сгенерирован invite-link, бот отправил юзеру сообщение с доступом, "
                     "последний open lead помечен paid.",
                     "404 — user/product не найден; 400 — невалидный период"),
            Endpoint("GET", "/api/payments/{id}", "Детали платежа", "Admin+Mgr",
                     "—", "200", "404"),
        ],
    ),
    ApiGroup(
        title="Подписки",
        prefix="/api/subscriptions",
        desc="Список действующих подписок и действия над ними.",
        endpoints=[
            Endpoint("GET", "/api/subscriptions", "Список подписок", "Admin+Mgr",
                     "?status=active|expired|revoked&channel_id=",
                     "200: [{ id, user, channel, product, starts_at, ends_at, status }]",
                     "—"),
            Endpoint("POST", "/api/subscriptions/{id}/extend",
                     "Продлить подписку (создаёт новый Payment)",
                     "Admin+Mgr",
                     "{ period_months: 3|6|12, amount, note? }",
                     "200: обновлённая подписка с новым ends_at",
                     "404"),
            Endpoint("POST", "/api/subscriptions/{id}/revoke",
                     "Досрочно отозвать (кикнуть из канала)",
                     "Admin+Mgr",
                     "{ reason: str }",
                     "200. Сайд-эффект: bot.kickChatMember + уведомление юзеру",
                     "409 — уже expired/revoked"),
        ],
    ),
    ApiGroup(
        title="Системное",
        prefix="/api/healthz, /metrics",
        desc="Служебные endpoints для эксплуатации и мониторинга.",
        endpoints=[
            Endpoint("GET", "/api/healthz", "Liveness probe", "Публ.",
                     "—", "200: { ok: true }", "—"),
        ],
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# Данные: Дизайн
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Screen:
    route: str
    title: str
    purpose: str
    layout: str           # описание раскладки
    components: List[str] # ключевые компоненты на экране
    states: List[str]     # loading / empty / error / etc
    actions: List[str]    # что пользователь может сделать
    mobile: str = ""      # как ведёт себя на смартфоне


SCREENS: List[Screen] = [
    Screen(
        route="/login",
        title="Вход в систему",
        purpose="Закрытая авторизация. Без регистрации, аккаунты создаются администратором.",
        layout="Полный экран. Центрированная карточка glass-strong на gradient-фоне с decorative blobs. "
               "Логотип-винил + название «Grammy» сверху, форма входа в карточке.",
        components=[
            "Лого-винил 44×44px + текст «Grammy» (28pt) + подпись «admin panel» (uppercase)",
            "Поле «Логин» (Input, autofocus, autocomplete='username')",
            "Поле «Пароль» (Input type=password, autocomplete='current-password')",
            "Кнопка «Войти» (Button primary, ширина 100%)",
            "Блок ошибки (rose-50 фон, rose-600 текст, появляется по факту ошибки)",
            "Подпись «Безопасное соединение · TLS Let's Encrypt» (мелким серым)",
        ],
        states=[
            "default — пустые поля, кнопка активна",
            "loading — кнопка disabled, текст «Входим…»",
            "error — алый блок над кнопкой с человеческим сообщением",
            "rate-limited — «Слишком много попыток, попробуйте через минуту»",
        ],
        actions=[
            "Submit формы → POST /api/auth/login → редирект на /",
            "Enter в любом поле = submit",
        ],
        mobile="Карточка занимает 92% ширины, кнопки 44px высоты для удобного нажатия пальцем.",
    ),
    Screen(
        route="/",
        title="Dashboard (главный экран)",
        purpose="Сводка для быстрого «холодного» входа в работу: что новое, сколько денег, кто оплатил.",
        layout="Sidebar 260px (слева) + main area. Header sticky с breadcrumbs. "
               "Контент: 4 KPI карточки + 2 секции последних заявок и платежей в две колонки.",
        components=[
            "Sidebar v2 (7 групп, collapsible, badges по новым заявкам)",
            "Header sticky с breadcrumbs и amber-badge новых заявок",
            "4 KPI карточки glass: пользователи, заявки, подписки, выручка за 30 дней",
            "Карточка «Последние заявки» — таблица 5 строк со статусом и временем",
            "Карточка «Последние платежи» — таблица 5 строк с суммой и периодом",
        ],
        states=[
            "loading — skeleton-серые блоки",
            "empty (первый запуск) — карточки с прочерками, текст «Данных пока нет»",
        ],
        actions=[
            "Клик по KPI → переход в соответствующий раздел",
            "Клик по заявке/платежу → переход в детали",
            "Auto-refresh KPI каждые 60 сек (SWR polling)",
        ],
        mobile="Sidebar → бургер-меню. KPI сетка 2×2 вместо 4×1. Таблицы → стек карточек.",
    ),
    Screen(
        route="/leads",
        title="Заявки",
        purpose="Главный рабочий экран менеджера. Очередь заявок с фильтром по статусу.",
        layout="Sidebar + main. Сверху — табы статусов (Все / Новые / Связались / Оплачено / Закрытые) "
               "с подсчётом в каждой. Под ними — таблица.",
        components=[
            "Табы фильтра по статусу с числами",
            "Таблица колонки: Клиент (аватар+имя+@username), Продукт, Статус (Pill), Когда (text-right)",
            "Hover-эффект на строке, клик → /leads/{id}",
            "CSV-export кнопка в правом верхнем углу",
            "Empty state — иллюстрация и текст «Пока нет заявок в этой категории»",
        ],
        states=[
            "loading — skeleton-таблица",
            "empty — Empty компонент",
            "filtered — таб подсветка + сохранение фильтра в URL",
        ],
        actions=[
            "Клик по табу → фильтр статуса",
            "Клик по строке → /leads/{id}",
            "«Скачать CSV» → стрим файла",
        ],
        mobile="Таблица min-width 820px с горизонтальным скроллом. Табы выровнены в строке со скроллом.",
    ),
    Screen(
        route="/leads/[id]",
        title="Детальная заявка",
        purpose="Карточка одной заявки с контактами клиента, историей и действиями.",
        layout="Двухколоночная: слева — детали заявки и продукт, справа — карточка клиента с быстрыми "
               "контактами и историей.",
        components=[
            "PageHeader: «Заявка #N от {date}»",
            "Карточка статуса с цветной Pill и таймстампами (new, contacted, paid, closed) в виде степпера",
            "Карточка продукта: название, тарифы, привязка к каналу",
            "Карточка клиента: аватар, имя, @username, кнопка «Открыть профиль»",
            "Блок «Быстрые действия»: Связались, Оплатил (открывает форму платежа), Закрыть",
            "Внизу — текстовое поле «Заметка по заявке» (auto-save)",
        ],
        states=[
            "loading", "404 — заявка не найдена",
            "action-pending — кнопки disabled на время запроса",
            "saved — Toast «Статус обновлён»",
        ],
        actions=[
            "Смена статуса → PATCH /api/leads/{id}",
            "«Оплатил» → открывает Sheet с формой POST /api/payments c предзаполнением",
            "Заметка → auto-save с debounce 1s",
        ],
        mobile="Колонки в стек, контакты клиента сверху для быстрого доступа к звонку.",
    ),
    Screen(
        route="/payments",
        title="Платежи",
        purpose="Журнал всех платежей + быстрое создание нового.",
        layout="Sidebar + main. Сверху — кнопка «Новый платёж» (открывает Sheet). Далее — таблица.",
        components=[
            "Кнопка «+ Новый платёж» в правом верхнем углу",
            "Фильтры: период (date range), продукт",
            "Таблица: Клиент, Продукт, Сумма (выровнено вправо, bold), Период, Когда",
            "Sheet «Новый платёж»: UserPicker, Select продукта, Select периода, Input суммы, опц. Note",
            "Подтверждение «Платёж создан, инвайт-ссылка отправлена клиенту в бот»",
        ],
        states=[
            "loading", "empty — «Пока нет платежей»",
            "Sheet validation — disabled submit пока не выбраны обязательные поля",
            "submit-pending — спиннер на кнопке, fields disabled",
            "success → Toast + закрытие Sheet + refresh таблицы",
        ],
        actions=[
            "Сортировка таблицы по столбцу",
            "POST /api/payments → авто-генерация подписки и invite",
        ],
        mobile="Sheet раскрывается на весь экран, форма вертикальная.",
    ),
    Screen(
        route="/subscriptions",
        title="Подписки",
        purpose="Действующие/истёкшие/отозванные подписки с действиями.",
        layout="Sidebar + main. Сверху — 4 KPI карточки (активных / истекает в 7 дней / доход / средний чек). "
               "Далее — таблица.",
        components=[
            "4 KPI: активные, истекающие, доход, средний чек",
            "Табы статусов (Активные / Все)",
            "Таблица: Клиент, Продукт, Статус (Pill), До какой даты, Куплено, Действия (Продлить)",
            "Pill статус: active=green, expiring=amber, expired=gray, revoked=rose",
            "Кнопка «Продлить» → Sheet с выбором периода и суммы (вызывает /extend)",
            "Кнопка «Отозвать» (в детали) → confirm + reason",
        ],
        states=["loading", "empty", "action-pending", "success Toast"],
        actions=[
            "Продление → POST /api/subscriptions/{id}/extend",
            "Отзыв → POST /api/subscriptions/{id}/revoke (с подтверждением)",
        ],
        mobile="Таблица стэк-карточками: каждая подписка — отдельная карточка с кнопкой «Продлить».",
    ),
    Screen(
        route="/users",
        title="Пользователи",
        purpose="Поиск клиента по имени, @username, Telegram ID. Без полного списка.",
        layout="Sidebar + main. Большая строка поиска по центру, результаты — таблица под ней.",
        components=[
            "Input поиска с placeholder «Имя, @username или TG ID»",
            "Debounce 300ms на ввод",
            "Таблица результатов: Аватар + имя + @username, Кол-во заявок, Кол-во платежей, Активная подписка (Pill)",
            "Empty state до ввода: подсказка с примерами",
            "Empty state «ничего не найдено» после ввода",
        ],
        states=["initial (подсказка)", "typing", "loading", "results", "no-results"],
        actions=[
            "Клик по строке → /users/{id}",
            "Enter в поиске = форс-сабмит",
        ],
        mobile="Полная ширина поиска, результаты карточками.",
    ),
    Screen(
        route="/users/[id]",
        title="Профиль клиента",
        purpose="Контакты, заметки, история взаимодействий клиента — для контекста менеджера.",
        layout="Двухколоночная: слева — контакты и заметки, справа — вкладки истории.",
        components=[
            "PageHeader: аватар + имя + @username + Telegram ID (mono)",
            "Карточка «Контакты»: email, phone — редактируемые поля с auto-save",
            "Карточка «Заметка менеджера»: Textarea с auto-save",
            "Карточка «Источник» (если есть): первая ссылка, первая UTM-кампания",
            "Вкладки «Заявки» / «Платежи» / «Подписки» с таблицами",
            "Pill «Уведомления выключены» если notifications_enabled=false",
        ],
        states=["loading", "404", "saved (Toast)"],
        actions=[
            "Редактирование контактов → PATCH /api/users/{id} (auto-save)",
            "Клик по записи в истории → переход в соответствующий раздел",
        ],
        mobile="Все блоки в стек, вкладки оставляем горизонтально со скроллом.",
    ),
    Screen(
        route="/products",
        title="Продукты",
        purpose="CRUD продуктов с тарифами 3/6/12 мес.",
        layout="Sidebar + main. Сверху — кнопка «+ Новый продукт». Далее — таблица с инлайн-редактированием цен.",
        components=[
            "Кнопка «+ Новый продукт» (открывает Sheet)",
            "Таблица: Название, Код (mono), Канал, Цены (3 столбца компактно), Активен (Switch), Действия",
            "Sheet «Новый/Редактирование продукта» с полями: name, code, description, channel_id (Select), currency, 3 цены, cover_url",
            "Inline-валидация: уникальность code, цены >0",
        ],
        states=["loading", "empty", "form-validation"],
        actions=[
            "Создание / обновление / удаление (только Admin)",
            "Switch «Активен» — мгновенный toggle (PATCH)",
        ],
        mobile="Sheet на весь экран, таблица в стек-карточках.",
    ),
    Screen(
        route="/channels",
        title="Каналы",
        purpose="Закрытые TG-каналы, привязанные к ботам.",
        layout="Sidebar + main. Кнопка «+ Подключить канал». Таблица.",
        components=[
            "Кнопка «+ Подключить канал»",
            "Таблица: Название, @username, Бот (badge), Продуктов, Активных подписок, Действия",
            "Sheet с полями: Select бота, chat_id, опц. title",
            "Подсказка в Sheet: «Добавьте бота как админа в канал с правом invite»",
        ],
        states=["loading", "empty", "validation (бот не админ)"],
        actions=["CRUD каналов"],
        mobile="Стек-карточки.",
    ),
    Screen(
        route="/bots",
        title="Боты",
        purpose="Telegram-боты, подключённые к системе.",
        layout="Sidebar + main. Кнопка «+ Добавить бота». Таблица.",
        components=[
            "Кнопка «+ Добавить бота»",
            "Таблица: @username, ID, Каналов, Продуктов, Активен (Switch), Действия",
            "Sheet добавления: Input токена",
            "После сохранения — мгновенная валидация через getMe",
        ],
        states=["loading", "empty", "validation (невалидный токен)"],
        actions=["CRUD ботов, toggle is_active"],
        mobile="Стек-карточки.",
    ),
    Screen(
        route="/account",
        title="Профиль администратора",
        purpose="Смена пароля своего аккаунта.",
        layout="Центрированная карточка glass с формой смены пароля.",
        components=[
            "Поля: Текущий пароль, Новый пароль, Повтор нового",
            "Кнопка «Сменить пароль»",
            "Подсказка о требованиях к паролю",
            "Toast о результате",
        ],
        states=["default", "submit-pending", "error (старый неверный)", "success Toast"],
        actions=["POST /api/admin/password"],
        mobile="Карточка на всю ширину.",
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# Хелперы для docx
# ─────────────────────────────────────────────────────────────────────────────

def _hr(doc):
    p = doc.add_paragraph()
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:color"), "C7D2FE")
    pBdr.append(bottom)
    pPr.append(pBdr)


def _h(doc, text, *, size, color=INK, bold=True, before=0, after=6, align=None):
    p = doc.add_paragraph()
    if align == "center":
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(text)
    r.font.size = Pt(size)
    r.bold = bold
    r.font.color.rgb = color
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.space_after = Pt(after)
    return p


def _p(doc, text, *, size=11, color=INK, italic=False, bold=False, after=4, mono=False):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.font.size = Pt(size)
    r.italic = italic
    r.bold = bold
    r.font.color.rgb = color
    if mono:
        r.font.name = "Consolas"
    p.paragraph_format.space_after = Pt(after)
    return p


def _bullets(doc, items, *, size=10.5, color=INK):
    for it in items:
        b = doc.add_paragraph(it, style="List Bullet")
        for r in b.runs:
            r.font.size = Pt(size)
            r.font.color.rgb = color
        b.paragraph_format.space_after = Pt(2)


# ─────────────────────────────────────────────────────────────────────────────
# Рендеринг
# ─────────────────────────────────────────────────────────────────────────────

def render_db_section(doc):
    _h(doc, "Часть 1. База данных", size=22, color=INK, before=0, after=10)
    _p(doc,
       "Postgres 16. 8 таблиц в Core-версии. Все имена в snake_case, первичные ключи — BIGINT. "
       "Временные метки — TIMESTAMPTZ. Денежные суммы — NUMERIC(10,2). "
       "Каскады задаются ниже у каждой таблицы в разделе «Внешние ключи».", after=8)

    # Сводная карта таблиц
    _h(doc, "Схема: 8 таблиц Core", size=14, color=INDIGO, before=6, after=4)
    sketch = (
        "admins ─┐\n"
        "        ├─→ payments → subscriptions ←─ channels ←─ bots\n"
        "users ──┤                                  ↑\n"
        "        └─→ leads ──→ products ────────────┘\n"
    )
    _p(doc, sketch, mono=True, size=10, color=MUTED, after=10)

    for t in TABLES:
        _h(doc, f"Таблица «{t.name}»", size=14, color=INDIGO, before=12, after=3)
        _p(doc, t.desc, italic=True, color=MUTED, after=4)

        # Поля
        _p(doc, "Поля", size=10, bold=True, color=INK, after=2)
        ftable = doc.add_table(rows=1 + len(t.fields), cols=4)
        ftable.style = "Light Grid Accent 1"
        hdr = ftable.rows[0].cells
        hdr[0].text = "Поле"
        hdr[1].text = "Тип"
        hdr[2].text = "Null"
        hdr[3].text = "Описание"
        for c in hdr:
            for p in c.paragraphs:
                for r in p.runs:
                    r.bold = True
                    r.font.size = Pt(10)
        for i, f in enumerate(t.fields, start=1):
            cells = ftable.rows[i].cells
            cells[0].text = f.name
            cells[1].text = f.type
            cells[2].text = "✓" if f.nullable else ""
            cells[3].text = f.note
            for p in cells[0].paragraphs:
                for r in p.runs:
                    r.font.name = "Consolas"
                    r.font.size = Pt(9.5)
                    r.font.color.rgb = INK
            for p in cells[1].paragraphs:
                for r in p.runs:
                    r.font.name = "Consolas"
                    r.font.size = Pt(9.5)
                    r.font.color.rgb = INDIGO
            for p in cells[2].paragraphs:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                for r in p.runs:
                    r.font.size = Pt(9.5)
            for p in cells[3].paragraphs:
                for r in p.runs:
                    r.font.size = Pt(9.5)
                    r.font.color.rgb = MUTED
        for row in ftable.rows:
            row.cells[0].width = Cm(4.0)
            row.cells[1].width = Cm(4.5)
            row.cells[2].width = Cm(1.0)
            row.cells[3].width = Cm(7.5)

        # Индексы
        if t.indexes:
            _p(doc, "Индексы", size=10, bold=True, color=INK, after=2)
            _bullets(doc, t.indexes, size=10)

        # FK
        if t.fks:
            _p(doc, "Внешние ключи", size=10, bold=True, color=INK, after=2)
            _bullets(doc, t.fks, size=10)

    # Принципы каскадов
    _h(doc, "Принципы каскадов и удалений", size=14, color=INDIGO, before=14, after=4)
    _bullets(doc, [
        "RESTRICT там, где удаление сломает бизнес-логику (нельзя удалить продукт с активными подписками).",
        "CASCADE для зависимых записей (заявки удаляются вместе с пользователем).",
        "SET NULL для опциональных ссылок (admin_id в платеже может потерять автора).",
        "Soft-delete (флаг is_active) для частых сценариев временного отключения.",
    ])


def render_api_section(doc):
    doc.add_page_break()
    _h(doc, "Часть 2. API", size=22, color=INK, before=0, after=10)
    _p(doc,
       "FastAPI, async/await. Префикс всех endpoint'ов — /api. Все ответы — JSON. "
       "Аутентификация — JWT в HttpOnly Secure cookie, TTL 7 дней. "
       "RBAC: admin / manager (см. колонку «Доступ» у каждого endpoint).", after=8)

    _h(doc, "Общие принципы", size=14, color=INDIGO, before=6, after=4)
    _bullets(doc, [
        "Все даты в ответах — ISO 8601 в UTC.",
        "Денежные суммы — строкой decimal (не float), чтобы не терять копейки.",
        "Пагинация — query-параметры limit (по умолчанию 50, макс 200) и offset.",
        "Фильтрация — query-параметры с явными именами.",
        "Стандартные коды ошибок: 400 (валидация), 401 (нет токена), 403 (нет прав), "
        "404 (не найдено), 409 (конфликт состояния), 422 (Pydantic), 429 (rate-limit).",
        "В payload ошибки: { detail: str | object }.",
    ])

    _h(doc, "Поля в ответе по умолчанию", size=14, color=INDIGO, before=10, after=4)
    _bullets(doc, [
        "id, created_at — есть у всех сущностей.",
        "В list-эндпоинтах ответ может быть массивом напрямую или объектом { items, total }.",
        "Связанные сущности подгружаются inline (например, user в lead — не отдельным запросом).",
    ])

    for g in API_GROUPS:
        _h(doc, g.title, size=14, color=INDIGO, before=14, after=3)
        _p(doc, f"Префикс: {g.prefix}", italic=True, color=MUTED, after=3)
        _p(doc, g.desc, after=4)

        for e in g.endpoints:
            # Заголовок endpoint
            p = doc.add_paragraph()
            r_m = p.add_run(f"{e.method}  ")
            r_m.font.name = "Consolas"
            r_m.bold = True
            r_m.font.size = Pt(11)
            r_m.font.color.rgb = GREEN if e.method == "GET" else (INDIGO if e.method == "POST" else (ROSE if e.method == "DELETE" else INK))

            r_path = p.add_run(e.path)
            r_path.font.name = "Consolas"
            r_path.font.size = Pt(11)
            r_path.bold = True
            r_path.font.color.rgb = INK

            r_acc = p.add_run(f"   [{e.access}]")
            r_acc.font.size = Pt(9.5)
            r_acc.font.color.rgb = MUTED

            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.left_indent = Cm(0.3)

            # Описание
            d = doc.add_paragraph(e.desc)
            d.paragraph_format.left_indent = Cm(0.8)
            d.paragraph_format.space_after = Pt(2)
            for r in d.runs:
                r.font.size = Pt(10.5)
                r.font.color.rgb = INK

            # Request / Response / Errors
            def _kv(label, value, color):
                if not value or value == "—":
                    return
                k = doc.add_paragraph()
                kr = k.add_run(f"{label}: ")
                kr.bold = True
                kr.font.size = Pt(9.5)
                kr.font.color.rgb = color
                vr = k.add_run(value)
                vr.font.size = Pt(9.5)
                vr.font.color.rgb = INK
                vr.font.name = "Consolas" if value.startswith(("{", "[", "—", "?")) else None
                k.paragraph_format.left_indent = Cm(0.8)
                k.paragraph_format.space_after = Pt(1)

            _kv("Запрос", e.request, INDIGO)
            _kv("Ответ", e.response, GREEN)
            _kv("Ошибки", e.errors, ROSE)

            spacer = doc.add_paragraph()
            spacer.paragraph_format.space_after = Pt(3)


def render_design_section(doc):
    doc.add_page_break()
    _h(doc, "Часть 3. Дизайн", size=22, color=INK, before=0, after=10)
    _p(doc,
       "Веб-приложение (Next.js 15 + React 19 + TailwindCSS). Адаптивное от 360px до 4K. "
       "13 экранов в Core. Стиль — glassmorphism с indigo→rose акцентом, бренд Grammy.", after=8)

    # Общая дизайн-система
    _h(doc, "Дизайн-система", size=14, color=INDIGO, before=6, after=4)
    _p(doc, "Цвета:", bold=True, size=10, after=2)
    _bullets(doc, [
        "Ink (основной текст): #1E1B4B",
        "Muted (вторичный текст): #6B7280",
        "Indigo (акцент / интерактив): #6366F1",
        "Rose (вторичный акцент / опасно): #F43F5E",
        "Green (успех / paid / active): #10B981",
        "Amber (внимание / new): #F59E0B",
        "Background: gradient blob'ы indigo/rose/teal на f4f6fb",
    ])
    _p(doc, "Шрифты:", bold=True, size=10, after=2, color=INK)
    _bullets(doc, [
        "Inter (web font Google Fonts), веса 400 / 500 / 600 / 700 / 800",
        "Моноширинный — Consolas / Menlo для кодов и mono-данных",
    ])
    _p(doc, "Компоненты-примитивы (общие для всех экранов):", bold=True, size=10, after=2, color=INK)
    _bullets(doc, [
        "Button (primary / ghost / danger, размеры sm/md/lg, gradient-вариант)",
        "Input / Textarea / Select / Field (с подписью и hint)",
        "Card (glass / glass-strong / glass-soft)",
        "Sheet (правое модальное окно для форм)",
        "Pill (цветной бейдж: gray / amber / green / rose / indigo)",
        "TableWrap + Th + Td + Tr (с min-width для скролла)",
        "Empty (пустое состояние с иллюстрацией)",
        "Toast (success / error / info, auto-dismiss 2.4 сек)",
        "UserPicker (Combobox-поиск пользователей с автодополнением)",
    ])

    # Общая раскладка
    _h(doc, "Общая раскладка приложения", size=14, color=INDIGO, before=12, after=4)
    _p(doc,
       "Все экраны (кроме /login) используют единый layout: sidebar слева 260px + main area. "
       "Sidebar содержит 5 групп для Core: «Обзор», «Продажи» (Заявки / Платежи / Подписки), "
       "«Каталог» (Продукты / Каналы / Боты), «Аудитория» (Пользователи), профиль внизу.")
    _p(doc,
       "Header sticky с breadcrumbs и amber-бейджем новых заявок видим на всех страницах. "
       "На мобиле sidebar превращается в overlay-меню по бургеру.")

    # Раздел по экранам
    _h(doc, "Экраны (13 в Core)", size=14, color=INDIGO, before=14, after=4)
    _p(doc,
       "Для каждого экрана указано: маршрут, назначение, раскладка, ключевые компоненты, "
       "состояния (loading / empty / error), доступные действия, поведение на мобильных.",
       italic=True, color=MUTED, after=8)

    for i, s in enumerate(SCREENS, start=1):
        _h(doc, f"{i}. {s.title}  —  {s.route}", size=13, color=INDIGO, before=10, after=2)

        _p(doc, s.purpose, italic=True, color=MUTED, after=4)

        _p(doc, "Раскладка", size=10, bold=True, after=2)
        _p(doc, s.layout, size=10.5, after=4)

        _p(doc, "Компоненты экрана", size=10, bold=True, after=2)
        _bullets(doc, s.components, size=10)

        _p(doc, "Состояния", size=10, bold=True, after=2)
        _bullets(doc, s.states, size=10)

        _p(doc, "Действия пользователя", size=10, bold=True, after=2)
        _bullets(doc, s.actions, size=10)

        if s.mobile:
            _p(doc, "Поведение на смартфоне", size=10, bold=True, after=2)
            _p(doc, s.mobile, size=10, after=4)

        _hr(doc)

    # Адаптивность общая
    _h(doc, "Адаптивность", size=14, color=INDIGO, before=14, after=4)
    _bullets(doc, [
        "Брейкпоинты: < 640px (mobile), 640-1023px (tablet), 1024+ (desktop)",
        "Sidebar: fixed-overlay на mobile, sticky 260px на tablet+",
        "Таблицы: min-width c горизонтальным скроллом, на mobile — стек карточек",
        "Формы: вертикальный layout на mobile, двух-колоночный на desktop",
        "Кнопки: высота не менее 40px для touch (mobile)",
    ])

    # Брендинг
    _h(doc, "Брендинг и фирменные элементы", size=14, color=INDIGO, before=14, after=4)
    _bullets(doc, [
        "Логотип-винил (SVG) — фавикон, иконка в sidebar, watermark на login",
        "Title всех страниц: «{Раздел} · Grammy»",
        "OG-картинка для шаринга в чатах: тёмный фон + большой Grammy + tagline",
        "Manifest для PWA — можно добавить на главный экран iOS/Android",
        "robots.txt = Disallow / — закрыто от поисковиков",
    ])


def build():
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    # Титул
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = title.add_run("Техническое задание\nGrammy · Core")
    r.font.size = Pt(28)
    r.bold = True
    r.font.color.rgb = INK

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rs = sub.add_run("База данных · API · Дизайн экранов")
    rs.font.size = Pt(14)
    rs.font.color.rgb = MUTED
    sub.paragraph_format.space_after = Pt(8)

    doc.add_paragraph()
    note = doc.add_paragraph()
    note.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rn = note.add_run("3 части · 8 таблиц БД · ~30 endpoints · 13 экранов")
    rn.italic = True
    rn.font.size = Pt(10.5)
    rn.font.color.rgb = MUTED

    doc.add_page_break()

    # 3 раздела
    render_db_section(doc)
    render_api_section(doc)
    render_design_section(doc)

    doc.save(OUT_DOCX)
    return OUT_DOCX


def main():
    path = build()
    total_endpoints = sum(len(g.endpoints) for g in API_GROUPS)
    print(f"✓ ТЗ: {path} ({path.stat().st_size // 1024} KB)")
    print(f"  {len(TABLES)} таблиц БД · {total_endpoints} endpoints · {len(SCREENS)} экранов")


if __name__ == "__main__":
    main()
