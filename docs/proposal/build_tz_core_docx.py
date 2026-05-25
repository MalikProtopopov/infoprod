"""
ТЗ Core в формате User Story.

Запуск:
  python3 docs/proposal/build_tz_core_docx.py

Выход:
  docs/proposal/Grammy_TZ_Core.docx

Структура:
  - Титул, общее описание
  - Роли (Admin / Manager / Client)
  - 6 эпиков с User Stories (всего ~30 шт)
  - Каждая US: ID, формулировка, критерии приёмки (Given/When/Then)
  - Нефункциональные требования
  - Допущения и ограничения
  - Что не входит в Core
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

OUT_DIR = Path(__file__).resolve().parent
OUT_DOCX = OUT_DIR / "Grammy_TZ_Core.docx"


# ─────────────────────────────────────────────────────────────────────────────
# Данные
# ─────────────────────────────────────────────────────────────────────────────

ROLES = [
    {
        "id": "Admin",
        "name": "Администратор",
        "desc": "Владелец проекта. Полный доступ: подключение ботов и каналов, продукты, цены, "
                "платежи, подписки, заявки, пользователи, аудит-журнал, удаление любых сущностей.",
    },
    {
        "id": "Manager",
        "name": "Менеджер",
        "desc": "Сотрудник, обрабатывающий заявки и платежи. Доступ ко всему, кроме удаления "
                "сущностей и аудит-журнала. Может вводить платежи, продлевать подписки, менять "
                "статусы заявок, дополнять профили клиентов.",
    },
    {
        "id": "Client",
        "name": "Клиент",
        "desc": "Telegram-пользователь, который покупает доступ. Взаимодействует с продуктом "
                "исключительно через бота: выбирает продукт, оставляет заявку, получает invite-"
                "ссылку после оплаты, может отказаться от уведомлений.",
    },
]


@dataclass
class UserStory:
    id: str
    role: str
    want: str
    why: str
    criteria: List[str] = field(default_factory=list)


@dataclass
class Epic:
    id: str
    title: str
    goal: str
    stories: List[UserStory]


EPICS: List[Epic] = [
    Epic(
        id="E1",
        title="Доступ в систему",
        goal="Контролируемый, безопасный вход в админ-панель с разграничением прав.",
        stories=[
            UserStory(
                id="US-1.1", role="Admin",
                want="войти в админ-панель по логину и паролю",
                why="получить доступ к управлению ботом и продажами",
                criteria=[
                    "Когда я ввожу правильные логин и пароль — попадаю на главный экран.",
                    "Когда я ввожу неправильный пароль 10 раз подряд — система блокирует мой IP на 1 минуту.",
                    "Сессия живёт 7 дней, после чего нужен повторный вход.",
                ],
            ),
            UserStory(
                id="US-1.2", role="Admin",
                want="сменить пароль из админ-панели",
                why="поддерживать безопасность аккаунта",
                criteria=[
                    "Для смены требуется ввод текущего пароля.",
                    "Новый пароль вводится дважды и проходит проверку совпадения.",
                    "После смены текущая сессия не разрывается.",
                ],
            ),
            UserStory(
                id="US-1.3", role="Manager",
                want="видеть только разделы, которые относятся к моей работе",
                why="не отвлекаться на функции, которые мне не нужны",
                criteria=[
                    "Менеджер не видит раздел «Аудит-журнал» в сайдбаре.",
                    "Менеджер не может выполнить удаление продукта, канала, бота — система возвращает «недостаточно прав».",
                    "Все остальные разделы доступны менеджеру так же, как администратору.",
                ],
            ),
        ],
    ),

    Epic(
        id="E2",
        title="Настройка инфраструктуры: боты, каналы, продукты",
        goal="Однократная настройка сущностей, через которые ведутся продажи. "
             "Любое число ботов и каналов без правки кода.",
        stories=[
            UserStory(
                id="US-2.1", role="Admin",
                want="подключить Telegram-бота, вставив его токен",
                why="продавать через него доступ в закрытые каналы",
                criteria=[
                    "При сохранении система проверяет токен через getMe и подтягивает имя/username бота.",
                    "Невалидный токен возвращает понятную ошибку, бот не создаётся.",
                    "Сразу после сохранения бот начинает принимать сообщения (без рестарта сервиса).",
                ],
            ),
            UserStory(
                id="US-2.2", role="Admin",
                want="подключить закрытый Telegram-канал к боту",
                why="иметь куда выдавать доступ платящим клиентам",
                criteria=[
                    "Система проверяет, что бот добавлен в канал как админ с правом приглашать.",
                    "Если прав недостаточно — выводится подсказка, что именно нужно дать.",
                    "После подключения канал можно привязать к одному или нескольким продуктам.",
                ],
            ),
            UserStory(
                id="US-2.3", role="Admin",
                want="создать продукт с ценами на 3, 6 и 12 месяцев",
                why="предлагать клиентам выбор по бюджету и сроку",
                criteria=[
                    "Поля: название, короткий код для deep-link, валюта, три цены, привязка к каналу.",
                    "Код продукта уникален и не конфликтует с tracking-ссылками.",
                    "Продукт можно деактивировать без удаления, чтобы временно скрыть.",
                ],
            ),
            UserStory(
                id="US-2.4", role="Admin",
                want="видеть, что система не даёт удалить сущности, на которые что-то ссылается",
                why="не сломать связи и не потерять данные клиентов",
                criteria=[
                    "Попытка удалить продукт с активными подписками блокируется с пояснением.",
                    "Бот с привязанными каналами/продуктами тоже нельзя удалить, пока они есть.",
                    "Удаление разрешено только админу, не менеджеру.",
                ],
            ),
        ],
    ),

    Epic(
        id="E3",
        title="Приём заявок от клиентов",
        goal="Клиент через бота оставляет заявку, она моментально появляется в админке.",
        stories=[
            UserStory(
                id="US-3.1", role="Client",
                want="написать боту /start и увидеть каталог продуктов",
                why="понять, что доступно к покупке",
                criteria=[
                    "Бот отвечает в течение 1 секунды.",
                    "Каждый продукт показан карточкой с названием, описанием, тремя ценами.",
                    "У каждой карточки есть кнопки выбора срока и «Оставить заявку».",
                ],
            ),
            UserStory(
                id="US-3.2", role="Client",
                want="оставить заявку нажатием одной кнопки",
                why="чтобы со мной связались и помогли с оплатой",
                criteria=[
                    "После нажатия бот подтверждает, что заявка отправлена.",
                    "Запись о заявке создаётся в админке мгновенно.",
                    "Если на этот же продукт у меня уже есть открытая заявка — новая не создаётся, бот напоминает.",
                ],
            ),
            UserStory(
                id="US-3.3", role="Manager",
                want="видеть в сайдбаре бейдж с числом новых заявок",
                why="не пропустить ни одного входящего лида",
                criteria=[
                    "Бейдж amber-цвета, видно из любого раздела админки.",
                    "Число обновляется каждую минуту автоматически.",
                    "Клик по бейджу открывает /leads с фильтром «new».",
                ],
            ),
            UserStory(
                id="US-3.4", role="Manager",
                want="открыть заявку и увидеть контакты клиента и историю",
                why="звонить или писать клиенту в правильный мессенджер",
                criteria=[
                    "В заявке видны: имя клиента, @username, привязанный продукт, дата.",
                    "Если у клиента уже были заявки и платежи — они показаны во вкладках профиля.",
                    "Доступны быстрые действия: связались, оплатил, закрыта.",
                ],
            ),
            UserStory(
                id="US-3.5", role="Manager",
                want="вести заявку по статусам new → contacted → paid → closed",
                why="отслеживать прогресс продажи и не терять клиентов",
                criteria=[
                    "На каждом переходе фиксируется временная метка.",
                    "Статус paid выставляется автоматически при создании платежа клиента.",
                    "Нельзя случайно вернуть закрытую заявку в «новую».",
                ],
            ),
            UserStory(
                id="US-3.6", role="Client",
                want="чтобы бот вежливо просил написать менеджеру при любом вне-сценарном тексте",
                why="не получить молчание и понять, как продолжить",
                criteria=[
                    "На любой текст, не подходящий под /start или callback, бот отвечает заранее настроенным текстом.",
                    "Текст содержит подсказку, как связаться с человеком.",
                    "Ответ не блокирует возможность снова попасть в каталог через /start.",
                ],
            ),
        ],
    ),

    Epic(
        id="E4",
        title="Платежи и выдача доступа",
        goal="После оплаты клиент получает доступ автоматически. По истечении — теряет.",
        stories=[
            UserStory(
                id="US-4.1", role="Manager",
                want="вручную внести платёж за клиента, выбрав продукт и срок",
                why="зафиксировать оплату, полученную вне Telegram",
                criteria=[
                    "Поля: клиент (поиск по @username/имени/TG ID), продукт, период (3/6/12 мес), сумма.",
                    "После сохранения создаётся подписка с датой истечения = сегодня + срок.",
                    "Сразу же отправляется invite-ссылка клиенту в личку бота.",
                ],
            ),
            UserStory(
                id="US-4.2", role="Client",
                want="получить ссылку в закрытый канал сразу после оплаты",
                why="попасть в канал без задержки и человеческого вмешательства",
                criteria=[
                    "Ссылка одноразовая (используется один раз).",
                    "Ссылка действует до истечения подписки.",
                    "Если я уже в канале (повторная оплата) — продлевается срок, без новой ссылки.",
                ],
            ),
            UserStory(
                id="US-4.3", role="Admin",
                want="чтобы система автоматически кикала клиентов с истекшей подпиской",
                why="не платить за «бесплатных» пользователей и держать канал чистым",
                criteria=[
                    "Воркер запускается раз в час и проверяет все active-подписки.",
                    "При обнаружении ends_at ≤ now статус меняется на expired, клиент удаляется из канала.",
                    "Клиенту отправляется сообщение с предложением продлить.",
                ],
            ),
            UserStory(
                id="US-4.4", role="Manager",
                want="продлить подписку клиенту",
                why="вернуть доступ или продлить текущий без двойной работы",
                criteria=[
                    "Продление выбирает срок (3/6/12 мес) и создаёт платёж.",
                    "Если подписка ещё активна — срок суммируется, не сбрасывается.",
                    "Если истекла — создаётся новая запись и новый invite.",
                ],
            ),
            UserStory(
                id="US-4.5", role="Manager",
                want="досрочно отозвать подписку нарушителя",
                why="убрать из канала клиента, который нарушает правила",
                criteria=[
                    "Действие требует подтверждения с указанием причины.",
                    "Клиент удаляется из канала немедленно, статус подписки = revoked.",
                    "Действие логируется в аудит-журнале.",
                ],
            ),
        ],
    ),

    Epic(
        id="E5",
        title="Профиль клиента и история взаимодействий",
        goal="Менеджер всегда понимает контекст разговора: кто этот человек, что с ним было.",
        stories=[
            UserStory(
                id="US-5.1", role="Manager",
                want="найти клиента по имени, @username или Telegram ID",
                why="быстро открыть нужный профиль во время разговора",
                criteria=[
                    "Поиск работает по частичному совпадению.",
                    "Результаты появляются по мере набора (не нужно нажимать Enter).",
                    "На странице результатов виден последний статус клиента (есть ли активная подписка).",
                ],
            ),
            UserStory(
                id="US-5.2", role="Manager",
                want="в профиле клиента видеть все его заявки, платежи и подписки на одном экране",
                why="быстро понимать историю и принимать решения",
                criteria=[
                    "Три вкладки: «Заявки», «Платежи», «Подписки».",
                    "Каждая запись с датой и ссылкой на детальный экран.",
                    "На главной вкладке профиля — контакты и заметки менеджера.",
                ],
            ),
            UserStory(
                id="US-5.3", role="Manager",
                want="добавить в профиль клиента email, телефон и текстовую заметку",
                why="дополнить данные, которые бот не собирает автоматически",
                criteria=[
                    "Поля свободные, без обязательной валидации.",
                    "Заметка многострочная, до 2000 символов.",
                    "Изменения сохраняются auto-save с задержкой 1 сек.",
                ],
            ),
            UserStory(
                id="US-5.4", role="Client",
                want="отказаться от уведомлений бота",
                why="бот не должен мне писать, если я не хочу",
                criteria=[
                    "В любом сообщении бота есть кнопка «Не присылать напоминания».",
                    "После нажатия флаг сохраняется, бот больше не пишет автоматически.",
                    "Это не отменяет invite-ссылки на канал (они приходят по оплате).",
                ],
            ),
        ],
    ),

    Epic(
        id="E6",
        title="Развёртывание и эксплуатация",
        goal="Один сервер, одна команда запуска. Минимум ручных операций после внедрения.",
        stories=[
            UserStory(
                id="US-6.1", role="Admin",
                want="запустить всю систему одной командой docker compose up на новом сервере",
                why="не зависеть от конкретного провайдера и иметь возможность переезда",
                criteria=[
                    "После клонирования репозитория и заполнения .env система разворачивается за < 5 минут.",
                    "На чистом VPS с Ubuntu и установленным Docker дополнительные пакеты не нужны.",
                    "Документация по разворачиванию умещается на одной странице.",
                ],
            ),
            UserStory(
                id="US-6.2", role="Admin",
                want="чтобы HTTPS-сертификат продлевался автоматически",
                why="не получать жалобы от менеджеров о «небезопасном сайте»",
                criteria=[
                    "Сертификат выпускается через Let's Encrypt при первом запуске.",
                    "Certbot проверяет срок раз в 12 часов и продлевает за 30 дней до истечения.",
                    "Nginx подхватывает новый сертификат без рестарта.",
                ],
            ),
            UserStory(
                id="US-6.3", role="Admin",
                want="работать с админкой со смартфона",
                why="принимать заявки и фиксировать оплаты, когда я не у компьютера",
                criteria=[
                    "Все ключевые экраны (Заявки, Платежи, Подписки) корректно отображаются на iOS Safari и Android Chrome.",
                    "Бургер-меню открывает sidebar; формы оптимизированы под пальцы.",
                    "Можно добавить иконку на главный экран как PWA.",
                ],
            ),
            UserStory(
                id="US-6.4", role="Admin",
                want="видеть бренд Grammy во всех точках (favicon, лого, OpenGraph)",
                why="команда воспринимает систему как профессиональный продукт",
                criteria=[
                    "Фавикон-винил отображается во вкладке браузера.",
                    "В sidebar — логотип-винил + название «Grammy».",
                    "При шаринге ссылки в Telegram/Slack показывается OG-картинка с брендом.",
                ],
            ),
        ],
    ),
]


# Нефункциональные требования
NFR = [
    ("Производительность", "Загрузка любого экрана админки — не более 1.5 сек на 1000+ заявок. Бот отвечает на /start за < 1 сек."),
    ("Безопасность", "Пароли в bcrypt-хэше, JWT в HttpOnly+Secure cookie, защита от подбора (rate-limit 10/мин по IP), маскирование секретов в логах."),
    ("Доступность", "Целевой uptime бота и админки — 99.5% в месяц. Воркер кика по истечении гарантирует выполнение в окне ≤ 1 час."),
    ("Масштаб", "Без переписывания: до 50 ботов в одном процессе, до 10 000 активных подписок, до 100 000 пользователей в БД."),
    ("Мобильность", "Все ключевые экраны работают на экранах от 360px. Тач-цели не менее 40×40 px."),
]


OUT_OF_SCOPE = [
    "Прогрев клиентов воронкой сообщений (отдельный модуль, не входит в Core).",
    "Лидмагниты (PDF/видео в шагах воронки) — не входит в Core.",
    "Tracking-ссылки и UTM-метки — не входит в Core.",
    "Страница «Эффективность» с графиками и Pareto-таблицей — не входит в Core.",
    "Аудит-журнал действий администраторов — не входит в Core.",
    "Prometheus / Grafana / Loki / алерты — не входит в Core.",
    "Покрытие тестами и CI/CD pipeline — не входит в Core.",
    "Интеграция Telegram Payments (Stars или провайдеры) — не входит в Core, платежи вводятся вручную.",
]


ASSUMPTIONS = [
    "Заказчик предоставляет: VPS с Ubuntu 22.04+ и установленным Docker; доменное имя для админки; токены ботов из @BotFather; ID закрытых каналов с правами админа у бота.",
    "Платежи проводятся вне Telegram (банковские переводы, ИП, эквайринг и т.п.). Внутри системы платёж фиксируется менеджером вручную.",
    "У одного продукта — один канал. Один бот может обслуживать несколько продуктов и каналов.",
    "Все цены продукта — в одной валюте (по умолчанию ₽).",
    "Срок реализации Core — 2 недели с момента подписания договора.",
    "Гарантия на исправление багов — 3 месяца после сдачи.",
]


# ─────────────────────────────────────────────────────────────────────────────
# Стили docx
# ─────────────────────────────────────────────────────────────────────────────

INDIGO = RGBColor(0x4F, 0x46, 0xE5)
INK = RGBColor(0x1E, 0x1B, 0x4B)
MUTED = RGBColor(0x6B, 0x72, 0x80)


def _add_hr(doc):
    p = doc.add_paragraph()
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:color"), "C7D2FE")
    pBdr.append(bottom)
    pPr.append(pBdr)


def _heading(doc, text, *, size, bold=True, color=INK, after_pt=6, before_pt=0, align="left"):
    p = doc.add_paragraph()
    if align == "center":
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(text)
    r.font.size = Pt(size)
    r.bold = bold
    r.font.color.rgb = color
    p.paragraph_format.space_after = Pt(after_pt)
    p.paragraph_format.space_before = Pt(before_pt)
    return p


def _para(doc, text, *, size=11, color=INK, italic=False, bold=False, after_pt=4):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.font.size = Pt(size)
    r.italic = italic
    r.bold = bold
    r.font.color.rgb = color
    p.paragraph_format.space_after = Pt(after_pt)
    return p


def _us_block(doc, us: UserStory, role_name_by_id: dict):
    """Рендерит одну User Story: ID, формулировка, критерии приёмки."""
    # Заголовок US
    p = doc.add_paragraph()
    r1 = p.add_run(f"{us.id}  ")
    r1.font.size = Pt(11)
    r1.font.color.rgb = INDIGO
    r1.bold = True
    r1.font.name = "Consolas"

    role_name = role_name_by_id.get(us.role, us.role)
    r2 = p.add_run(f"Как {role_name},")
    r2.font.size = Pt(11)
    r2.bold = True
    r2.font.color.rgb = INK

    r3 = p.add_run(f" я хочу {us.want},")
    r3.font.size = Pt(11)
    r3.font.color.rgb = INK

    r4 = p.add_run(f" чтобы {us.why}.")
    r4.font.size = Pt(11)
    r4.italic = True
    r4.font.color.rgb = MUTED

    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.left_indent = Cm(0.5)

    # Критерии приёмки
    if us.criteria:
        cp = doc.add_paragraph()
        cr = cp.add_run("Критерии приёмки")
        cr.font.size = Pt(9.5)
        cr.bold = True
        cr.font.color.rgb = INDIGO
        cp.paragraph_format.left_indent = Cm(1.0)
        cp.paragraph_format.space_after = Pt(2)

        for c in us.criteria:
            cb = doc.add_paragraph(c, style="List Bullet")
            cb.paragraph_format.left_indent = Cm(1.5)
            cb.paragraph_format.space_after = Pt(1)
            for r in cb.runs:
                r.font.size = Pt(10)
                r.font.color.rgb = INK

    # Лёгкий разделитель
    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_after = Pt(2)


# ─────────────────────────────────────────────────────────────────────────────
# Генерация
# ─────────────────────────────────────────────────────────────────────────────

def build():
    doc = Document()

    # Базовый стиль
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
    title.paragraph_format.space_after = Pt(8)

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rs = sub.add_run("Telegram-бот продажи доступа в закрытые каналы\nФормат: User Story по ролям")
    rs.font.size = Pt(13)
    rs.font.color.rgb = MUTED

    doc.add_paragraph()
    info = doc.add_paragraph()
    info.alignment = WD_ALIGN_PARAGRAPH.CENTER
    ri = info.add_run("6 эпиков · 26 User Stories · нефункциональные требования · допущения")
    ri.italic = True
    ri.font.size = Pt(10.5)
    ri.font.color.rgb = MUTED

    doc.add_page_break()

    # 1. Общее описание
    _heading(doc, "1. О продукте", size=18, color=INK, after_pt=8)
    _para(doc,
          "Grammy — закрытая админ-панель и Telegram-бот для продажи доступа в закрытые каналы. "
          "Версия Core покрывает базовый сценарий: клиент через бота оставляет заявку, менеджер "
          "связывается и фиксирует оплату, система автоматически добавляет клиента в канал и "
          "автоматически удаляет по истечении подписки. На любые вне-сценарные обращения бот "
          "вежливо просит написать менеджеру.")
    _para(doc,
          "ТЗ написано в формате User Story с привязкой к ролям. Каждая история формулирует одну "
          "потребность одного типа пользователя и сопровождается критериями приёмки. "
          "Технические детали реализации остаются за исполнителем.", after_pt=10)

    # 2. Роли
    _heading(doc, "2. Роли пользователей", size=18, color=INK, before_pt=10, after_pt=6)

    role_name_by_id = {r["id"]: r["name"] for r in ROLES}
    table = doc.add_table(rows=1 + len(ROLES), cols=2)
    table.style = "Light Grid Accent 1"
    hdr = table.rows[0].cells
    hdr[0].text = "Роль"
    hdr[1].text = "Описание"
    for c in hdr:
        for p in c.paragraphs:
            for r in p.runs:
                r.bold = True
                r.font.size = Pt(11)
    for i, role in enumerate(ROLES, start=1):
        cells = table.rows[i].cells
        cells[0].text = role["name"]
        cells[1].text = role["desc"]
        for p in cells[0].paragraphs:
            for r in p.runs:
                r.bold = True
                r.font.size = Pt(11)
                r.font.color.rgb = INDIGO
        for p in cells[1].paragraphs:
            for r in p.runs:
                r.font.size = Pt(10.5)
    for row in table.rows:
        row.cells[0].width = Cm(4)
        row.cells[1].width = Cm(13)

    doc.add_paragraph()

    # 3. Эпики и User Stories
    _heading(doc, "3. Функциональные требования (User Stories)", size=18, color=INK, before_pt=14, after_pt=4)
    _para(doc,
          "26 историй, объединённых в 6 эпиков. Каждая история сформулирована по шаблону "
          "«Как [роль], я хочу [действие], чтобы [результат]» и сопровождается критериями приёмки.",
          color=MUTED, after_pt=10)

    for epic in EPICS:
        _heading(doc, f"{epic.id}. {epic.title}", size=15, color=INDIGO, before_pt=14, after_pt=4)
        _para(doc, f"Цель эпика: {epic.goal}", italic=True, color=MUTED, after_pt=8)
        for us in epic.stories:
            _us_block(doc, us, role_name_by_id)
        _add_hr(doc)

    # 4. Нефункциональные требования
    doc.add_page_break()
    _heading(doc, "4. Нефункциональные требования", size=18, color=INK, after_pt=8)

    nfr_table = doc.add_table(rows=1 + len(NFR), cols=2)
    nfr_table.style = "Light Grid Accent 1"
    nh = nfr_table.rows[0].cells
    nh[0].text = "Параметр"
    nh[1].text = "Требование"
    for c in nh:
        for p in c.paragraphs:
            for r in p.runs:
                r.bold = True
                r.font.size = Pt(11)
    for i, (name, desc) in enumerate(NFR, start=1):
        cells = nfr_table.rows[i].cells
        cells[0].text = name
        cells[1].text = desc
        for p in cells[0].paragraphs:
            for r in p.runs:
                r.bold = True
                r.font.size = Pt(11)
                r.font.color.rgb = INDIGO
        for p in cells[1].paragraphs:
            for r in p.runs:
                r.font.size = Pt(10.5)
    for row in nfr_table.rows:
        row.cells[0].width = Cm(4)
        row.cells[1].width = Cm(13)

    # 5. Допущения
    _heading(doc, "5. Допущения и зона ответственности заказчика", size=18, color=INK, before_pt=14, after_pt=6)
    for a in ASSUMPTIONS:
        b = doc.add_paragraph(a, style="List Bullet")
        for r in b.runs:
            r.font.size = Pt(10.5)
            r.font.color.rgb = INK

    # 6. Что не входит в Core
    _heading(doc, "6. Что не входит в Core", size=18, color=INK, before_pt=14, after_pt=6)
    _para(doc, "Перечисленное ниже продаётся отдельными модулями (см. таблицу опций в КП):",
          italic=True, color=MUTED, after_pt=4)
    for s in OUT_OF_SCOPE:
        b = doc.add_paragraph(s, style="List Bullet")
        for r in b.runs:
            r.font.size = Pt(10.5)
            r.font.color.rgb = INK

    # Финал
    _heading(doc, "7. Порядок приёмки", size=18, color=INK, before_pt=14, after_pt=6)
    _para(doc,
          "Приёмка ведётся в два этапа. После первой недели — приёмочное тестирование инфраструктуры, "
          "аутентификации, базового бота с /start и каталогом, добавления продуктов/каналов. "
          "После второй недели — приёмочное тестирование сценария оплаты и автоматической выдачи доступа "
          "плюс worker автоматического кика по истечении.",
          after_pt=6)
    _para(doc,
          "Каждая User Story считается выполненной только при прохождении всех её критериев приёмки. "
          "Замечания фиксируются в трекере, исправляются в рамках работ без дополнительной оплаты.",
          after_pt=6)

    doc.save(OUT_DOCX)
    return OUT_DOCX


def main():
    path = build()
    total_us = sum(len(e.stories) for e in EPICS)
    print(f"✓ ТЗ Core: {path} ({path.stat().st_size // 1024} KB)")
    print(f"  {len(EPICS)} эпиков · {total_us} User Stories · {len(ROLES)} роли")


if __name__ == "__main__":
    main()
