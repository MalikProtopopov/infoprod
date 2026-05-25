"""
Собирает HTML руководства пользователя Grammy.

Запуск:
  python3 docs/proposal/build_guide_html.py
  node docs/proposal/html_to_pdf.js docs/proposal/Grammy_Guide.html docs/proposal/Grammy_Guide.pdf --guide

Формат: A4 portrait. Колонтитулы (header + footer + номер страницы) рендерятся
Chromium-ом через --guide флаг в html_to_pdf.js — они автоматически повторяются
на каждой физической странице, включая страницы, на которые перешёл текст.
"""
from __future__ import annotations

import base64
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent
SHOTS_DIR = OUT_DIR / "screenshots"
OUT_HTML = OUT_DIR / "Grammy_Guide.html"


def img_b64(name: str) -> str:
    p = SHOTS_DIR / name
    if not p.exists():
        return ""
    return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode("ascii")


VINYL_SVG = """
<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:100%">
  <defs>
    <radialGradient id="d" cx="50%" cy="50%" r="55%">
      <stop offset="0%" stop-color="#1e1b4b"/><stop offset="70%" stop-color="#0f0a2e"/><stop offset="100%" stop-color="#050314"/>
    </radialGradient>
    <linearGradient id="l" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#818cf8"/><stop offset="55%" stop-color="#6366f1"/><stop offset="100%" stop-color="#f43f5e"/>
    </linearGradient>
  </defs>
  <circle cx="32" cy="32" r="30" fill="url(#d)"/>
  <g stroke="#fff" fill="none" stroke-width="0.35"><circle cx="32" cy="32" r="26" opacity=".10"/><circle cx="32" cy="32" r="23" opacity=".10"/><circle cx="32" cy="32" r="20" opacity=".10"/><circle cx="32" cy="32" r="17" opacity=".10"/></g>
  <path d="M 32 3 A 29 29 0 0 1 61 32" stroke="#fff" stroke-width="0.8" fill="none" opacity=".18" stroke-linecap="round"/>
  <circle cx="32" cy="32" r="11.5" fill="url(#l)"/><circle cx="32" cy="32" r="1.6" fill="#050314"/>
</svg>
""".strip()


CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
@page { size: A4 portrait; margin: 22mm 18mm 18mm 18mm; }

html, body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  font-size: 11pt;
  color: #1e1b4b;
  background: #fff;
  line-height: 1.55;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}

/* COVER — отдельный полностраничный блок с dark-bg, выходит в Chromium margin'ы,
   чтобы перекрыть на этой странице PDF header/footer (они есть, но сольются с фоном) */
