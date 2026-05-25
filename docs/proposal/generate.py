"""
Генератор ТЗ (docx) и сметы (xlsx) для проекта Grammy.

Запуск:
  python3 docs/proposal/generate.py

Результат:
  docs/proposal/Grammy_TZ.docx
  docs/proposal/Grammy_Smeta.xlsx

Зависимости: python-docx, openpyxl.

Логика:
- MODULES — единый источник правды по модулям (ФТ, User Flow, Use Cases, задачи и часы).
- HOURLY_RATE — ставка в одном месте; в Excel — формула, всё пересчитывается из одной ячейки.
- OPTIONS — три пакета комплектации (Базовый / Стандарт / Премиум), каждый модуль помечен принадлежностью.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

# ─────────────────────────────────────────────────────────────────────────────
# Параметры
# ─────────────────────────────────────────────────────────────────────────────

PROJECT_NAME = "Grammy"
PROJECT_TAGLINE = "Telegram-бот продажи доступа в закрытые каналы + админ-панель"
HOURLY_RATE = 3500  # ₽/час, параметризовано в Excel

OUT_DIR = Path(__file__).resolve().parent
DOCX_PATH = OUT_DIR / f"{PROJECT_NAME}_TZ.docx"
XLSX_PATH = OUT_DIR / f"{PROJECT_NAME}_Smeta.xlsx"


# ─────────────────────────────────────────────────────────────────────────────
# Структуры данных
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Task:
    """Атомарная задача внутри модуля — строка в смете."""
    name: str
    backend: int = 0
    frontend: int = 0
    design: int = 0
    devops: int = 0
    qa: int = 0

    @property
    def total(self) -> int:
        return self.backend + self.frontend + self.design + self.devops + self.qa


@dataclass
class Flow:
    name: str
    steps: List[str]


@dataclass
class UseCase:
    name: str
    actor: str
    precondition: str
    steps: List[str]
    result: str


@dataclass
class Module:
    id: str
    title: str
    summary: str
    goals: List[str]
    fts: List[str]
    flows: List[Flow]
    use_cases: List[UseCase]
    tech: List[str]
    acceptance: List[str]
    tasks: List[Task]
    options: List[str] = field(default_factory=list)  # "base" / "standard" / "premium"

    @property
    def total_hours(self) -> int:
        return sum(t.total for t in self.tasks)

    @property
    def sum_backend(self) -> int: return sum(t.backend for t in self.tasks)
    @property
    def sum_frontend(self) -> int: return sum(t.frontend for t in self.tasks)
    @property
    def sum_design(self) -> int: return sum(t.design for t in self.tasks)
    @property
    def sum_devops(self) -> int: return sum(t.devops for t in self.tasks)
    @property
    def sum_qa(self) -> int: return sum(t.qa for t in self.tasks)


# ─────────────────────────────────────────────────────────────────────────────
# СОДЕРЖАНИЕ МОДУЛЕЙ
# ─────────────────────────────────────────────────────────────────────────────

MODULES: List[Module] = [
    # ─────────────────────────── M01 ───────────────────────────
    Module(
        id="M01",
        title="Платформа и инфраструктура",
        summary=(
            "Развёртывание production-окружения проекта: контейнеризация всех сервисов, "
            "управляемая БД Postgres, обратный прокси с HTTPS-сертификатом, автоматический "
            "выпуск и продление SSL, базовые health-check'и и автоматическая очистка "
            "Docker-кэша. Это фундамент, на котором стоят все остальные модули."
        ),
        goals=[
            "Запускать всю систему одной командой на новом сервере.",
            "Получать HTTPS «из коробки», без ручных операций с сертификатами.",
            "Иметь предсказуемую процедуру обновления (rsync + docker compose).",
            "Не давать диску забиваться кэшем сборок (авточистка).",
        ],
        fts=[
            "ФТ-01.1. Все сервисы (backend, admin, db, nginx, certbot) запускаются через единый docker-compose.",
            "ФТ-01.2. БД Postgres 16 хранится в именованном Docker volume и проходит healthcheck до старта backend.",
            "ФТ-01.3. Nginx терминирует SSL и проксирует /api на backend, остальное на admin.",
            "ФТ-01.4. Certbot автоматически продлевает сертификат Let's Encrypt каждые 12 ч.",
            "ФТ-01.5. Backend на старте автоматически применяет миграции Alembic (alembic upgrade head).",
            "ФТ-01.6. Имеется endpoint /api/healthz для проверки живости.",
            "ФТ-01.7. Cron daily очищает Docker builder cache и dangling images старше 72 ч.",
            "ФТ-01.8. Файл .env содержит все секреты; .env.example описывает каждый параметр.",
        ],
        flows=[
            Flow(
                name="Развёртывание на новом сервере",
                steps=[
                    "Администратор подготавливает VM с Docker и docker compose.",
                    "Заливает код через rsync в /opt/grammy.",
                    "Заполняет .env (БД, JWT, ADMIN_PASSWORD, доменное имя).",
                    "Выполняет docker compose up -d.",
                    "Certbot получает сертификат при первом запуске; nginx подхватывает.",
                    "Backend накатывает миграции; admin доступен по HTTPS на домене.",
                ],
            ),
            Flow(
                name="Обновление до новой версии",
                steps=[
                    "rsync новой версии в /opt/grammy (с исключением .env, certbot/).",
                    "docker compose build admin backend.",
                    "docker compose up -d admin backend — Postgres и nginx не пересоздаются.",
                    "Миграция накатывается автоматически.",
                    "Cron в течение суток очищает старый builder cache.",
                ],
            ),
        ],
        use_cases=[
            UseCase(
                name="UC-01.1. Аварийный перезапуск backend",
                actor="DevOps",
                precondition="Backend упал из-за ошибки приложения, контейнер в Restarting.",
                steps=[
                    "Запускает docker compose logs backend и видит причину.",
                    "Откатывает изменения или фиксит конфиг.",
                    "docker compose up -d backend.",
                    "Проверяет /api/healthz → 200.",
                ],
                result="Сервис снова доступен, downtime < 5 минут.",
            ),
        ],
        tech=[
            "Docker Compose v2", "PostgreSQL 16", "Nginx (alpine)",
            "Certbot (Let's Encrypt webroot)", "cron",
        ],
        acceptance=[
            "После `docker compose up -d` на чистой VM сайт открывается по HTTPS за < 5 минут.",
            "Сертификат продлевается без вмешательства администратора.",
            "Используемое место Docker за месяц не растёт более чем на 1 ГБ.",
        ],
        tasks=[
            Task("Docker Compose: db / backend / admin / nginx / certbot", devops=14, qa=2),
            Task("Healthcheck Postgres + /api/healthz endpoint", backend=3, qa=1),
            Task("Nginx-конфиг с SSL termination и проксированием", devops=6, qa=2),
            Task("Certbot webroot + auto-renew", devops=4, qa=1),
            Task("Cron daily docker cleanup", devops=3),
            Task(".env / .env.example / документация переменных", devops=3),
        ],
        options=["base", "standard", "premium"],
    ),

    # ─────────────────────────── M02 ───────────────────────────
    Module(
        id="M02",
        title="Аутентификация и RBAC",
        summary=(
            "Закрытая админ-панель: вход по логину/паролю, JWT в HttpOnly-cookie, "
            "три роли с разной полнотой прав, защита от подбора пароля, смена пароля, "
            "audit-friendly identity на каждом запросе."
        ),
        goals=[
            "Не пускать в админку посторонних.",
            "Разграничить, что может admin (всё), manager (без удалений) и viewer (только просмотр).",
            "Гарантировать, что пароли хранятся в bcrypt-хэше, а токен — не доступен из JS.",
        ],
        fts=[
            "ФТ-02.1. POST /api/auth/login принимает username+password, возвращает HttpOnly-cookie с JWT.",
            "ФТ-02.2. JWT — HS256, TTL 7 дней; cookie помечается Secure и SameSite=Lax.",
            "ФТ-02.3. POST /api/auth/logout удаляет cookie.",
            "ФТ-02.4. GET /api/auth/me возвращает текущего администратора (id, username, role).",
            "ФТ-02.5. Rate-limit на /login: 10 попыток за 60 секунд по IP, in-memory.",
            "ФТ-02.6. Роли admin / manager / viewer проверяются через зависимость require_role(...).",
            "ФТ-02.7. Смена пароля /api/admin/password требует ввода старого пароля.",
            "ФТ-02.8. На фронте unauthenticated-юзер автоматически редиректится на /login.",
        ],
        flows=[
            Flow(
                name="Первый вход",
                steps=[
                    "Открывает домен → редирект на /login.",
                    "Вводит логин и пароль администратора.",
                    "Backend проверяет bcrypt-хэш, возвращает cookie.",
                    "Фронт делает GET /auth/me, получает роль, кладёт в layout.",
                    "Sidebar отображается с пунктами по роли (admin видит «Аудит-журнал» и т.п.).",
                ],
            ),
            Flow(
                name="Истечение токена",
                steps=[
                    "Юзер работает в админке, токен истекает по TTL.",
                    "Любой запрос возвращает 401.",
                    "fetch-обёртка автоматически редиректит на /login.",
                ],
            ),
        ],
        use_cases=[
            UseCase(
                name="UC-02.1. Менеджер пытается удалить продукт",
                actor="Manager",
                precondition="Менеджер залогинен, открыл /products.",
                steps=[
                    "Нажимает «Удалить».",
                    "Фронт отправляет DELETE /api/products/{id}.",
                    "Backend через require_role('admin') возвращает 403.",
                    "Фронт показывает тост: «Недостаточно прав».",
                ],
                result="Продукт не удалён, действие логируется (audit).",
            ),
        ],
        tech=[
            "JWT (python-jose, HS256)", "bcrypt (passlib)", "FastAPI Depends",
            "HttpOnly Secure cookie", "SWR-обёртка с 401-handling на фронте",
        ],
        acceptance=[
            "Пароли не лежат в БД в открытом виде; токен не доступен из document.cookie.",
            "После 10 неуспешных попыток вход блокируется на 1 минуту.",
            "Manager не может удалить ни один ресурс через UI и через прямой API-вызов.",
        ],
        tasks=[
            Task("Backend: модель Admin + миграция + bcrypt-утилиты", backend=4, qa=2),
            Task("Endpoint /auth/login + JWT + cookie + rate-limit", backend=6, qa=4),
            Task("Endpoint /auth/me + /auth/logout + смена пароля", backend=3, qa=2),
            Task("Dependency current_admin + require_role(*)", backend=3, qa=2),
            Task("Frontend: /login форма + redirect логика", frontend=6, design=3, qa=2),
            Task("Frontend: auth-check в layout, fetch-обёртка с 401", frontend=4, qa=2),
            Task("UX: пустые поля, ошибки, состояние «вошёл»", design=3),
        ],
        options=["base", "standard", "premium"],
    ),

    # ─────────────────────────── M03 ───────────────────────────
    Module(
        id="M03",
        title="Каталог: продукты, каналы, боты",
        summary=(
            "Сущности, вокруг которых строится продажа: Telegram-бот (носитель), "
            "закрытый канал (товар), продукт с ценами на 3/6/12 месяцев. Полный CRUD "
            "в админке с валидацией ссылок между сущностями."
        ),
        goals=[
            "Подключать любое число ботов и каналов без правки кода.",
            "Гибко настраивать ценовые тарифы под продукт (3/6/12 мес).",
            "Гарантировать, что нельзя удалить сущность, на которую ссылаются другие.",
        ],
        fts=[
            "ФТ-03.1. Бот подключается одним полем — токеном; backend валидирует токен через getMe.",
            "ФТ-03.2. После добавления бот сразу попадает в polling-менеджер (без рестарта сервиса).",
            "ФТ-03.3. Канал привязывается к боту; backend проверяет, что бот может приглашать в канал.",
            "ФТ-03.4. Продукт имеет уникальный code (для deep-link /start), три цены и валюту.",
            "ФТ-03.5. Удаление сущности с зависимыми объектами блокируется (RESTRICT с понятным сообщением).",
            "ФТ-03.6. UI показывает счётчики у каждой сущности: продукты, активные подписки, лиды.",
        ],
        flows=[
            Flow(
                name="Запуск нового канала на продажу",
                steps=[
                    "Админ добавляет бота (вводит токен).",
                    "Добавляет канал, выбрав ранее созданного бота.",
                    "Создаёт продукт, привязывает к каналу, задаёт цены.",
                    "Открывает страницу продукта → видит автоматически сгенерированную tracking-ссылку.",
                ],
            ),
        ],
        use_cases=[
            UseCase(
                name="UC-03.1. Конфликт code продукта и slug ссылки",
                actor="Admin",
                precondition="Уже существует tracking-link со slug=launch_2026.",
                steps=[
                    "Админ создаёт продукт с code=launch_2026.",
                    "Backend возвращает 409 Conflict с пояснением.",
                    "UI подсвечивает поле code красным.",
                ],
                result="Конфликт предотвращён, deep-link однозначен.",
            ),
        ],
        tech=[
            "SQLAlchemy 2.0 async", "aiogram 3.x (getMe, getChat)",
            "Next.js + SWR (батч-counts через JOIN)",
        ],
        acceptance=[
            "Через UI можно завести бота, канал и продукт за < 3 минут.",
            "Удаление каскадно блокируется при наличии зависимостей.",
            "Бот, отключённый в UI, перестаёт принимать сообщения за < 30 секунд.",
        ],
        tasks=[
            Task("Backend: модели Bot/Channel/Product + миграции", backend=4, qa=2),
            Task("Backend API /bots (CRUD, getMe-валидация, sync polling)", backend=6, qa=3),
            Task("Backend API /channels (CRUD, проверка прав бота)", backend=5, qa=3),
            Task("Backend API /products (CRUD, code-unique, collision-check)", backend=6, qa=3),
            Task("Frontend: страница /bots", frontend=6, qa=2),
            Task("Frontend: страница /channels", frontend=6, qa=2),
            Task("Frontend: страница /products + детали + ссылки", frontend=12, qa=3),
            Task("Дизайн: формы CRUD, пустые состояния, badges", design=6),
        ],
        options=["base", "standard", "premium"],
    ),

    # ─────────────────────────── M04 ───────────────────────────
    Module(
        id="M04",
        title="Пользователи и first-touch",
        summary=(
            "Учёт всех Telegram-пользователей, прошедших через бота. Идемпотентная фиксация "
            "first-touch (первый бот, первая ссылка, первая UTM-метка) — основа для атрибуции "
            "и аналитики. Поиск, профиль с историей заявок / платежей / подписок."
        ),
        goals=[
            "Понимать, кто привёл каждого юзера в проект — и не терять эту информацию.",
            "Быстро находить пользователя по @username, имени или TG ID.",
            "Видеть на одном экране всю его историю взаимодействия.",
        ],
        fts=[
            "ФТ-04.1. При первом /start или сообщении создаётся запись User, заполняются first_*-поля.",
            "ФТ-04.2. first_*-поля заполняются ровно один раз и не перезаписываются (идемпотентно).",
            "ФТ-04.3. current_tracking_link_id сохраняется как «горячая» атрибуция на 30 минут (для last-touch).",
            "ФТ-04.4. Поиск по подстроке в username, first_name, last_name, telegram_user_id.",
            "ФТ-04.5. Профиль показывает контакты, заявки, платежи, подписки в трёх вкладках.",
            "ФТ-04.6. Админ может вручную дополнить email/phone/notes.",
            "ФТ-04.7. Пользователь может отказаться от уведомлений (отдельный флаг), бот это учитывает.",
        ],
        flows=[
            Flow(
                name="Поиск и редактирование контактов",
                steps=[
                    "Менеджер открывает /users.",
                    "Вводит @username в строку поиска.",
                    "Видит совпадения, кликает на нужного.",
                    "Дополняет email и заметку «обещал оплатить через 2 дня».",
                    "Возвращается в /leads, видит контекст по этому юзеру.",
                ],
            ),
        ],
        use_cases=[
            UseCase(
                name="UC-04.1. Повторный заход юзера по другой ссылке",
                actor="Telegram-пользователь",
                precondition="User уже есть в БД с first_tracking_link_id=#42.",
                steps=[
                    "Кликает другую ссылку /start?slug=YT2.",
                    "Backend апдейтит current_tracking_link_id=#77.",
                    "first_tracking_link_id остаётся #42.",
                ],
                result="First-touch сохранён, last-touch обновлён.",
            ),
        ],
        tech=[
            "SQLAlchemy partial-update", "Идемпотентность через NULL-check",
            "Композитный индекс по telegram_user_id",
        ],
        acceptance=[
            "Тысячный /start того же юзера не перезаписывает first_*-поля.",
            "Поиск по 100 000 пользователей возвращает результаты за < 200 мс.",
            "Если юзер отключил уведомления — воронка ему не доставляется.",
        ],
        tasks=[
            Task("Backend: модель User + first_* поля + миграции", backend=4, qa=2),
            Task("Backend: идемпотентная функция _set_first_touch", backend=3, qa=3),
            Task("Backend API /users (поиск, профиль с JOIN)", backend=5, qa=3),
            Task("Frontend: /users со строкой поиска", frontend=6, qa=2),
            Task("Frontend: /users/[id] с тремя вкладками истории", frontend=6, qa=2),
            Task("Дизайн: профиль пользователя", design=4),
        ],
        options=["base", "standard", "premium"],
    ),

    # ─────────────────────────── M05 ───────────────────────────
    Module(
        id="M05",
        title="Заявки (Leads)",
        summary=(
            "Учёт «холодного» интереса к продукту: пользователь нажал «Оставить заявку» в боте — "
            "создаётся Lead со статусом new. Менеджер ведёт её по воронке "
            "new → contacted → paid → closed с фиксацией временных меток на каждом шаге."
        ),
        goals=[
            "Не терять ни одной заявки.",
            "Видеть, по какой ссылке пришёл клиент (last-touch на момент клика).",
            "Замерять время «до контакта» и «до оплаты» — для оптимизации воронки.",
        ],
        fts=[
            "ФТ-05.1. Кнопка «Оставить заявку» в боте создаёт Lead и стартует default-воронку продукта.",
            "ФТ-05.2. Заявка сохраняет tracking_link_id из current_link юзера (last-touch, TTL 30 мин).",
            "ФТ-05.3. Статусы: new → contacted → paid → closed; на каждом ставится соответствующий timestamp.",
            "ФТ-05.4. На странице /leads фильтр по статусу через табы.",
            "ФТ-05.5. На странице /leads/[id] видны контакты, продукт, источник, история статусов.",
            "ФТ-05.6. Smart-переход: создание Payment вручную автоматически переводит свежий Lead в paid.",
            "ФТ-05.7. Экспорт списка лидов в CSV (для отчёта менеджера).",
        ],
        flows=[
            Flow(
                name="Обычная заявка → оплата",
                steps=[
                    "Юзер нажал «Оставить заявку» в боте.",
                    "Создан Lead со статусом new, source = tracking_link_id.",
                    "Менеджер открывает /leads, видит новую (badge в сайдбаре).",
                    "Связывается с клиентом, ставит «contacted».",
                    "После оплаты создаёт Payment → Lead переходит в paid.",
                ],
            ),
        ],
        use_cases=[
            UseCase(
                name="UC-05.1. Просрочка контакта",
                actor="Manager",
                precondition="Заявка висит со статусом new более 24 ч.",
                steps=[
                    "Sidebar показывает счётчик «Новых: 7» с оранжевой плашкой.",
                    "Менеджер открывает /leads?status=new.",
                    "Видит свежие заявки сверху.",
                ],
                result="Менеджер начинает обработку, заявка не теряется.",
            ),
        ],
        tech=[
            "Status FSM на уровне сервиса", "Last-touch резолв через current_link",
            "CSV-экспорт через FastAPI StreamingResponse",
        ],
        acceptance=[
            "Создание Lead из бота занимает < 200 мс.",
            "Переход статусов нельзя выполнить в обратную сторону (closed → new).",
            "CSV-экспорт корректно открывается в Excel (UTF-8 BOM, разделитель ;).",
        ],
        tasks=[
            Task("Backend: модель Lead + миграция + FSM", backend=4, qa=2),
            Task("Backend API /leads (CRUD, фильтр, экспорт CSV)", backend=6, qa=3),
            Task("Frontend: /leads с табами + badge в sidebar", frontend=8, qa=2),
            Task("Frontend: /leads/[id]", frontend=6, qa=2),
            Task("Дизайн: лид-карточка и таблица", design=4),
        ],
        options=["base", "standard", "premium"],
    ),

    # ─────────────────────────── M06 ───────────────────────────
    Module(
        id="M06",
        title="Платежи и подписки",
        summary=(
            "Учёт оплат и активных подписок на закрытые каналы. Платёж создаёт/продлевает "
            "подписку, генерирует одноразовый invite-link в канал и отправляет его клиенту. "
            "Истечение срока автоматически отзывает доступ. Поддержка Telegram Payments — "
            "опциональная (PreCheckout + SuccessfulPayment)."
        ),
        goals=[
            "Автоматизировать выдачу доступа после оплаты — без ручных приглашений.",
            "Не оставлять «вечно активных» подписчиков — автоматически выгонять по истечении срока.",
            "Дать менеджеру возможность вручную провести оплату (если клиент оплатил вне TG).",
        ],
        fts=[
            "ФТ-06.1. Платёж имеет period_months (3/6/12), amount, currency, привязку к user и product.",
            "ФТ-06.2. После создания платежа автоматически создаётся/продлевается Subscription.",
            "ФТ-06.3. Backend генерирует одноразовую invite-ссылку с member_limit=1, expire_at=ends_at.",
            "ФТ-06.4. Ссылка отправляется юзеру в Telegram через бота.",
            "ФТ-06.5. Свежий Lead этого пользователя по этому продукту автоматически переходит в paid.",
            "ФТ-06.6. При оплате product.cancel_on_payment активные воронки этого продукта останавливаются.",
            "ФТ-06.7. Worker expire_due (каждый час) переводит подписки с ends_at ≤ now в expired, кикает из канала.",
            "ФТ-06.8. Подписку можно продлить (extend, дни/месяцы) или досрочно отозвать (revoke).",
            "ФТ-06.9. Telegram Payments: PreCheckoutQuery валидирует, SuccessfulPayment создаёт Payment автоматически.",
        ],
        flows=[
            Flow(
                name="Ручная оплата менеджером",
                steps=[
                    "Менеджер открывает /payments → «Новый платёж».",
                    "Выбирает пользователя (UserPicker), продукт, период, вводит сумму.",
                    "Backend создаёт Payment + Subscription, генерирует invite-ссылку, шлёт юзеру.",
                    "Юзер получает в боте: «Доступ открыт до DD.MM.YYYY. Ссылка: ...».",
                ],
            ),
            Flow(
                name="Истечение подписки",
                steps=[
                    "Worker раз в час находит Subscription с ends_at ≤ now.",
                    "Меняет status=expired, кикает юзера из канала.",
                    "Отправляет сообщение: «Доступ к каналу окончен. Продлить можно...».",
                ],
            ),
        ],
        use_cases=[
            UseCase(
                name="UC-06.1. Повторная оплата до истечения старой",
                actor="Manager",
                precondition="У юзера активна подписка до 30.06.",
                steps=[
                    "Менеджер создаёт ещё один Payment на 6 мес.",
                    "Backend продлевает ту же Subscription: ends_at = 30.06 + 6 мес = 30.12.",
                    "Юзеру приходит: «Доступ продлён до 30.12.2026».",
                ],
                result="Подписка не дублируется, период суммируется.",
            ),
        ],
        tech=[
            "APScheduler hourly job", "aiogram createChatInviteLink / banChatMember",
            "Telegram Payments (PreCheckoutQuery, SuccessfulPayment)",
        ],
        acceptance=[
            "Платёж создан → invite-ссылка приходит юзеру в течение 5 секунд.",
            "Подписка с истекшим ends_at гарантированно отзывается в течение 1 часа.",
            "Повторный платёж до истечения корректно суммирует периоды.",
        ],
        tasks=[
            Task("Backend: модели Payment + Subscription + миграции", backend=4, qa=2),
            Task("Backend: сервис subscriptions.grant_for_payment", backend=8, qa=4),
            Task("Backend: revoke/extend + интеграция aiogram (kick, invite)", backend=6, qa=3),
            Task("Backend API /payments + /subscriptions", backend=6, qa=3),
            Task("Backend: worker expire_due (APScheduler hourly)", backend=4, qa=2),
            Task("Backend: Telegram Payments — PreCheckout + SuccessfulPayment", backend=6, qa=3),
            Task("Frontend: /payments + UserPicker", frontend=10, qa=2),
            Task("Frontend: /subscriptions с действиями revoke/extend", frontend=8, qa=2),
            Task("Дизайн: формы платежа, статусы подписок", design=6),
        ],
        options=["base", "standard", "premium"],
    ),

    # ─────────────────────────── M07 ───────────────────────────
    Module(
        id="M07",
        title="Воронки прогрева (Студия)",
        summary=(
            "Сценарии follow-up сообщений: серия отложенных сообщений с лидмагнитами, "
            "которые бот сам шлёт юзеру после подписки или кодового слова. Студия в админке — "
            "флагман UX: 4 секции (параметры → шаги → точки входа → запуск), drag-n-drop "
            "по шагам, rich-text редактор под Telegram HTML, реалтайм-превью как в Telegram, "
            "auto-save и безопасные подтверждения при правке активных воронок."
        ),
        goals=[
            "Дать неинженеру возможность собрать прогревочную кампанию за 15-30 минут.",
            "Сделать невозможной отправку «сырого» сообщения с поломанным HTML.",
            "Защитить активных подписчиков воронки от случайных правок.",
        ],
        fts=[
            "ФТ-07.1. Воронка состоит из шагов: задержка от старта + текст + опционально лидмагнит + inline-кнопки.",
            "ФТ-07.2. Поддерживается полный набор Telegram HTML: b, i, u, s, code, pre, blockquote (expandable), tg-spoiler, ссылка.",
            "ФТ-07.3. Rich-text редактор имеет тулбар, хоткеи (⌘B/I/U/K/E), сохраняет нативный undo через execCommand.",
            "ФТ-07.4. Реалтайм-превью отрисовывает сообщение визуально как в Telegram (включая лидмагнит и кнопки).",
            "ФТ-07.5. Шаги переупорядочиваются drag-n-drop.",
            "ФТ-07.6. Шаги auto-save с debounce 1 сек.",
            "ФТ-07.7. При правке активной воронки UI показывает warning и confirm-диалог (сколько подписчиков затронет).",
            "ФТ-07.8. При старте воронки для юзера расписываются ScheduledMessage на каждый шаг с delay_minutes.",
            "ФТ-07.9. При отмене воронки все непротправленные сообщения отменяются массово.",
            "ФТ-07.10. Если product.cancel_on_payment=true — оплата автоматически отменяет воронку.",
            "ФТ-07.11. ttl_days ограничивает максимальную длину воронки (по умолчанию 90).",
            "ФТ-07.12. Worker scheduled_messages обрабатывает очередь батчами по 100 каждые 5 минут.",
        ],
        flows=[
            Flow(
                name="Создание воронки с нуля",
                steps=[
                    "Админ открывает /funnels → «Новая воронка» (FunnelWizard).",
                    "Выбирает продукт, выбирает шаблон (welcome / sales / nurture).",
                    "Wizard создаёт воронку с 3-5 предзаполненными шагами.",
                    "Открывается Студия. Админ дорабатывает тексты в RichTextEditor.",
                    "Видит превью справа в реальном времени.",
                    "Меняет порядок шагов мышью.",
                    "Активирует воронку → она сразу начинает работать для новых юзеров.",
                ],
            ),
            Flow(
                name="Тестовый прогон воронки",
                steps=[
                    "Админ нажимает «Тестовый прогон».",
                    "Backend создаёт FunnelEntry с source=manual, user=admin.",
                    "ObservableTestPanel показывает SSE-стрим: что и когда отправилось.",
                    "Манульные FunnelEntry исключены из аналитики.",
                ],
            ),
        ],
        use_cases=[
            UseCase(
                name="UC-07.1. Правка активной воронки",
                actor="Admin",
                precondition="В воронке 250 активных entries.",
                steps=[
                    "Открывает шаг 3, меняет текст.",
                    "UI показывает warning: «Активных подписчиков: 250. Изменения затронут ~63 будущих сообщения».",
                    "Нажимает «Подтвердить и сохранить».",
                    "Auto-save срабатывает, изменения применяются к ещё не отправленным сообщениям.",
                ],
                result="Активная аудитория не страдает, админ принял осознанное решение.",
            ),
        ],
        tech=[
            "Drag-n-drop шагов", "execCommand insertText (undo-friendly)",
            "Безопасный HTML-whitelist (parse_mode=HTML)",
            "APScheduler worker 5 мин с batch=100",
            "SSE-стрим для test-панели",
        ],
        acceptance=[
            "Воронка из 5 шагов собирается за < 20 минут.",
            "В превью отображается ровно то, что увидит юзер в Telegram.",
            "Удаление шага не ломает уже запланированные сообщения других юзеров.",
            "Worker не отправит сообщение, если юзер успел отписаться или воронка отменена.",
        ],
        tasks=[
            Task("Backend: модели Funnel/FunnelStep/FunnelEntry/ScheduledMessage + миграции", backend=6, qa=3),
            Task("Backend: сервис FunnelsService (start_for_user, cancel_entry)", backend=10, qa=5),
            Task("Backend API /funnels (CRUD, reorder)", backend=6, qa=3),
            Task("Backend API /funnels/{id}/entries", backend=4, qa=2),
            Task("Backend: worker scheduled_messages (батч, шаблонизация, отмена)", backend=10, qa=6),
            Task("Backend: cancel_on_payment интеграция", backend=3, qa=2),
            Task("Frontend: Студия воронок — section 1 (параметры) с auto-save", frontend=8, qa=2),
            Task("Frontend: Студия — section 2 (шаги, drag-n-drop)", frontend=14, qa=3),
            Task("Frontend: Студия — section 3 (точки входа + EntryPointsSection)", frontend=10, qa=2),
            Task("Frontend: Студия — section 4 (запуск + warnings)", frontend=6, qa=2),
            Task("Frontend: компонент RichTextEditor (тулбар, хоткеи, undo)", frontend=14, qa=3),
            Task("Frontend: компонент TelegramPreview (HTML-whitelist, рендер)", frontend=10, qa=3),
            Task("Frontend: ObservableTestPanel + SSE", frontend=6, qa=2),
            Task("Frontend: SafetyWarning + ActiveFunnelConfirm", frontend=4, qa=2),
            Task("Frontend: ButtonsEditor", frontend=6, qa=2),
            Task("Frontend: FunnelWizard (4-шаговый диалог)", frontend=10, qa=2),
            Task("Дизайн: Студия — флагманский UX, 4 секции, превью, drag-n-drop", design=24),
            Task("Дизайн: UX-сценарии правки и тестирования", design=6),
        ],
        options=["standard", "premium"],
    ),

    # ─────────────────────────── M08 ───────────────────────────
    Module(
        id="M08",
        title="Лидмагниты",
        summary=(
            "Загрузка и доставка бесплатных материалов (PDF, видео, картинки, документы). "
            "Файлы хранятся на диске сервера, в момент первой отправки кэшируется "
            "Telegram file_id — последующие отправки идут без перезаливки."
        ),
        goals=[
            "Дать клиенту «получил ценность бесплатно» — повышает доверие.",
            "Не перезаливать один и тот же файл в Telegram 1000 раз.",
            "Контролировать, какой лидмагнит привязан к какому продукту.",
        ],
        fts=[
            "ФТ-08.1. Лидмагнит загружается multipart/form-data; backend сохраняет на диск с uuid-именем.",
            "ФТ-08.2. Backend автоматически определяет тип файла (pdf/image/video/document).",
            "ФТ-08.3. При первой отправке через бота сохраняется telegram_file_id, дальше — отправка по file_id.",
            "ФТ-08.4. UI имеет drag-n-drop upload с прогресс-баром и предпросмотром.",
            "ФТ-08.5. Лидмагнит привязывается к шагу воронки и идёт вместе с текстовым сообщением.",
            "ФТ-08.6. Удаление лидмагнита удаляет файл с диска и сбрасывает file_id.",
        ],
        flows=[
            Flow(
                name="Прикрепить лидмагнит к шагу воронки",
                steps=[
                    "Админ в Студии воронок нажимает «Добавить лидмагнит» в шаге.",
                    "Открывается QuickLeadMagnetUpload с drag-n-drop.",
                    "Перетаскивает PDF, видит прогресс заливки.",
                    "После завершения файл привязан к шагу.",
                    "В TelegramPreview появляется блок-attachment с иконкой и именем.",
                ],
            ),
        ],
        use_cases=[
            UseCase(
                name="UC-08.1. Кэширование file_id",
                actor="Worker scheduled_messages",
                precondition="Первый раз отправляет PDF юзеру.",
                steps=[
                    "Worker загружает файл в Telegram через sendDocument.",
                    "Получает file_id в ответе.",
                    "Сохраняет lead_magnet.telegram_file_id в БД.",
                    "Следующая отправка использует file_id — без чтения файла с диска.",
                ],
                result="Throughput воронки увеличивается в десятки раз.",
            ),
        ],
        tech=[
            "FastAPI File upload (multipart)", "Магнит на диске + uuid",
            "aiogram sendDocument/sendPhoto/sendVideo с file_id cache",
        ],
        acceptance=[
            "Файл < 50 МБ загружается за один запрос.",
            "Повторная отправка того же лидмагнита 1000 юзерам не упирается в I/O диска.",
            "Удалённый лидмагнит не присылается даже если он в активной воронке (graceful skip).",
        ],
        tasks=[
            Task("Backend: модель LeadMagnet + миграция", backend=2, qa=1),
            Task("Backend: сервис LeadMagnetsService (upload, send, type-detect)", backend=6, qa=3),
            Task("Backend API /lead-magnets (CRUD + upload)", backend=4, qa=2),
            Task("Frontend: /lead-magnets таблица", frontend=4, qa=2),
            Task("Frontend: QuickLeadMagnetUpload (drag-n-drop + прогресс)", frontend=8, qa=2),
            Task("Дизайн: drop-zone, preview, типы файлов", design=4),
        ],
        options=["standard", "premium"],
    ),

    # ─────────────────────────── M09 ───────────────────────────
    Module(
        id="M09",
        title="Точки входа: tracking-ссылки и кодовые слова",
        summary=(
            "Способы запустить воронку: deep-link с UTM-метками и/или кодовое слово в чате. "
            "Каждая ссылка считает клики, уникальных юзеров и автоматически приходит "
            "в аналитику. Кодовые слова уникальны на уровне БД (защита от race condition)."
        ),
        goals=[
            "Видеть, какой канал продвижения (Instagram, YouTube, Telegram-чат) приводит платящих.",
            "Отслеживать каждый рекламный пост отдельной ссылкой.",
            "Запускать воронку «без ссылки» — через короткое слово, удобное на эфирах и в подкастах.",
        ],
        fts=[
            "ФТ-09.1. Tracking-ссылка имеет уникальный slug (auto-gen 8 символов или custom 4-64).",
            "ФТ-09.2. К ссылке привязаны utm_source / medium / campaign / content.",
            "ФТ-09.3. Ссылка опционально привязана к воронке (запускается при /start с этим slug).",
            "ФТ-09.4. Бот считает click_count и unique_users (по telegram_user_id).",
            "ФТ-09.5. Slug проверяется на конфликт с product.code.",
            "ФТ-09.6. Кодовое слово — case-insensitive, уникальное на уровне БД через unique index.",
            "ФТ-09.7. Кодовое слово запускает привязанную воронку (если юзер не в ней уже).",
            "ФТ-09.8. В Студии воронок есть отдельная секция «Точки входа» с быстрым копированием ссылки и тостом.",
        ],
        flows=[
            Flow(
                name="Создание ссылки под Instagram Reels",
                steps=[
                    "Админ в Студии нажимает «Новая ссылка».",
                    "Вводит utm_source=instagram, utm_medium=reels.",
                    "Backend генерирует slug, возвращает полный URL.",
                    "Админ копирует ссылку, вставляет в bio Instagram.",
                    "Через неделю в /analytics видит, что Reels принесли 47 лидов и 12 оплат.",
                ],
            ),
        ],
        use_cases=[
            UseCase(
                name="UC-09.1. Конкурент админ создаёт то же слово",
                actor="Admin A & Admin B",
                precondition="Двое одновременно создают триггер «КЛУБ».",
                steps=[
                    "Admin A нажимает «Создать».",
                    "Admin B нажимает «Создать» в ту же секунду.",
                    "Первый коммит проходит, второй ловит ошибку UniqueViolation.",
                    "UI второму показывает: «Слово уже занято».",
                ],
                result="Дубликат невозможен ни при каком race.",
            ),
        ],
        tech=[
            "Auto-gen slug (8 символов alphanumeric)",
            "Postgres unique index on lower(word)",
            "Idempotent click_count / unique_users update",
        ],
        acceptance=[
            "Slug длиной 8 символов даёт ~218 трлн комбинаций — коллизии исключены.",
            "Создание триггера с занятым словом возвращает 409 за < 50 мс.",
            "Клик по ссылке в боте обновляет счётчик за один запрос.",
        ],
        tasks=[
            Task("Backend: модели TrackingLink + FunnelTrigger + миграции (unique index)", backend=4, qa=2),
            Task("Backend: сервис TrackingLinksService (slug-gen, collision-check)", backend=4, qa=3),
            Task("Backend: сервис FunnelTriggersService (case-insensitive)", backend=3, qa=2),
            Task("Backend API /tracking-links + /funnel-triggers", backend=6, qa=3),
            Task("Backend: интеграция click_count / unique_users в боте", backend=3, qa=2),
            Task("Frontend: блок «Точки входа» в Студии + копирование с тостом", frontend=8, qa=2),
            Task("Frontend: страница /funnel-triggers", frontend=4, qa=2),
            Task("Frontend: страница /products/[id] — ссылки на продукт", frontend=4, qa=2),
            Task("Дизайн: модалки создания ссылки, slug-preview", design=4),
        ],
        options=["standard", "premium"],
    ),

    # ─────────────────────────── M10 ───────────────────────────
    Module(
        id="M10",
        title="Аналитика и метрики",
        summary=(
            "Dashboard и страница /analytics: динамика лидов / оплат / выручки во времени с "
            "разрезом по источникам, кампаниям, продуктам; модели атрибуции last-touch / "
            "first-touch; Pareto-таблица топ-источников; пошаговая конверсия воронок; "
            "health-check данных с warnings («низкая атрибуция», «много failed-сообщений»)."
        ),
        goals=[
            "Видеть, какие каналы продвижения окупаются.",
            "Понимать, на каком шаге воронки люди отваливаются.",
            "Не принимать решения по «битым» данным — health-блок подсветит проблемы.",
        ],
        fts=[
            "ФТ-10.1. Dashboard / показывает 4 KPI и последние 5 заявок и платежей.",
            "ФТ-10.2. /analytics поддерживает периоды 7/30/90 дней.",
            "ФТ-10.3. Разрез по dimension: source / campaign / product / без разреза.",
            "ФТ-10.4. Атрибуция переключается last-touch ↔ first-touch.",
            "ФТ-10.5. Гранулярность time-series: день / неделя / месяц.",
            "ФТ-10.6. Stacked-area chart по выбранной метрике.",
            "ФТ-10.7. Pareto-таблица топ-N с CVR и выручкой.",
            "ФТ-10.8. Карточки воронок с их CVR (entered → paid).",
            "ФТ-10.9. /sources — детальный отчёт по UTM-источникам с конверсиями click→lead→payment.",
            "ФТ-10.10. Health-блок выводит warnings: «низкая атрибуция», «20%+ юзеров отключили уведомления», «много failed scheduled messages».",
            "ФТ-10.11. Тестовые прогоны (source=manual) автоматически исключены из расчётов.",
            "ФТ-10.12. Композитные индексы на (created_at, utm_source/tracking_link_id/product_id).",
        ],
        flows=[
            Flow(
                name="Поиск самого окупаемого канала",
                steps=[
                    "Открывает /analytics, ставит период «30 дней».",
                    "Меняет dimension на «По кампании», метрика — «Выручка».",
                    "Видит, что utm_campaign=spring_launch принёс 80% выручки.",
                    "Кликает на воронку из карточки — попадает в Студию для оптимизации.",
                ],
            ),
        ],
        use_cases=[
            UseCase(
                name="UC-10.1. Низкая атрибуция: данные дырявые",
                actor="Admin",
                precondition="60% лидов приходят без tracking_link_id.",
                steps=[
                    "Health-блок показывает warning: «Только 40% лидов имеют атрибуцию».",
                    "Кнопка «К продуктам» ведёт на /products создать ссылки.",
                ],
                result="Админ понимает, что аналитика не репрезентативна, и чинит источник.",
            ),
        ],
        tech=[
            "Recharts (stacked area + responsive)",
            "Postgres date_trunc + composite indexes",
            "SQL агрегация с DISTINCT в подзапросе (избегаем N+1)",
            "SWR dedupingInterval 60s",
        ],
        acceptance=[
            "Страница /analytics на 30 днях и 1000+ оплат отрисовывается за < 2 сек.",
            "При смене dimension/period график обновляется за < 1 сек (из кэша).",
            "Все цифры подписаны на русском (никаких CVR / Last-touch без перевода).",
        ],
        tasks=[
            Task("Backend: модель индексов под аналитику + миграция", backend=4, qa=2),
            Task("Backend: /stats/overview (10+ COUNT/SUM)", backend=4, qa=2),
            Task("Backend: /stats/health с warnings (8+ диагностик)", backend=6, qa=3),
            Task("Backend: /stats/timeline (date_trunc, last/first-touch, dimensions)", backend=10, qa=4),
            Task("Backend: /stats/funnels/summary (single-query JOIN, DISTINCT)", backend=6, qa=3),
            Task("Backend: /stats/funnels/{id}/conversion (per-step метрики)", backend=6, qa=3),
            Task("Backend: /sources (Pareto группировка)", backend=4, qa=2),
            Task("Frontend: Dashboard / (4 KPI + recent + sidebar badges)", frontend=8, qa=2),
            Task("Frontend: /analytics (фильтры, recharts, KPI, Pareto, funnels)", frontend=24, qa=4),
            Task("Frontend: /sources (таблица с конверсиями)", frontend=8, qa=2),
            Task("Frontend: Health-блок с warnings и actions", frontend=6, qa=2),
            Task("Frontend: a11y (aria-pressed, aria-live, aria-label на chart)", frontend=4, qa=2),
            Task("Дизайн: KPI карточки, графики, фильтры, таблицы", design=16),
        ],
        options=["standard", "premium"],
    ),

    # ─────────────────────────── M11 ───────────────────────────
    Module(
        id="M11",
        title="Telegram-бот (aiogram, multi-bot)",
        summary=(
            "Многоботный polling-менеджер: одновременно держит активными десятки ботов "
            "(каждый со своим токеном) в одном процессе. Хэндлеры команд (/start с deep-link, "
            "/my, /help), callback-обработка (карточки продуктов, заявки, отписка), резолв "
            "кодовых слов из чат-сообщений. First-touch и last-touch атрибуция."
        ),
        goals=[
            "Управлять любым количеством ботов из одной админки без правки кода.",
            "Гарантировать, что упавший бот не уронит остальные.",
            "Атрибутировать каждый touch — для аналитики и отчётности.",
        ],
        fts=[
            "ФТ-11.1. Менеджер ботов запускается на старте приложения, инициализирует все is_active боты.",
            "ФТ-11.2. Падение одного бота не аффектит остальные; менеджер пытается перезапустить упавшие при следующем sync.",
            "ФТ-11.3. /start с параметром резолвит сначала tracking_link.slug, затем product.code.",
            "ФТ-11.4. /start без параметра показывает каталог активных продуктов.",
            "ФТ-11.5. Callback prod:{id} показывает карточку продукта с ценами.",
            "ФТ-11.6. Callback lead:{id} создаёт Lead с last-touch атрибуцией.",
            "ФТ-11.7. Callback unsubscribe_notifications выключает рассылку для пользователя.",
            "ФТ-11.8. Текстовое сообщение (не команда) ищется в funnel_triggers; если совпадает — запускается воронка.",
            "ФТ-11.9. Все тексты бота вынесены в backend/app/bot/texts.py (русский).",
        ],
        flows=[
            Flow(
                name="/start с tracking-ссылкой",
                steps=[
                    "Юзер кликает t.me/bot?start=insta_reels_05.",
                    "Бот резолвит slug в TrackingLink, увеличивает click_count.",
                    "Если юзер новый — создаёт User, заполняет first_*.",
                    "Сохраняет current_tracking_link_id на 30 мин.",
                    "Если у ссылки есть funnel_id — запускает воронку.",
                    "Показывает карточку продукта (если ссылка привязана к product).",
                ],
            ),
        ],
        use_cases=[
            UseCase(
                name="UC-11.1. Бот упал из-за невалидного токена",
                actor="Bot manager",
                precondition="Один из ботов имеет отозванный токен.",
                steps=[
                    "Polling этого бота падает с TelegramAuthError.",
                    "Manager логирует, удаляет из реестра.",
                    "Остальные боты продолжают работать.",
                    "Админ заходит в /bots, видит ошибку, обновляет токен или деактивирует бота.",
                ],
                result="Один поломанный бот не аффектит остальные.",
            ),
        ],
        tech=[
            "aiogram 3.x", "asyncio.Task per bot",
            "Crash isolation через try/except в polling loop",
            "Static texts.py (RU)",
        ],
        acceptance=[
            "30+ ботов работают в одном процессе без деградации.",
            "Падение бота фиксируется в логах с указанием bot_id.",
            "Восстановление бота происходит не позднее следующего sync.",
        ],
        tasks=[
            Task("Backend: BotManager (start, sync, stop, crash-detect)", backend=10, qa=4),
            Task("Backend: command handlers (/start с deep-link, /help, /my)", backend=8, qa=4),
            Task("Backend: callback handlers (prod, lead, unsubscribe)", backend=6, qa=3),
            Task("Backend: текстовые сообщения → trigger lookup", backend=3, qa=2),
            Task("Backend: utility telegram.py (sendMessageSafe, invite, kick)", backend=4, qa=2),
            Task("Backend: тексты бота (RU)", backend=2),
            Task("Дизайн: тон голоса, эмодзи, кнопки в боте", design=4),
        ],
        options=["base", "standard", "premium"],
    ),

    # ─────────────────────────── M12 ───────────────────────────
    Module(
        id="M12",
        title="Админ-панель UI/UX (база)",
        summary=(
            "Дизайн-система и базовые компоненты: glassmorphism-стиль, индиго-розовый gradient, "
            "анимированный фон, навигация Sidebar v2 (7 групп с collapsible-состоянием и "
            "динамическими badge), breadcrumbs, библиотека UI-примитивов (Button / Input / "
            "Card / Sheet / Pill / Toast / Empty / TableWrap)."
        ),
        goals=[
            "Единый визуальный язык на всех экранах админки.",
            "Быстрый доступ ко всем разделам с подсветкой того, что требует внимания.",
            "Адаптивность от смартфона до 4K-монитора.",
        ],
        fts=[
            "ФТ-12.1. Sidebar разбит на 7 групп: Обзор / Аналитика / Продажи / Воронки / Каталог / Аудитория / Администрирование.",
            "ФТ-12.2. Группы collapsible; состояние сохраняется в localStorage.",
            "ФТ-12.3. На пунктах есть динамические badges: новые лиды, истекающие подписки, требующие настройки воронки.",
            "ФТ-12.4. Badge-данные обновляются по polling (60-120 сек).",
            "ФТ-12.5. Breadcrumbs строятся динамически из pathname с русскими названиями.",
            "ФТ-12.6. Глобальный Toast-провайдер: success/error/info, auto-dismiss 2.4 сек.",
            "ФТ-12.7. Glass-стиль: rgba(255,255,255,0.65) + backdrop-blur(14px).",
            "ФТ-12.8. Mobile: sidebar скрывается, открывается по бургеру.",
            "ФТ-12.9. UI-компоненты типизированы и покрыты unit-тестами.",
        ],
        flows=[
            Flow(
                name="Перемещение между разделами",
                steps=[
                    "Юзер видит в sidebar «Заявки 12» с amber-плашкой.",
                    "Кликает.",
                    "Breadcrumbs обновляются: Обзор / Заявки.",
                    "После работы клик «Воронки» — breadcrumbs обновляются.",
                ],
            ),
        ],
        use_cases=[
            UseCase(
                name="UC-12.1. Узкое окно браузера",
                actor="Manager",
                precondition="Работает на ноутбуке с шириной экрана 1280px.",
                steps=[
                    "Открывает /analytics.",
                    "Sidebar остаётся в режиме «icons + labels».",
                    "Таблица Pareto имеет горизонтальный скролл.",
                ],
                result="Все экраны работают без horizontal page-scroll.",
            ),
        ],
        tech=[
            "TailwindCSS + custom glass utilities", "React Context (Toast)",
            "localStorage для collapsible state", "SWR polling для badge",
        ],
        acceptance=[
            "Все 21 страница админки используют единый sidebar и breadcrumbs.",
            "Toast корректно стекируется при 5+ одновременных вызовах.",
            "Все UI-компоненты покрыты unit-тестами.",
        ],
        tasks=[
            Task("Frontend: UI-библиотека (Button/Input/Select/Field/Card/Sheet/Pill/Empty/Table)", frontend=14, qa=4),
            Task("Frontend: Sidebar v2 (группы, collapsible, badges, mobile)", frontend=14, qa=3),
            Task("Frontend: Breadcrumbs с динамической мапой названий", frontend=4, qa=1),
            Task("Frontend: ToastProvider (Context, auto-dismiss, aria-live)", frontend=4, qa=2),
            Task("Frontend: globals.css (glass utilities, animations, blob-фон)", frontend=6),
            Task("Frontend: Mobile-адаптация (бургер, sticky sidebar, breakpoints)", frontend=6, qa=2),
            Task("Дизайн: дизайн-система (цвета, шрифты, тени, отступы, иконки)", design=14),
            Task("Дизайн: Sidebar v2 (структура групп, badge-логика)", design=6),
            Task("Дизайн: glass-стиль, gradients, micro-animations", design=8),
        ],
        options=["base", "standard", "premium"],
    ),

    # ─────────────────────────── M13 ───────────────────────────
    Module(
        id="M13",
        title="Брендинг и SEO",
        summary=(
            "Айдентика проекта: логотип в виде виниловой пластинки, фавикон SVG, apple-icon, "
            "OpenGraph-картинка для шаринга в чатах, PWA-манифест, robots.txt с Disallow "
            "(админка — закрытая, индексация поисковиками не нужна). Расширенные мета-теги."
        ),
        goals=[
            "Узнаваемый бренд во всех точках касания (вкладка, домашний экран, превью ссылки).",
            "Корректное закрытие от поисковых систем.",
            "Возможность добавить админку на главный экран как PWA.",
        ],
        fts=[
            "ФТ-13.1. Фавикон SVG (виниловая пластинка, indigo→rose gradient) — масштабируется без потери чёткости.",
            "ФТ-13.2. apple-icon 180×180 генерируется динамически через next/og.",
            "ФТ-13.3. OG-картинка 1200×630 с большим лого и слоганом.",
            "ФТ-13.4. PWA manifest позволяет добавить иконку на главный экран iOS/Android.",
            "ФТ-13.5. robots.txt с Disallow: / — закрытая админка.",
            "ФТ-13.6. Title template '%s · Grammy' для подстраниц.",
            "ФТ-13.7. OpenGraph + Twitter cards для шаринга в чатах команды.",
            "ФТ-13.8. theme-color раздельно для light и dark prefers-color-scheme.",
            "ФТ-13.9. metadataBase из NEXT_PUBLIC_SITE_URL для корректных absolute URL.",
            "ФТ-13.10. Логотип-винил в Sidebar и Login — консистентен с фавиконом.",
        ],
        flows=[
            Flow(
                name="Поделиться ссылкой на админку в чате",
                steps=[
                    "Сотрудник вставляет grammy.mediann.dev в чат команды.",
                    "Telegram/Slack автоматически генерирует превью с OG-картинкой и описанием.",
                    "Коллеги видят бренд, заголовок и краткое описание.",
                ],
            ),
        ],
        use_cases=[
            UseCase(
                name="UC-13.1. Поисковик индексирует админку",
                actor="Поисковый бот",
                precondition="Стандартное поведение поисковика.",
                steps=[
                    "Гуглбот заходит на grammy.mediann.dev/robots.txt.",
                    "Видит Disallow: /.",
                    "Не индексирует ни одну страницу.",
                ],
                result="Закрытые URL не попадают в выдачу.",
            ),
        ],
        tech=[
            "Next.js file-based metadata (app/icon.svg, app/apple-icon.tsx, app/opengraph-image.tsx)",
            "next/og ImageResponse (динамическая генерация PNG)",
            "app/manifest.ts, app/robots.ts",
        ],
        acceptance=[
            "Фавикон корректно отображается в Chrome / Safari / Firefox / iOS.",
            "Превью в Telegram/Slack показывает OG-картинку.",
            "robots.txt запрещает индексацию всем user-agents.",
        ],
        tasks=[
            Task("Frontend: app/icon.svg (виниловая пластинка)", frontend=2),
            Task("Frontend: app/apple-icon.tsx (next/og)", frontend=2),
            Task("Frontend: app/opengraph-image.tsx (winyl + wordmark)", frontend=3),
            Task("Frontend: app/manifest.ts + app/robots.ts", frontend=1),
            Task("Frontend: расширенные metadata + viewport в layout", frontend=2, qa=1),
            Task("Frontend: лого в Sidebar и Login (мини-винил)", frontend=2),
            Task("Дизайн: brand identity (логотип-винил, типографика, цвета)", design=8),
            Task("Дизайн: OG-композиция", design=2),
        ],
        options=["base", "standard", "premium"],
    ),

    # ─────────────────────────── M14 ───────────────────────────
    Module(
        id="M14",
        title="Аудит-журнал",
        summary=(
            "Запись каждого действия администратора в админке (создание / изменение / удаление "
            "ресурсов) с маскированием секретов в payload. Просмотр журнала с фильтрами по "
            "админу, действию, типу ресурса. Доступ только у роли admin."
        ),
        goals=[
            "Иметь полную трассу действий для разбора инцидентов и compliance.",
            "Не утечь пароли и токены в логи (маскирование).",
            "Дать руководителю возможность видеть, что делают менеджеры.",
        ],
        fts=[
            "ФТ-14.1. Каждое write-действие админки логируется в audit_log.",
            "ФТ-14.2. Поля: admin_id, action, resource_type, resource_id, method, path, ip, user_agent, payload.",
            "ФТ-14.3. В payload поля password/token/secret заменяются на '***'.",
            "ФТ-14.4. Запись делается через сервис log_action (вызов из API-эндпоинтов).",
            "ФТ-14.5. Страница /audit-log доступна только роли admin.",
            "ФТ-14.6. Фильтры: admin_id, action (create/update/delete), resource_type.",
            "ФТ-14.7. Сортировка по убыванию created_at.",
            "ФТ-14.8. Просмотр payload в раскрывающемся блоке.",
        ],
        flows=[
            Flow(
                name="Разбор: кто удалил продукт",
                steps=[
                    "Админ открывает /audit-log.",
                    "Ставит фильтр resource_type=product, action=delete.",
                    "Видит: Manager Иван удалил product#42 вчера в 15:32.",
                    "Раскрывает payload — видит ip, user-agent.",
                ],
            ),
        ],
        use_cases=[
            UseCase(
                name="UC-14.1. Утечка пароля заблокирована",
                actor="System",
                precondition="Админ сменил пароль (POST /api/admin/password).",
                steps=[
                    "Endpoint вызывает log_action с payload {old_password, new_password}.",
                    "Audit-сервис _scrub маскирует оба поля.",
                    "В audit_log записывается {old_password: '***', new_password: '***'}.",
                ],
                result="Секреты не утекают в журнал.",
            ),
        ],
        tech=[
            "SQLAlchemy AuditLog model", "JSONB payload",
            "_scrub regex по ключам (password|token|secret|api_key)",
        ],
        acceptance=[
            "100% write-эндпоинтов API логируются.",
            "Никаких секретов в payload (verified тестом, который пытается их найти регексом).",
            "Страница /audit-log грузит 1000 записей за < 500 мс.",
        ],
        tasks=[
            Task("Backend: модель AuditLog + миграция + индексы", backend=3, qa=2),
            Task("Backend: сервис log_action + _scrub", backend=4, qa=3),
            Task("Backend: интеграция log_action во все write-эндпоинты", backend=6, qa=3),
            Task("Backend API /audit-log с фильтрами", backend=3, qa=2),
            Task("Frontend: /audit-log таблица с фильтрами", frontend=8, qa=2),
            Task("Дизайн: журнал с раскрывающимся payload", design=4),
        ],
        options=["premium"],
    ),

    # ─────────────────────────── M15 ───────────────────────────
    Module(
        id="M15",
        title="Observability и алерты",
        summary=(
            "Prometheus метрики из backend (RPS, latency, in-flight, бизнес-метрики), Loki + "
            "Promtail для логов (с retention 7 дней), Grafana с дашбордом, Alertmanager с "
            "правилами (BackendDown / HighErrorRate / HighLatencyP95 / TooManyInFlight), "
            "structlog в JSON с request_id и маскированием секретов, опциональная интеграция "
            "Sentry для ошибок и performance traces."
        ),
        goals=[
            "Заранее знать о проблемах (упал ли бэкенд, лезет ли latency).",
            "Иметь возможность быстро найти конкретный запрос в логах по request_id.",
            "Не пропускать ошибки в продакшене (Sentry).",
        ],
        fts=[
            "ФТ-15.1. /metrics endpoint выдаёт Prometheus-формат: http_requests_total, http_request_duration_seconds, http_requests_in_flight, bot_polling_status, subscription_active_total, payment_total, lead_total.",
            "ФТ-15.2. Loki хранит логи 7 дней, Prometheus — 30 дней.",
            "ФТ-15.3. Promtail парсит docker-логи и файловые JSON-логи.",
            "ФТ-15.4. Grafana дашборд «Infobizbot — Backend Overview»: RPS, p95 latency, active subscriptions.",
            "ФТ-15.5. Alertmanager: BackendDown (critical, 1m), HighErrorRate>5% (warning, 5m), HighLatencyP95>1s, TooManyInFlight>50.",
            "ФТ-15.6. Inhibition rule: при BackendDown остальные алерты подавляются.",
            "ФТ-15.7. structlog: JSON в stdout, request_id из middleware, маскирование password/token.",
            "ФТ-15.8. Path normalization для метрик: /users/42 → /users/:id (контроль кардинальности).",
            "ФТ-15.9. Sentry init опциональный (если SENTRY_DSN), traces_sample_rate=0.1.",
        ],
        flows=[
            Flow(
                name="Расследование 5xx-ошибки",
                steps=[
                    "Alertmanager уведомил о HighErrorRate в Grafana UI.",
                    "Инженер открывает Grafana, видит всплеск 500 за последние 10 мин.",
                    "Берёт request_id из метки.",
                    "Идёт в Loki, фильтрует {service=\"backend\"} | json | request_id=\"XYZ\".",
                    "Видит трейс, понимает причину.",
                    "Если Sentry включён — там готовый стек.",
                ],
            ),
        ],
        use_cases=[
            UseCase(
                name="UC-15.1. Бэкенд лежит — администратор узнаёт первым",
                actor="System",
                precondition="Backend упал из-за OOM.",
                steps=[
                    "Prometheus не получает /metrics 1 минуту.",
                    "Alert BackendDown срабатывает (critical).",
                    "Alertmanager шлёт в Grafana AlertManager UI.",
                    "Инженер видит alert, начинает разбор.",
                ],
                result="Mean time to detection < 1 минуты.",
            ),
        ],
        tech=[
            "Prometheus + Alertmanager + Loki + Promtail + Grafana",
            "prometheus-client (FastAPI middleware)",
            "structlog (JSON, contextvars, secret-mask)",
            "Sentry SDK с FastApiIntegration / SqlalchemyIntegration",
        ],
        acceptance=[
            "При выключении backend alert приходит в течение 1 минуты.",
            "Любой запрос можно найти в Loki по request_id.",
            "В логах нет паролей и токенов (regression-тест с пыткой их вставить).",
        ],
        tasks=[
            Task("DevOps: prometheus.yml + scrape backend + retention 30d", devops=3, qa=1),
            Task("DevOps: loki + promtail (docker_sd_configs, JSON pipeline, 7d)", devops=4, qa=1),
            Task("DevOps: alertmanager + 5 alert rules + inhibit", devops=4, qa=2),
            Task("DevOps: grafana с автопровижионом datasources + dashboard JSON", devops=4, qa=1),
            Task("Backend: prometheus-client middleware (counter/histogram/gauge)", backend=4, qa=2),
            Task("Backend: structlog setup (JSON, contextvars, mask)", backend=3, qa=2),
            Task("Backend: RequestContextMiddleware (request_id, latency)", backend=3, qa=2),
            Task("Backend: Sentry init (опционально)", backend=2, qa=1),
            Task("Дизайн: layout dashboard в Grafana (если нужен кастом)", design=4),
        ],
        options=["standard", "premium"],
    ),

    # ─────────────────────────── M16 ───────────────────────────
    Module(
        id="M16",
        title="QA: тесты и CI/CD",
        summary=(
            "Глубокое покрытие тестами: backend (~470 unit/integration с реальным Postgres через "
            "testcontainers), frontend (~28 unit с MSW), e2e (Playwright, 6 spec'ов с global setup "
            "и переиспользованием cookie). GitHub Actions с пятью параллельными jobs, pre-commit "
            "хуки (ruff, gitleaks, ...). Soft-fail Trivy security scan."
        ),
        goals=[
            "Не выкатывать сломанное в продакшен.",
            "Делать рефакторинги без страха (миграция версии — пройдёт тесты или нет).",
            "Иметь зеркало production-инфры в тестах (реальный Postgres, не mock).",
        ],
        fts=[
            "ФТ-16.1. Backend unit/integration: pytest + testcontainers (PostgresContainer session-scope).",
            "ФТ-16.2. Фабрики моделей (make / make_committed) для 16+ сущностей.",
            "ФТ-16.3. mock_telegram_ok fixture для перехвата Telegram API вызовов.",
            "ФТ-16.4. Frontend: vitest + MSW + happy-dom; setupServer с onUnhandledRequest='error'.",
            "ФТ-16.5. E2E: Playwright + Chromium, global setup с переиспользованием cookie.",
            "ФТ-16.6. GitHub Actions: backend-lint (ruff + bandit + pip-audit), backend-test, frontend-lint, frontend-test, security (Trivy).",
            "ФТ-16.7. Concurrency с cancel-in-progress, кэш pip/npm.",
            "ФТ-16.8. Pre-commit: ruff format/check, gitleaks, check-merge-conflict, check-yaml/toml, end-of-file-fixer.",
            "ФТ-16.9. Coverage в Codecov (backend + frontend), отдельные флаги.",
        ],
        flows=[
            Flow(
                name="Pull request пайплайн",
                steps=[
                    "Разработчик открывает PR.",
                    "GitHub Actions запускает 5 jobs параллельно.",
                    "Backend-test разворачивает Postgres в контейнере, прогоняет 470+ тестов параллельно (-n 2).",
                    "Frontend-test прогоняет 28 vitest + загружает coverage.",
                    "Trivy сканирует на уязвимости (soft-fail).",
                    "Reviewer мерджит, если зелёное.",
                ],
            ),
        ],
        use_cases=[
            UseCase(
                name="UC-16.1. Регрессия после рефакторинга",
                actor="Developer",
                precondition="Разработчик меняет логику атрибуции.",
                steps=[
                    "Локально запускает pytest.",
                    "Падают 3 теста: ленты атрибуции last-touch.",
                    "Чинит логику, тесты зеленеют.",
                    "Открывает PR — CI зелёный.",
                ],
                result="Регрессия пойман до продакшена.",
            ),
        ],
        tech=[
            "pytest + testcontainers + httpx AsyncClient",
            "vitest + MSW + happy-dom",
            "Playwright (chromium, global setup)",
            "GitHub Actions, Codecov, Trivy, Gitleaks",
        ],
        acceptance=[
            "Покрытие backend > 80% (line coverage).",
            "Покрытие критичных компонентов фронта (UI-библиотека) — 100%.",
            "E2E прогон проходит за < 5 минут.",
            "Pre-commit отлавливает секреты до коммита.",
        ],
        tasks=[
            Task("Backend: conftest.py + testcontainers + фабрики + savepoints", devops=10, qa=24),
            Task("Backend: написание ~470 тестов (API + services + bot + workers)", qa=48),
            Task("Frontend: setup vitest + MSW + handlers + setupServer", devops=4, qa=4),
            Task("Frontend: написание ~28 тестов (компоненты + страницы)", qa=20),
            Task("E2E: Playwright config + global setup + 6 spec'ов", devops=4, qa=16),
            Task("CI: 5 jobs в GitHub Actions + Codecov + кэш", devops=8, qa=2),
            Task("Pre-commit: 8 хуков, конфигурация", devops=3, qa=1),
            Task("Security: Trivy scan + gitleaks (soft-fail)", devops=3, qa=1),
        ],
        options=["premium"],
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# Пакеты комплектации
# ─────────────────────────────────────────────────────────────────────────────

PACKAGES = [
    ("base", "Базовый (MVP)",
     "Минимально жизнеспособный продукт: можно подключить ботов и каналы, "
     "продавать продукты, обрабатывать заявки и платежи вручную, выдавать доступ. "
     "Без воронок, без полноценной аналитики, без observability."),
    ("standard", "Стандарт",
     "Базовый + автоматизация и аналитика: воронки прогрева, tracking-ссылки и UTM, "
     "лидмагниты, страница аналитики с фильтрами и графиками, наблюдаемость с алертами. "
     "Готовый production-инструмент инфобиз-команды."),
    ("premium", "Премиум",
     "Стандарт + полноценный compliance и QA: журнал действий с маскированием секретов, "
     "полное покрытие тестами (backend ~470, frontend ~28, e2e 6), CI/CD с 5 jobs, "
     "pre-commit, security-сканирование."),
]


# ─────────────────────────────────────────────────────────────────────────────
# DOCX генератор
# ─────────────────────────────────────────────────────────────────────────────

def _set_paragraph_style(p, *, size=11, bold=False, color=None, after_pt=4):
    p.paragraph_format.space_after = Pt(after_pt)
    for run in p.runs:
        run.font.size = Pt(size)
        run.bold = bold
        if color:
            run.font.color.rgb = color


def _add_bookmark(paragraph, name):
    """Добавляет именованный bookmark в параграф — для перекрёстных ссылок."""
    run = paragraph.runs[0] if paragraph.runs else paragraph.add_run()
    start = OxmlElement("w:bookmarkStart")
    start.set(qn("w:id"), str(abs(hash(name)) % 10_000))
    start.set(qn("w:name"), name)
    end = OxmlElement("w:bookmarkEnd")
    end.set(qn("w:id"), start.get(qn("w:id")))
    run._r.addprevious(start)
    run._r.addnext(end)


def _add_horizontal_rule(doc):
    p = doc.add_paragraph()
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:color"), "C0C0C0")
    pBdr.append(bottom)
    pPr.append(pBdr)


def _add_table(doc, headers, rows, col_widths_cm=None):
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = "Light Grid Accent 1"
    hdr = table.rows[0].cells
    for i, h in enumerate(headers):
        hdr[i].text = h
        for p in hdr[i].paragraphs:
            for r in p.runs:
                r.bold = True
                r.font.size = Pt(10)
    for r_idx, row in enumerate(rows, start=1):
        for c_idx, val in enumerate(row):
            cell = table.rows[r_idx].cells[c_idx]
            cell.text = str(val)
            for p in cell.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(10)
    if col_widths_cm:
        for col_idx, width in enumerate(col_widths_cm):
            for row in table.rows:
                row.cells[col_idx].width = Cm(width)
    return table


def generate_docx() -> Path:
    doc = Document()

    # Базовая нормализация стиля Normal
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    # ── Титул ─────────────────────────────────────────────
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = title.add_run(f"Техническое задание\n«{PROJECT_NAME}»")
    r.font.size = Pt(28)
    r.bold = True
    r.font.color.rgb = RGBColor(0x1E, 0x1B, 0x4B)

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = sub.add_run(PROJECT_TAGLINE)
    r.font.size = Pt(13)
    r.font.color.rgb = RGBColor(0x6B, 0x72, 0x80)

    doc.add_paragraph()

    info = doc.add_paragraph()
    info.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = info.add_run("Модульная структура · 16 модулей · Гибкая комплектация")
    r.italic = True
    r.font.size = Pt(11)
    r.font.color.rgb = RGBColor(0x6B, 0x72, 0x80)

    doc.add_page_break()

    # ── Раздел: Общее описание ─────────────────────────────
    h = doc.add_heading("1. Общее описание", level=1)
    doc.add_paragraph(
        "Grammy — программный продукт для запуска и сопровождения продаж доступа в закрытые "
        "Telegram-каналы. Состоит из административной панели (Next.js), backend-API "
        "(FastAPI), Telegram-бота (aiogram, мультибот) и стека наблюдаемости "
        "(Prometheus + Grafana + Loki + Alertmanager)."
    )
    doc.add_paragraph(
        "Документ собран как набор независимых модулей. Каждый модуль самодостаточен, "
        "имеет свои функциональные требования, пользовательские сценарии, технологический "
        "стек и оценку трудозатрат. Это даёт возможность гибкой комплектации поставки: "
        "от MVP до Premium."
    )

    # Архитектура
    doc.add_heading("Архитектура и стек", level=2)
    _add_table(
        doc,
        ["Слой", "Технологии"],
        [
            ("Frontend", "Next.js 15, React 19, TailwindCSS, SWR, Recharts, Vitest"),
            ("Backend", "Python 3.12, FastAPI, SQLAlchemy 2.0 async, Alembic, structlog"),
            ("База данных", "PostgreSQL 16 (с композитными аналитическими индексами)"),
            ("Telegram", "aiogram 3.x (мультибот polling), Telegram Payments"),
            ("Workers", "APScheduler (expire_due, scheduled_messages)"),
            ("Observability", "Prometheus, Grafana, Loki, Promtail, Alertmanager, Sentry (опц.)"),
            ("Инфраструктура", "Docker Compose, Nginx, Let's Encrypt (certbot)"),
            ("CI/CD", "GitHub Actions, Codecov, Trivy, Gitleaks"),
            ("Тесты", "pytest + testcontainers, vitest + MSW, Playwright"),
        ],
        col_widths_cm=[4, 13],
    )

    # Сводная таблица модулей
    doc.add_heading("Состав модулей", level=2)
    rows = []
    for m in MODULES:
        rows.append((m.id, m.title, f"{m.total_hours} ч", ", ".join(m.options)))
    _add_table(
        doc,
        ["ID", "Модуль", "Трудозатраты", "Пакеты"],
        rows,
        col_widths_cm=[1.5, 9, 2.5, 4],
    )

    # Пакеты комплектации
    doc.add_heading("Пакеты комплектации", level=2)
    for code, name, desc in PACKAGES:
        included = [m for m in MODULES if code in m.options]
        total_hours = sum(m.total_hours for m in included)
        cost = total_hours * HOURLY_RATE

        pname = doc.add_paragraph()
        r = pname.add_run(f"{name}")
        r.bold = True
        r.font.size = Pt(13)
        r.font.color.rgb = RGBColor(0x4F, 0x46, 0xE5)

        doc.add_paragraph(desc)

        info_p = doc.add_paragraph()
        info_p.add_run(f"Состав: ").bold = True
        info_p.add_run(", ".join(m.id for m in included))
        info_p.add_run(f"\nИтого: ").bold = True
        info_p.add_run(f"{total_hours} ч × {HOURLY_RATE:,} ₽ = {cost:,} ₽".replace(",", " "))
        doc.add_paragraph()

    doc.add_page_break()

    # ── Модули ─────────────────────────────────────────────
    for idx, m in enumerate(MODULES, start=1):
        h = doc.add_heading(f"2.{idx}. {m.id}. {m.title}", level=1)
        _add_bookmark(h, f"module_{m.id}")

        doc.add_paragraph(m.summary)

        # Цели
        doc.add_heading("Бизнес-цели", level=2)
        for g in m.goals:
            doc.add_paragraph(g, style="List Bullet")

        # ФТ
        doc.add_heading("Функциональные требования", level=2)
        for ft in m.fts:
            doc.add_paragraph(ft, style="List Number")

        # Flows
        doc.add_heading("Пользовательские сценарии (User Flow)", level=2)
        for f in m.flows:
            p = doc.add_paragraph()
            r = p.add_run(f.name)
            r.bold = True
            for step in f.steps:
                doc.add_paragraph(step, style="List Number")

        # Use cases
        doc.add_heading("Варианты использования (Use Cases)", level=2)
        for uc in m.use_cases:
            p = doc.add_paragraph()
            r = p.add_run(uc.name)
            r.bold = True

            r2 = doc.add_paragraph().add_run("Актор: ")
            r2.bold = True
            r2.font.size = Pt(10)
            doc.paragraphs[-1].add_run(uc.actor).font.size = Pt(10)

            r3 = doc.add_paragraph().add_run("Предусловие: ")
            r3.bold = True
            r3.font.size = Pt(10)
            doc.paragraphs[-1].add_run(uc.precondition).font.size = Pt(10)

            r4 = doc.add_paragraph().add_run("Основной поток:")
            r4.bold = True
            r4.font.size = Pt(10)
            for s in uc.steps:
                doc.add_paragraph(s, style="List Number")

            r5 = doc.add_paragraph().add_run("Результат: ")
            r5.bold = True
            r5.font.size = Pt(10)
            doc.paragraphs[-1].add_run(uc.result).font.size = Pt(10)

        # Tech
        doc.add_heading("Технологии", level=2)
        doc.add_paragraph(", ".join(m.tech))

        # Acceptance
        doc.add_heading("Критерии приёмки", level=2)
        for a in m.acceptance:
            doc.add_paragraph(a, style="List Bullet")

        # Трудозатраты
        doc.add_heading("Трудозатраты", level=2)
        rows = [(t.name, t.backend or "—", t.frontend or "—", t.design or "—",
                 t.devops or "—", t.qa or "—", t.total) for t in m.tasks]
        rows.append(("ИТОГО", m.sum_backend, m.sum_frontend, m.sum_design,
                     m.sum_devops, m.sum_qa, m.total_hours))
        _add_table(
            doc,
            ["Задача", "Backend", "Frontend", "Design", "DevOps", "QA", "Всего"],
            rows,
            col_widths_cm=[7.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5],
        )

        cost = m.total_hours * HOURLY_RATE
        p = doc.add_paragraph()
        r = p.add_run(f"Стоимость модуля: {cost:,} ₽".replace(",", " "))
        r.bold = True
        r.font.size = Pt(12)

        _add_horizontal_rule(doc)

    # ── Условия и порядок работ ─────────────────────────────
    doc.add_page_break()
    doc.add_heading("3. Условия и порядок работ", level=1)
    doc.add_paragraph(
        "1. Работы ведутся итерационно, поэтапно по модулям. Каждый модуль завершается "
        "приёмочным тестированием по критериям из соответствующего раздела."
    )
    doc.add_paragraph(
        "2. Заказчик предоставляет: токены ботов, доступ к закрытым Telegram-каналам, "
        "доменное имя для админ-панели, реквизиты для Telegram Payments (если входит в пакет)."
    )
    doc.add_paragraph(
        "3. Исполнитель предоставляет: разработанный исходный код, документацию, "
        "развёртывание на серверах Заказчика, передачу знаний по эксплуатации."
    )
    doc.add_paragraph(
        "4. Указанные трудозатраты — рабочие часы команды (разработка + дизайн + QA + DevOps). "
        f"Часовая ставка: {HOURLY_RATE:,} ₽. Конкретный график оплат фиксируется договором.".replace(",", " ")
    )
    doc.add_paragraph(
        "5. Сроки реализации модулей определяются исходя из выбранного пакета и зависимостей "
        "между модулями (например, M07 «Воронки» опирается на M11 «Telegram-бот»)."
    )

    doc.save(DOCX_PATH)
    return DOCX_PATH


# ─────────────────────────────────────────────────────────────────────────────
# XLSX генератор
# ─────────────────────────────────────────────────────────────────────────────

THIN = Side(style="thin", color="C0C0C0")
BORDER = Border(top=THIN, bottom=THIN, left=THIN, right=THIN)
HEADER_FILL = PatternFill("solid", fgColor="1E1B4B")
SUBHEADER_FILL = PatternFill("solid", fgColor="EEF2FF")
TOTAL_FILL = PatternFill("solid", fgColor="FEF3C7")
GRAND_TOTAL_FILL = PatternFill("solid", fgColor="6366F1")


def _style_header(cell, *, white=True):
    cell.font = Font(bold=True, color="FFFFFF" if white else "1E1B4B", size=11)
    cell.fill = HEADER_FILL if white else SUBHEADER_FILL
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell.border = BORDER


def _style_cell(cell, *, bold=False, align="left"):
    cell.font = Font(bold=bold, size=10)
    cell.alignment = Alignment(horizontal=align, vertical="center", wrap_text=True)
    cell.border = BORDER


def generate_xlsx() -> Path:
    wb = Workbook()

    # ── Лист 1: Параметры ─────────────────────────────────
    ws_params = wb.active
    ws_params.title = "Параметры"
    ws_params["A1"] = "Параметр"
    ws_params["B1"] = "Значение"
    _style_header(ws_params["A1"])
    _style_header(ws_params["B1"])

    ws_params["A2"] = "Часовая ставка (₽)"
    ws_params["B2"] = HOURLY_RATE
    _style_cell(ws_params["A2"], bold=True)
    _style_cell(ws_params["B2"], align="right")
    ws_params["B2"].number_format = "#,##0 ₽"

    ws_params["A3"] = "Проект"
    ws_params["B3"] = PROJECT_NAME
    _style_cell(ws_params["A3"], bold=True)
    _style_cell(ws_params["B3"])

    ws_params["A4"] = "Описание"
    ws_params["B4"] = PROJECT_TAGLINE
    _style_cell(ws_params["A4"], bold=True)
    _style_cell(ws_params["B4"])

    ws_params.column_dimensions["A"].width = 28
    ws_params.column_dimensions["B"].width = 60

    ws_params["A6"] = "Изменение ставки в B2 автоматически пересчитает все стоимости на других листах."
    ws_params["A6"].font = Font(italic=True, size=9, color="6B7280")
    ws_params.merge_cells("A6:B6")

    RATE_REF = "Параметры!$B$2"

    # ── Лист 2: Сводная ───────────────────────────────────
    ws_summary = wb.create_sheet("Сводная")
    headers = ["ID", "Модуль", "Backend", "Frontend", "Design", "DevOps", "QA", "Всего, ч", "Стоимость, ₽", "Пакеты"]
    for col, h in enumerate(headers, start=1):
        cell = ws_summary.cell(row=1, column=col, value=h)
        _style_header(cell)

    row = 2
    for m in MODULES:
        ws_summary.cell(row=row, column=1, value=m.id)
        ws_summary.cell(row=row, column=2, value=m.title)
        ws_summary.cell(row=row, column=3, value=m.sum_backend)
        ws_summary.cell(row=row, column=4, value=m.sum_frontend)
        ws_summary.cell(row=row, column=5, value=m.sum_design)
        ws_summary.cell(row=row, column=6, value=m.sum_devops)
        ws_summary.cell(row=row, column=7, value=m.sum_qa)
        ws_summary.cell(row=row, column=8, value=m.total_hours)
        cell_cost = ws_summary.cell(row=row, column=9, value=f"=H{row}*{RATE_REF}")
        cell_cost.number_format = "#,##0 ₽"
        ws_summary.cell(row=row, column=10, value=", ".join(m.options))

        for col in range(1, 11):
            c = ws_summary.cell(row=row, column=col)
            _style_cell(c, align="right" if 3 <= col <= 9 else "left")
        ws_summary.cell(row=row, column=1).font = Font(bold=True, size=10)
        row += 1

    # Итого
    total_row = row
    ws_summary.cell(row=total_row, column=1, value="ИТОГО")
    ws_summary.cell(row=total_row, column=2, value="Все модули (полная комплектация)")
    for col in range(3, 9):
        letter = get_column_letter(col)
        ws_summary.cell(row=total_row, column=col, value=f"=SUM({letter}2:{letter}{total_row-1})")
    ws_summary.cell(row=total_row, column=9, value=f"=H{total_row}*{RATE_REF}")
    ws_summary.cell(row=total_row, column=9).number_format = "#,##0 ₽"

    for col in range(1, 11):
        c = ws_summary.cell(row=total_row, column=col)
        c.font = Font(bold=True, size=11, color="1E1B4B")
        c.fill = TOTAL_FILL
        c.alignment = Alignment(horizontal="right" if 3 <= col <= 9 else "left", vertical="center")
        c.border = BORDER

    widths = [6, 32, 9, 9, 9, 9, 9, 11, 16, 22]
    for i, w in enumerate(widths, start=1):
        ws_summary.column_dimensions[get_column_letter(i)].width = w

    ws_summary.freeze_panes = "A2"

    # ── Лист 3: Детализация ───────────────────────────────
    ws_detail = wb.create_sheet("Детализация")
    headers = ["Модуль ТЗ", "Задача", "Backend", "Frontend", "Design", "DevOps", "QA", "Всего, ч", "Стоимость, ₽"]
    for col, h in enumerate(headers, start=1):
        cell = ws_detail.cell(row=1, column=col, value=h)
        _style_header(cell)

    row = 2
    for m in MODULES:
        # Подзаголовок модуля
        sub_cell = ws_detail.cell(row=row, column=1, value=f"{m.id}. {m.title}")
        ws_detail.merge_cells(start_row=row, end_row=row, start_column=1, end_column=9)
        sub_cell.font = Font(bold=True, size=11, color="1E1B4B")
        sub_cell.fill = SUBHEADER_FILL
        sub_cell.alignment = Alignment(horizontal="left", vertical="center")
        sub_cell.border = BORDER
        row += 1

        for t in m.tasks:
            ws_detail.cell(row=row, column=1, value=m.id)
            ws_detail.cell(row=row, column=2, value=t.name)
            ws_detail.cell(row=row, column=3, value=t.backend or "")
            ws_detail.cell(row=row, column=4, value=t.frontend or "")
            ws_detail.cell(row=row, column=5, value=t.design or "")
            ws_detail.cell(row=row, column=6, value=t.devops or "")
            ws_detail.cell(row=row, column=7, value=t.qa or "")
            ws_detail.cell(row=row, column=8, value=t.total)
            cost = ws_detail.cell(row=row, column=9, value=f"=H{row}*{RATE_REF}")
            cost.number_format = "#,##0 ₽"

            for col in range(1, 10):
                _style_cell(ws_detail.cell(row=row, column=col),
                            align="right" if 3 <= col <= 9 else "left")
            ws_detail.cell(row=row, column=1).font = Font(bold=True, size=10)
            row += 1

        # Подитог модуля
        ws_detail.cell(row=row, column=1, value="")
        ws_detail.cell(row=row, column=2, value=f"Итого {m.id}")
        ws_detail.cell(row=row, column=3, value=m.sum_backend)
        ws_detail.cell(row=row, column=4, value=m.sum_frontend)
        ws_detail.cell(row=row, column=5, value=m.sum_design)
        ws_detail.cell(row=row, column=6, value=m.sum_devops)
        ws_detail.cell(row=row, column=7, value=m.sum_qa)
        ws_detail.cell(row=row, column=8, value=m.total_hours)
        cost = ws_detail.cell(row=row, column=9, value=f"=H{row}*{RATE_REF}")
        cost.number_format = "#,##0 ₽"
        for col in range(1, 10):
            c = ws_detail.cell(row=row, column=col)
            c.font = Font(bold=True, size=10, color="92400E")
            c.fill = TOTAL_FILL
            c.alignment = Alignment(horizontal="right" if 3 <= col <= 9 else "left", vertical="center")
            c.border = BORDER
        row += 1

    widths = [10, 50, 9, 9, 9, 9, 9, 11, 16]
    for i, w in enumerate(widths, start=1):
        ws_detail.column_dimensions[get_column_letter(i)].width = w
    ws_detail.freeze_panes = "A2"

    # ── Лист 4: Пакеты комплектации ────────────────────────
    ws_pkg = wb.create_sheet("Пакеты")
    headers = ["Пакет", "Описание", "Состав (модули)", "Всего, ч", "Стоимость, ₽"]
    for col, h in enumerate(headers, start=1):
        cell = ws_pkg.cell(row=1, column=col, value=h)
        _style_header(cell)

    row = 2
    for code, name, desc in PACKAGES:
        included = [m for m in MODULES if code in m.options]
        total_hours = sum(m.total_hours for m in included)
        module_list = ", ".join(m.id for m in included)

        ws_pkg.cell(row=row, column=1, value=name)
        ws_pkg.cell(row=row, column=2, value=desc)
        ws_pkg.cell(row=row, column=3, value=module_list)
        ws_pkg.cell(row=row, column=4, value=total_hours)
        cost = ws_pkg.cell(row=row, column=5, value=f"=D{row}*{RATE_REF}")
        cost.number_format = "#,##0 ₽"

        for col in range(1, 6):
            _style_cell(ws_pkg.cell(row=row, column=col),
                        align="right" if 4 <= col <= 5 else "left")
        ws_pkg.cell(row=row, column=1).font = Font(bold=True, size=11, color="4F46E5")
        ws_pkg.row_dimensions[row].height = 50
        row += 1

    widths = [18, 60, 30, 11, 16]
    for i, w in enumerate(widths, start=1):
        ws_pkg.column_dimensions[get_column_letter(i)].width = w

    # ── Лист 5: Матрица модули × пакеты ────────────────────
    ws_matrix = wb.create_sheet("Матрица")
    ws_matrix.cell(row=1, column=1, value="Модуль")
    _style_header(ws_matrix.cell(row=1, column=1))
    for col_idx, (code, name, _) in enumerate(PACKAGES, start=2):
        ws_matrix.cell(row=1, column=col_idx, value=name)
        _style_header(ws_matrix.cell(row=1, column=col_idx))

    for row_idx, m in enumerate(MODULES, start=2):
        c = ws_matrix.cell(row=row_idx, column=1, value=f"{m.id}. {m.title}")
        _style_cell(c)
        for col_idx, (code, name, _) in enumerate(PACKAGES, start=2):
            mark = "✓" if code in m.options else ""
            cell = ws_matrix.cell(row=row_idx, column=col_idx, value=mark)
            _style_cell(cell, align="center", bold=True)
            if mark:
                cell.font = Font(bold=True, color="059669", size=12)

    ws_matrix.column_dimensions["A"].width = 38
    for col_idx in range(2, 2 + len(PACKAGES)):
        ws_matrix.column_dimensions[get_column_letter(col_idx)].width = 18
    ws_matrix.freeze_panes = "B2"

    wb.save(XLSX_PATH)
    return XLSX_PATH


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    docx_path = generate_docx()
    xlsx_path = generate_xlsx()
    print(f"✓ ТЗ:    {docx_path}")
    print(f"✓ Смета: {xlsx_path}")

    # Сводка по модулям
    print()
    print(f"{'ID':<5} {'Модуль':<40} {'Часы':>6} {'Цена':>14}")
    print("─" * 70)
    grand = 0
    for m in MODULES:
        cost = m.total_hours * HOURLY_RATE
        grand += cost
        print(f"{m.id:<5} {m.title[:40]:<40} {m.total_hours:>6} {cost:>10,} ₽".replace(",", " "))
    print("─" * 70)
    total_h = sum(m.total_hours for m in MODULES)
    print(f"{'ИТОГО':<46} {total_h:>6} {grand:>10,} ₽".replace(",", " "))


if __name__ == "__main__":
    main()