.cover {
  margin: -22mm -18mm -18mm -18mm;
  padding: 50mm 24mm 30mm;
  min-height: 297mm;
  background: radial-gradient(circle at 20% 25%, #2a2566 0%, #0f0a2e 55%, #050314 100%);
  color: #fff;
  page-break-after: always;
  display: flex;
  flex-direction: column;
  justify-content: center;
  position: relative;
}
.cover .logo { width: 28mm; height: 28mm; margin-bottom: 14mm; }
.cover .kicker {
  font-size: 11pt; text-transform: uppercase; letter-spacing: 3px; color: #818cf8; margin-bottom: 5mm;
}
.cover h1 {
  font-size: 48pt; font-weight: 900; line-height: 1; letter-spacing: -2px;
  color: #ffffff;
  margin-bottom: 5mm;
}
.cover .subtitle { font-size: 17pt; color: #c7d2fe; max-width: 150mm; line-height: 1.35; }
.cover .meta {
  position: absolute; bottom: 30mm; left: 24mm;
  color: #818cf8; font-size: 10pt; letter-spacing: 1px; text-transform: uppercase;
}

/* TOC */
.toc-page { page-break-after: always; padding-top: 4mm; }
.toc-page h1 { font-size: 24pt; font-weight: 800; margin-bottom: 8mm; }
.toc { margin-top: 6mm; }
.toc ol { list-style: none; padding: 0; }
.toc li {
  display: flex; justify-content: space-between; padding: 2.5mm 0;
  border-bottom: 1px dashed #e5e7eb;
  font-size: 11.5pt; color: #1e1b4b;
}
.toc li .num { color: #6366f1; font-weight: 700; margin-right: 4mm; min-width: 14mm; }
.toc li .pg { color: #9ca3af; font-variant-numeric: tabular-nums; }

/* Глава */
.chapter {
  page-break-after: always;
  padding-top: 4mm;
}
.chapter:last-child { page-break-after: auto; }

/* Номер главы и заголовок — в две отдельные строки */
.ch-num {
  display: block;
  font-size: 10pt;
  font-weight: 700;
  color: #6366f1;
  letter-spacing: 3px;
  text-transform: uppercase;
  margin-bottom: 4mm;
}
.ch-title {
  font-size: 24pt;
  font-weight: 800;
  letter-spacing: -0.5px;
  color: #1e1b4b;
  margin-bottom: 5mm;
  page-break-after: avoid;
}

.intro {
  font-size: 11.5pt;
  color: #4b5563;
  max-width: 165mm;
  margin-bottom: 6mm;
}

/* Скриншоты — без border, без тяжёлой тени */
.shot {
  margin: 6mm 0 0;
  border-radius: 3mm;
  overflow: hidden;
  page-break-inside: avoid;
}
.shot img { width: 100%; display: block; }
.caption {
  font-size: 9pt;
  color: #6b7280;
  font-style: italic;
  text-align: center;
  margin-top: 2mm;
  margin-bottom: 5mm;
}

/* Мобильные скриншоты — узкие, ставим в ряд */
.mobile-row {
  display: flex;
  gap: 10mm;
  justify-content: center;
  margin: 6mm 0 4mm;
  page-break-inside: avoid;
}
.mobile-row .frame {
  flex: 0 0 62mm;
  border-radius: 4mm;
  overflow: hidden;
  background: #0b1020;
  padding: 3mm;
  box-shadow: 0 4px 12px -4px rgba(15,10,46,0.18);
}
.mobile-row .frame img {
  width: 100%;
  display: block;
  border-radius: 2mm;
}
.mobile-caption {
  text-align: center;
  font-size: 9.5pt;
  color: #6b7280;
  margin-top: 1mm;
  font-weight: 500;
}

/* Подразделы */
h2.sec {
  font-size: 14pt;
  font-weight: 700;
  color: #1e1b4b;
  margin-top: 7mm;
  margin-bottom: 3mm;
  page-break-after: avoid;
}
h3.subsec {
  font-size: 11pt;
  font-weight: 700;
  color: #4f46e5;
  text-transform: uppercase;
  letter-spacing: 1.5px;
  margin-top: 6mm;
  margin-bottom: 2mm;
  page-break-after: avoid;
}

p { margin-bottom: 2mm; }

/* Steps */
ol.steps {
  padding-left: 0;
  list-style: none;
  counter-reset: step;
  page-break-inside: avoid;
}
ol.steps li {
  position: relative;
  padding: 2mm 0 2mm 11mm;
  margin-bottom: 1mm;
  font-size: 10.5pt;
  color: #374151;
  line-height: 1.5;
  counter-increment: step;
}
ol.steps li::before {
  content: counter(step);
  position: absolute; left: 0; top: 1.5mm;
  width: 7mm; height: 7mm; border-radius: 50%;
  background: #6366f1;
  color: #fff;
  font-size: 9pt; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
}

kbd {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 9pt; background: #f3f4f6; border: 1px solid #d1d5db;
  border-radius: 3px; padding: 0.5mm 1.5mm; color: #1e1b4b;
}
code {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 9.5pt; background: #eef2ff; color: #4338ca;
  padding: 0.3mm 1.5mm; border-radius: 3px;
}

.tip, .warn {
  margin: 5mm 0;
  padding: 4mm 5mm;
  border-radius: 3mm;
  font-size: 10pt;
  page-break-inside: avoid;
}
.tip {
  background: #f5f3ff;
  border-left: 4px solid #6366f1;
  color: #4338ca;
}
.tip strong { color: #1e1b4b; }
.warn {
  background: #fef3c7;
  border-left: 4px solid #f59e0b;
  color: #92400e;
}
.warn strong { color: #78350f; }
"""


# ─────────────────────────────────────────────────────────────────────────────
# Cover & TOC
# ─────────────────────────────────────────────────────────────────────────────

def page_cover() -> str:
    return f"""
    <section class="cover">
      <div class="logo">{VINYL_SVG}</div>
      <div class="kicker">Grammy</div>
      <h1>Руководство<br/>пользователя</h1>
      <p class="subtitle">Подключение, продажи, воронки, аналитика — пошагово, с реальными скриншотами интерфейса.</p>
      <div class="meta">v1.0 · 2026 · mediann.dev</div>
    </section>
    """


def page_toc(items: list[tuple[str, str, int]]) -> str:
    lis = "".join(
        f'<li><span><span class="num">{num}</span>{title}</span><span class="pg">с. {page}</span></li>'
        for num, title, page in items
    )
    return f"""
    <section class="toc-page">
      <h1>Содержание</h1>
      <div class="toc"><ol>{lis}</ol></div>
    </section>
    """


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def render_steps(steps: list[str]) -> str:
    return "<ol class='steps'>" + "".join(f"<li>{s}</li>" for s in steps) + "</ol>"


def render_shot(name: str, caption: str = "") -> str:
    if not name:
        return ""
    out = f'<div class="shot"><img src="{img_b64(name)}" alt=""/></div>'
    if caption:
        out += f'<div class="caption">{caption}</div>'
    return out


def render_tip(text: str) -> str:
    return f'<div class="tip"><strong>Совет.</strong> {text}</div>' if text else ""


def render_warn(text: str) -> str:
    return f'<div class="warn"><strong>Внимание.</strong> {text}</div>' if text else ""


# ─────────────────────────────────────────────────────────────────────────────
# Главы
# ─────────────────────────────────────────────────────────────────────────────

def chapter(*, num: str, title: str, intro: str = "",
            shot: str = "", caption: str = "",
            sections: list[dict] = None,
            tip: str = "", warn: str = "") -> str:
    """Базовая глава: интро → скриншот → секции с шагами → совет/предупреждение."""
    sec_html = ""
    for s in (sections or []):
        sec_html += f'<h2 class="sec">{s["heading"]}</h2>'
        if s.get("text"):
            sec_html += f'<p>{s["text"]}</p>'
        if s.get("steps"):
            sec_html += render_steps(s["steps"])
    return f"""
    <section class="chapter">
      <div class="ch-num">ГЛАВА {num}</div>
      <h1 class="ch-title">{title}</h1>
      {f'<p class="intro">{intro}</p>' if intro else ''}
      {render_shot(shot, caption)}
      {sec_html}
      {render_tip(tip)}
      {render_warn(warn)}
    </section>
    """


def chapter_compact(*, num: str, title: str, intro: str = "",
                    blocks: list[dict]) -> str:
    """Глава с несколькими подразделами/скриншотами подряд."""
    html_blocks = ""
    for b in blocks:
        html_blocks += '<div style="page-break-inside: avoid;">'
        html_blocks += f'<h3 class="subsec">{b["heading"]}</h3>'
        if b.get("text"):
            html_blocks += f'<p style="font-size:10.5pt; color:#4b5563; margin-bottom:3mm;">{b["text"]}</p>'
        if b.get("shot"):
            html_blocks += render_shot(b["shot"], b.get("caption", ""))
        if b.get("steps"):
            html_blocks += render_steps(b["steps"])
        html_blocks += '</div>'
    return f"""
    <section class="chapter">
      <div class="ch-num">ГЛАВА {num}</div>
      <h1 class="ch-title">{title}</h1>
      {f'<p class="intro">{intro}</p>' if intro else ''}
      {html_blocks}
    </section>
    """


def chapter_mobile() -> str:
    """Спец-глава про mobile: два узких скриншота в ряд (не растянутые)."""
    return f"""
    <section class="chapter">
      <div class="ch-num">ГЛАВА 12</div>
      <h1 class="ch-title">Мобильный режим</h1>
      <p class="intro">Все экраны адаптированы под смартфон. Sidebar скрывается и открывается бургер-кнопкой, таблицы получают горизонтальный скролл, кнопки увеличены под пальцы.</p>

      <div class="mobile-row">
        <div>
          <div class="frame">
            <img src="{img_b64('20_mobile_dashboard.png')}" alt=""/>
          </div>
          <div class="mobile-caption">Дашборд на смартфоне</div>
        </div>
        <div>
          <div class="frame">
            <img src="{img_b64('21_mobile_sidebar.png')}" alt=""/>
          </div>
          <div class="mobile-caption">Sidebar в режиме оверлея</div>
        </div>
      </div>

      <h2 class="sec">Как пользоваться</h2>
      <ol class="steps">
        <li>Тапните по бургеру слева сверху — выезжает сайдбар.</li>
        <li>Закрыть — крестиком или по фону.</li>
        <li>Все формы оптимизированы под пальцы: минимальная высота кнопки 40 px.</li>
        <li>Таблицы прокручиваются горизонтально внутри своего блока — страница не «разъезжается».</li>
      </ol>

      <div class="tip"><strong>Совет.</strong> Добавьте админку на главный экран iOS/Android через «Поделиться → На экран Домой». Манифест уже настроен — иконка-винил появится как полноценное приложение.</div>
    </section>
    """


# ─────────────────────────────────────────────────────────────────────────────

def build_html() -> str:
    parts = []
    parts.append(page_cover())

    toc_items = [
        ("1.", "Вход в систему", 3),
        ("2.", "Главный экран и навигация", 4),
        ("3.", "Настройка инфраструктуры: боты, каналы, продукты", 5),
        ("4.", "Воронки прогрева: Студия", 8),
        ("5.", "Лидмагниты", 11),
        ("6.", "Точки входа и атрибуция", 12),
        ("7.", "Обработка заявок и платежей", 13),
        ("8.", "Аналитика и метрики", 15),
        ("9.", "Пользователи", 16),
        ("10.", "Аудит-журнал", 17),
        ("11.", "Профиль и смена пароля", 18),
        ("12.", "Мобильный режим", 19),
        ("13.", "Типичные сценарии", 20),
    ]
    parts.append(page_toc(toc_items))

    # Глава 1
    parts.append(chapter(
        num="1", title="Вход в систему",
        intro="Админ-панель Grammy закрыта от поисковиков и доступна только по паре «логин + пароль». Это безопасное HTTPS-соединение с автопродлеваемым SSL-сертификатом.",
        shot="01_login.png",
        caption="Страница входа. Логин и пароль выдаются администратором при настройке системы.",
        sections=[{
            "heading": "Как войти",
            "steps": [
                "Откройте адрес вашей админки в браузере (например, <code>https://grammy.mediann.dev</code>).",
                "Введите логин и пароль администратора.",
                "Нажмите «Войти» — при успешном входе попадёте на главный экран.",
            ],
        }],
        warn="После 10 неудачных попыток вход с вашего IP блокируется на 1 минуту — защита от подбора пароля.",
    ))

    # Глава 2
    parts.append(chapter(
        num="2", title="Главный экран и навигация",
        intro="После входа вы видите дашборд с ключевыми показателями и боковую панель с разделами. Все цифры обновляются автоматически каждую минуту.",
        shot="02_dashboard.png",
        caption="Главный экран: KPI за период, последние заявки и платежи, бейджи в сайдбаре.",
        sections=[
            {
                "heading": "Что показывает главный экран",
                "steps": [
                    "Четыре карточки KPI: пользователи, заявки, подписки, выручка за последние 30 дней.",
                    "Список последних 5 заявок (с переходом на профиль клиента).",
                    "Список последних 5 платежей с суммой и периодом подписки.",
                ],
            },
            {
                "heading": "Сайдбар: 7 групп разделов",
                "steps": [
                    "<strong>Обзор</strong> — главный экран.",
                    "<strong>Аналитика</strong> — «Эффективность» и «Источники».",
                    "<strong>Продажи</strong> — Заявки, Платежи, Подписки.",
                    "<strong>Воронки</strong> — Воронки, Лидмагниты, Кодовые слова.",
                    "<strong>Каталог</strong> — Продукты, Каналы, Боты.",
                    "<strong>Аудитория</strong> — Пользователи.",
                    "<strong>Администрирование</strong> — Аудит-журнал (только для роли admin).",
                ],
            },
        ],
        tip="Группы сайдбара сворачиваются кликом по их заголовку. Состояние запоминается между сессиями.",
    ))

    # Глава 3 — Инфраструктура
    parts.append(chapter_compact(
        num="3", title="Настройка инфраструктуры: боты, каналы, продукты",
        intro="Прежде чем продавать, нужно один раз настроить три сущности: Telegram-бот → закрытый канал → продукт с тарифами. Это занимает 10–15 минут.",
        blocks=[{
            "heading": "3.1 Добавление бота",
            "text": "Бот — «лицо» продукта в Telegram. Через него юзеры заходят, оставляют заявки и получают доступ. Один бот может обслуживать несколько продуктов.",
            "shot": "05_bots.png",
            "caption": "Раздел «Боты». Виден список с количеством каналов и продуктов на каждом.",
            "steps": [
                "Создайте бота в @BotFather, скопируйте токен.",
                "В Grammy: <strong>Каталог → Боты → Добавить бота</strong>, вставьте токен.",
                "Система проверит токен через Telegram API и подхватит имя и username автоматически.",
            ],
        }],
    ))

    parts.append(chapter_compact(
        num="3", title="Настройка инфраструктуры (продолжение)",
        blocks=[
            {
                "heading": "3.2 Добавление канала",
                "text": "Канал — закрытый Telegram-чат или канал, в который вы продаёте доступ. Бот должен быть его администратором с правом приглашать.",
                "shot": "04_channels.png",
                "caption": "Раздел «Каналы». Каждый канал привязан к боту.",
                "steps": [
                    "Создайте закрытый канал в Telegram, добавьте бота как админа с правом «Приглашать».",
                    "В Grammy: <strong>Каталог → Каналы → Добавить канал</strong>, выберите бота и введите ID канала или @username.",
                    "Система проверит, что бот действительно может приглашать в этот канал.",
                ],
            },
            {
                "heading": "3.3 Создание продукта",
                "text": "Продукт — «товар» с тарифами на 3, 6 и 12 месяцев. У продукта уникальный код (для deep-link /start) и привязка к каналу.",
                "shot": "03_products.png",
                "caption": "Раздел «Продукты». Видны цены по тарифам и активные подписки.",
                "steps": [
                    "<strong>Каталог → Продукты → Новый продукт</strong>.",
                    "Заполните название, короткий код (например, <code>club</code>), валюту и три цены.",
                    "Выберите канал — сохраните. Продукт готов к продажам.",
                ],
            },
        ],
    ))

    # Глава 4 — Воронки
    parts.append(chapter(
        num="4", title="Воронки прогрева: Студия",
        intro="Воронка — серия отложенных сообщений, которые бот сам шлёт юзеру после старта. Используется для прогрева к покупке: «дать ценность бесплатно, потом продать».",
        shot="09_funnels_list.png",
        caption="Список воронок. У каждой видно состояние (активна / черновик), число шагов и активных подписчиков.",
        sections=[{
            "heading": "Создать воронку",
            "steps": [
                "<strong>Воронки → Новая воронка</strong>.",
                "Мастер из 4 шагов: выбор продукта → шаблон шагов → название → готово.",
                "После закрытия мастера откроется Студия — главный экран редактирования.",
            ],
        }],
        tip="Шаблоны «welcome», «sales», «nurture» предзаполняют типовые тексты — их можно отредактировать под себя.",
    ))

    parts.append(chapter_compact(
        num="4", title="Студия воронок: 4 секции",
        intro="Студия — главный экран работы с воронкой. Состоит из 4 секций, по которым можно перемещаться через прогресс-бар сверху.",
        blocks=[
            {
                "heading": "4.1 Параметры воронки",
                "shot": "17_funnel_studio.png",
                "caption": "Секция 1: название, описание, продукт, бот, TTL и «отменять при оплате».",
                "steps": [
                    "Задайте читаемое название (например, «Старт · Прогрев 5 дней»).",
                    "Выберите продукт и бота, через которого пойдут сообщения.",
                    "TTL по умолчанию — 90 дней. После этого незавершённые подписчики выходят из воронки.",
                    "Флажок «отменять при оплате» — рекомендуем оставить включённым.",
                ],
            },
            {
                "heading": "4.2 Шаги воронки",
                "shot": "18_funnel_studio_steps.png",
                "caption": "Секция 2: список шагов слева, редактор шага по центру, превью справа.",
                "steps": [
                    "Каждый шаг — это сообщение бота: текст, лидмагнит (опционально), inline-кнопки.",
                    "Задержка задаётся в минутах / часах / днях относительно старта воронки.",
                    "Текст редактируется в Rich-text редакторе: жирный, моноширинный, цитаты, спойлеры, ссылки. Хоткеи <kbd>⌘B</kbd>, <kbd>⌘I</kbd>, <kbd>⌘K</kbd>.",
                    "Справа — превью точно как в Telegram, обновляется в реальном времени.",
                    "Порядок шагов перетаскивается мышкой.",
                ],
            },
        ],
    ))

    parts.append(chapter_compact(
        num="4", title="Студия воронок: точки входа и запуск",
        blocks=[
            {
                "heading": "4.3 Точки входа",
                "shot": "19_funnel_studio_entry_points.png",
                "caption": "Секция 3: tracking-ссылки и кодовые слова.",
                "steps": [
                    "<strong>Trackable Link</strong> — UTM-размеченная ссылка, запускает воронку и считает клики. Создаётся в один клик.",
                    "Кликните по иконке копирования рядом со счётчиком — ссылка в буфере, всплывает зелёный тост.",
                    "<strong>Кодовое слово</strong> — короткое слово (например, «КЛУБ»). Юзер пишет его в чат боту, и воронка стартует. Удобно для эфиров и подкастов.",
                    "<strong>Default для заявок</strong> — если включить, воронка автоматически запускается при оставлении заявки на этот продукт.",
                ],
            },
            {
                "heading": "4.4 Запуск",
                "shot": "22_funnel_studio_launch.png",
                "caption": "Секция 4: активация и тестовый прогон.",
                "steps": [
                    "После проверки — переключатель «Активна». С этого момента воронка работает для всех новых юзеров.",
                    "Перед активацией прогоните тестовый запуск — бот пройдёт всю воронку для вас самого, в реальном времени.",
                    "Тестовые прогоны автоматически исключены из аналитики (помечены как <code>source=manual</code>).",
                ],
            },
        ],
    ))

    # Глава 5 — Лидмагниты
    parts.append(chapter(
        num="5", title="Лидмагниты",
        intro="Лидмагнит — бесплатный PDF, видео, картинка или документ, который бот шлёт юзеру в комплекте с шагом воронки. Создаёт ощущение «получил ценность бесплатно» — повышает доверие и конверсию.",
        shot="10_lead_magnets.png",
        caption="Раздел «Лидмагниты». Видны имя, тип, размер, количество скачиваний.",
        sections=[
            {"heading": "Как загрузить", "steps": [
                "<strong>Воронки → Лидмагниты</strong>.",
                "«+ Новый лидмагнит» или перетащите файл прямо в drop-зону.",
                "Система автоматически определит тип (PDF / image / video / document).",
                "Задайте читаемое имя и (опционально) привяжите к продукту.",
            ]},
            {"heading": "Прикрепить к шагу воронки", "steps": [
                "В Студии воронок откройте нужный шаг.",
                "В блоке «Лидмагнит» выберите файл из выпадающего списка.",
                "В Telegram-превью появится attachment с иконкой типа файла.",
            ]},
        ],
        tip="При первой отправке файла Telegram возвращает <code>file_id</code> — мы его кэшируем. Следующие 1000 отправок того же лидмагнита идут без перезаливки.",
    ))

    # Глава 6 — Точки входа
    parts.append(chapter_compact(
        num="6", title="Точки входа и атрибуция",
        intro="Где будут лежать ссылки на бота, как считать клики и понимать, какие каналы продвижения приводят платящих клиентов.",
        blocks=[
            {
                "heading": "6.1 Tracking-ссылки",
                "text": "У каждой рекламной площадки — своя ссылка с UTM-разметкой. Бот считает клики и уникальных пользователей. В аналитике видна воронка CTR → CR по каждому каналу.",
                "shot": "11_funnel_triggers.png",
                "caption": "Раздел «Кодовые слова». Видны слова, активные/неактивные, число использований.",
                "steps": [
                    "Создайте ссылку прямо в Студии воронки или в карточке продукта.",
                    "Укажите <code>utm_source</code> (instagram / youtube), <code>utm_medium</code> (reels / post), опционально <code>utm_campaign</code>.",
                    "Скопируйте ссылку иконкой слева от счётчика кликов.",
                    "Через 1–2 дня в <strong>Аналитика → Источники</strong> увидите воронку CTR → CR.",
                ],
            },
            {
                "heading": "6.2 Кодовые слова",
                "text": "Если ссылку вставить нельзя (эфир, подкаст) — используйте короткое слово. Уникально на уровне БД: два администратора одновременно не создадут одно и то же слово.",
                "steps": [
                    "<strong>Воронки → Кодовые слова → + Добавить слово</strong>.",
                    "Введите слово без пробелов (например, <code>КЛУБ</code>), привяжите к воронке.",
                    "Скажите в эфире: «Напишите боту слово КЛУБ» — все, кто напишут, попадут в воронку.",
                ],
            },
        ],
    ))

    # Глава 7 — Платежи
    parts.append(chapter_compact(
        num="7", title="Обработка заявок и платежей",
        intro="Заявки ведутся по статусам new → contacted → paid → closed. Платежи могут создаваться вручную или автоматически через Telegram Payments.",
        blocks=[{
            "heading": "7.1 Заявки",
            "shot": "06_leads.png",
            "caption": "Раздел «Заявки». Табы — фильтр по статусу.",
            "steps": [
                "Заявка создаётся, когда юзер нажимает «Оставить заявку» в боте.",
                "В сайдбаре появляется бейдж: «Новых: N».",
                "Менеджер открывает заявку, связывается, меняет статус: new → contacted.",
                "После оплаты статус автоматически становится paid (при создании Payment этому юзеру).",
            ],
        }],
    ))

    parts.append(chapter_compact(
        num="7", title="Обработка заявок и платежей (продолжение)",
        blocks=[
            {
                "heading": "7.2 Ручное создание платежа",
                "shot": "07_payments.png",
                "caption": "Раздел «Платежи».",
                "steps": [
                    "<strong>Продажи → Платежи → Новый платёж</strong>.",
                    "Выбираете пользователя через UserPicker (поиск по @username/имени/TG ID).",
                    "Выбираете продукт, период (3 / 6 / 12 мес), сумму.",
                    "Сохраняете — система создаёт Subscription, генерирует одноразовый invite в канал, отправляет юзеру.",
                ],
            },
            {
                "heading": "7.3 Подписки",
                "shot": "08_subscriptions.png",
                "caption": "Раздел «Подписки». Видны действующие подписки и их сроки.",
                "steps": [
                    "Каждая подписка — active-запись с датой <code>ends_at</code>.",
                    "Worker раз в час проверяет истёкшие подписки, отзывает доступ и шлёт уведомление.",
                    "Подписку можно <strong>продлить</strong> или <strong>отозвать досрочно</strong>.",
                ],
            },
        ],
    ))

    # Глава 8 — Аналитика
    parts.append(chapter(
        num="8", title="Аналитика и метрики",
        intro="Страница «Эффективность» — главный инструмент принятия решений. Динамика во времени, разрез по источникам, две модели атрибуции, конверсия воронок.",
        shot="13_analytics.png",
        caption="Страница /analytics с фильтрами, KPI, графиком, Pareto-таблицей.",
        sections=[{
            "heading": "Как читать страницу",
            "steps": [
                "<strong>Период</strong>: 7 / 30 / 90 дней.",
                "<strong>Атрибуция</strong>: «Последнее касание» — источник последней заявки. «Первое касание» — источник первого захода.",
                "<strong>Разрез</strong>: По источнику / По кампании / По продукту / Без разреза.",
                "<strong>KPI-карточки</strong>: лиды, оплаты, выручка, конверсия лид→оплата.",
                "<strong>Pareto-таблица</strong>: топ источников по выручке.",
            ],
        }],
        tip="Health-блок сверху подсветит «дырявые» данные: низкая атрибуция, много failed-сообщений, юзеры отключили уведомления.",
    ))

    # Глава 9 — Пользователи
    parts.append(chapter(
        num="9", title="Пользователи",
        intro="Раздел /users — реестр всех Telegram-юзеров, которые когда-либо взаимодействовали с ботом. Здесь видны первичные источники и история активности.",
        shot="14_users.png",
        caption="Поиск пользователей по @username, имени или Telegram ID.",
        sections=[{
            "heading": "Что видно в профиле",
            "steps": [
                "Контакты: имя, @username, email, phone, заметки менеджера.",
                "Первичный источник: первый бот, первая ссылка, UTM первой кампании.",
                "Текущая «горячая» атрибуция: последняя tracking-ссылка, активна 30 минут после клика.",
                "История: заявки, платежи, подписки во вкладках.",
                "Флаг «уведомления выключены» — если стоит, бот не шлёт этому юзеру воронки.",
            ],
        }],
    ))

    # Глава 10 — Аудит
    parts.append(chapter(
        num="10", title="Аудит-журнал",
        intro="Любое write-действие администратора (create / update / delete) логируется. Журнал доступен только роли <strong>admin</strong> — менеджеры его не видят.",
        shot="15_audit_log.png",
        caption="Раздел «Аудит-журнал» с фильтрами по администратору, действию и типу ресурса.",
        sections=[{
            "heading": "Как пользоваться",
            "steps": [
                "<strong>Администрирование → Аудит-журнал</strong>.",
                "Фильтруйте: кто (admin), что сделал (create/update/delete), с каким ресурсом (product / funnel / payment / ...).",
                "Раскройте запись — увидите IP, user-agent, payload.",
                "Пароли, токены и секреты автоматически заменены на <code>***</code>.",
            ],
        }],
        tip="Используйте аудит для разбора инцидентов («кто удалил продукт») и compliance.",
    ))

    # Глава 11 — Профиль
    parts.append(chapter(
        num="11", title="Профиль и смена пароля",
        intro="Здесь администратор меняет свой пароль. После смены текущая сессия продолжает работать, но повторный вход потребует новый пароль.",
        shot="16_account.png",
        caption="Страница профиля.",
        sections=[{
            "heading": "Шаги",
            "steps": [
                "Откройте профиль (иконка шестерёнки в футере сайдбара).",
                "Введите текущий пароль (защита от перехвата сессии).",
                "Введите новый пароль дважды.",
                "Сохраните.",
            ],
        }],
    ))

    # Глава 12 — Мобильный — отдельная функция со спец-раскладкой
    parts.append(chapter_mobile())

    # Глава 13 — Сценарии
    parts.append(chapter(
        num="13", title="Типичные сценарии",
        intro="Подборка частых задач с указанием, в каких разделах их решать.",
        sections=[
            {"heading": "Сценарий 1. Запуск нового продукта с нуля", "steps": [
                "Каталог → Боты: добавить бота.",
                "Каталог → Каналы: добавить канал.",
                "Каталог → Продукты: создать продукт, привязать к каналу.",
                "Воронки → Новая воронка → выбрать продукт → шаблон.",
                "В Студии: настроить шаги, добавить лидмагниты, активировать.",
                "В Точках входа: создать tracking-ссылку под канал продвижения.",
                "Разместить ссылку в Instagram / YouTube / Telegram-чате.",
                "Через 1–2 дня — Аналитика → Эффективность.",
            ]},
            {"heading": "Сценарий 2. Реактивация просроченных подписок", "steps": [
                "Продажи → Подписки → фильтр <code>status=expired</code>.",
                "Скачать CSV (в правом верхнем углу).",
                "Связаться с клиентами, предложить продлить.",
                "При продлении создать платёж — подписка продлевается автоматически.",
            ]},
            {"heading": "Сценарий 3. A/B-тест двух ссылок", "steps": [
                "Создать 2 tracking-ссылки с разными <code>utm_content</code> (A и B).",
                "Разместить в чередующихся постах / Reels.",
                "Аналитика → разрез «По кампании».",
                "Через 7 дней — сравнить CVR.",
            ]},
            {"heading": "Сценарий 4. Расследование «кто и когда правил воронку»", "steps": [
                "Администрирование → Аудит-журнал.",
                "Фильтр: resource_type=funnel, action=update.",
                "Видны все правки с автором, временем, IP.",
                "Раскрыть payload — что именно поменяли.",
            ]},
        ],
        tip="Если что-то идёт не так — Health-блок в Аналитике первым подскажет, что чинить.",
    ))

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Grammy — Руководство пользователя</title>
<style>{CSS}</style>
</head>
<body>
{''.join(parts)}
</body>
</html>"""


def main():
    html = build_html()
    OUT_HTML.write_text(html, encoding="utf-8")
    size_kb = OUT_HTML.stat().st_size // 1024
    print(f"✓ HTML собрано: {OUT_HTML} ({size_kb} KB)")
    print("Рендер: node docs/proposal/html_to_pdf.js Grammy_Guide.html Grammy_Guide.pdf --guide")


if __name__ == "__main__":
    main()
