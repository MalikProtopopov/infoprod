"""
Собирает HTML КП (коммерческого предложения) для Grammy.

Запуск:
  python3 docs/proposal/build_proposal_html.py

Выход:
  docs/proposal/Grammy_KP.html

Далее HTML конвертируется в PDF через html_to_pdf.js (Playwright).
Стиль — слайдовая презентация в A4 landscape, бренд indigo→rose.
"""
from __future__ import annotations

import base64
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent
SHOTS_DIR = OUT_DIR / "screenshots"
OUT_HTML = OUT_DIR / "Grammy_KP.html"

HOURLY_RATE = 3500


def img_b64(name: str) -> str:
    """Возвращает data:image/png;base64,... для встраивания png в HTML."""
    p = SHOTS_DIR / name
    if not p.exists():
        return ""
    return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode("ascii")


# Используем оригинальный SVG-винил из admin/app/icon.svg (но компактнее)
VINYL_SVG = """
<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:100%">
  <defs>
    <radialGradient id="d" cx="50%" cy="50%" r="55%">
      <stop offset="0%" stop-color="#1e1b4b"/>
      <stop offset="70%" stop-color="#0f0a2e"/>
      <stop offset="100%" stop-color="#050314"/>
    </radialGradient>
    <linearGradient id="l" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#818cf8"/>
      <stop offset="55%" stop-color="#6366f1"/>
      <stop offset="100%" stop-color="#f43f5e"/>
    </linearGradient>
  </defs>
  <circle cx="32" cy="32" r="30" fill="url(#d)"/>
  <g stroke="#fff" fill="none" stroke-width="0.35">
    <circle cx="32" cy="32" r="26" opacity=".10"/>
    <circle cx="32" cy="32" r="23" opacity=".10"/>
    <circle cx="32" cy="32" r="20" opacity=".10"/>
    <circle cx="32" cy="32" r="17" opacity=".10"/>
  </g>
  <path d="M 32 3 A 29 29 0 0 1 61 32" stroke="#fff" stroke-width="0.8" fill="none" opacity=".18" stroke-linecap="round"/>
  <circle cx="32" cy="32" r="11.5" fill="url(#l)"/>
  <circle cx="32" cy="32" r="11.5" fill="none" stroke="#fff" stroke-width="0.4" opacity=".25"/>
  <circle cx="32" cy="32" r="1.6" fill="#050314"/>
</svg>
""".strip()

# ─────────────────────────────────────────────────────────────────────────────

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
@page { size: A4 landscape; margin: 0; }

html, body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Inter", Helvetica, Arial, sans-serif;
  font-size: 14px;
  color: #1e1b4b;
  background: #fff;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}

.slide {
  width: 297mm;
  height: 210mm;
  padding: 22mm 24mm;
  position: relative;
  page-break-after: always;
  overflow: hidden;
}
.slide:last-child { page-break-after: auto; }

.slide.dark {
  background: radial-gradient(circle at 18% 28%, #2a2566 0%, #0f0a2e 55%, #050314 100%);
  color: #fff;
}
.slide.brand-band::before {
  content: "";
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 8mm;
  background: linear-gradient(180deg, #6366f1 0%, #f43f5e 100%);
}

h1.slide-title {
  font-size: 28pt; font-weight: 800; letter-spacing: -0.8px;
  color: #1e1b4b; margin-bottom: 6mm;
}
.slide.dark h1.slide-title { color: #fff; }
h2.section { font-size: 12pt; text-transform: uppercase; letter-spacing: 2px;
  color: #6b7280; font-weight: 600; margin-bottom: 6mm; }
.slide.dark h2.section { color: #a5b4fc; }
p.lead { font-size: 16pt; line-height: 1.45; color: #374151; max-width: 220mm; }
.slide.dark p.lead { color: #e5e7eb; }

/* Cover */
.cover { display: flex; flex-direction: column; justify-content: center; padding: 30mm 28mm; }
.cover .logo { width: 32mm; height: 32mm; margin-bottom: 12mm; }
.cover h1 {
  font-size: 64pt; font-weight: 900; letter-spacing: -3px;
  background: linear-gradient(135deg, #fff 0%, #c7d2fe 60%, #fda4af 100%);
  -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; color: transparent;
  margin-bottom: 4mm;
}
.cover .tagline { font-size: 18pt; color: #c7d2fe; max-width: 200mm; line-height: 1.4; margin-bottom: 14mm; font-weight: 400; }
.cover .meta { color: #818cf8; font-size: 11pt; letter-spacing: 1px; text-transform: uppercase; }

/* Footer page number */
.footer {
  position: absolute; left: 24mm; right: 24mm; bottom: 10mm;
  display: flex; align-items: center; justify-content: space-between;
  font-size: 9pt; color: #9ca3af;
}
.slide.dark .footer { color: #6366f1; }
.footer .brand { display: flex; align-items: center; gap: 5px; font-weight: 600; letter-spacing: 1px; }
.footer .brand-mark { width: 14px; height: 14px; }

/* Grids */
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12mm; margin-top: 8mm; }
.grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8mm; margin-top: 8mm; }
.grid-4 { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 6mm; margin-top: 8mm; }

.card {
  padding: 8mm; border-radius: 4mm; background: #fff;
  border: 1px solid #e5e7eb;
}
.slide.dark .card { background: rgba(255,255,255,0.06); border-color: rgba(255,255,255,0.10); }
.card h3 {
  font-size: 13pt; font-weight: 700; margin-bottom: 3mm;
  color: #1e1b4b;
}
.slide.dark .card h3 { color: #fff; }
.card .desc { color: #4b5563; font-size: 11pt; line-height: 1.5; }
.slide.dark .card .desc { color: #d1d5db; }
.card .kpi { font-size: 28pt; font-weight: 800; line-height: 1; color: #6366f1; margin-bottom: 2mm; }
.card .kpi-label { font-size: 10pt; text-transform: uppercase; letter-spacing: 1px; color: #6b7280; }

/* Pricing */
.pricing-card {
  padding: 8mm 7mm; border-radius: 5mm; background: #fff;
  border: 1px solid #e5e7eb; position: relative;
}
.pricing-card.featured {
  border: 2px solid #6366f1;
  box-shadow: 0 12px 32px -16px rgba(99,102,241,0.6);
}
.pricing-card .pkg-name {
  font-size: 11pt; text-transform: uppercase; letter-spacing: 2px; color: #6366f1;
  font-weight: 700; margin-bottom: 2mm;
}
.pricing-card .pkg-price {
  font-size: 26pt; font-weight: 800; color: #1e1b4b; line-height: 1; margin-bottom: 1mm;
}
.pricing-card .pkg-hours {
  font-size: 9.5pt; color: #6b7280; margin-bottom: 4mm;
}
.pricing-card ul { list-style: none; padding: 0; }
.pricing-card li { padding: 1.2mm 0; font-size: 10pt; color: #374151; display: flex; gap: 6px; }
.pricing-card li::before { content: "✓"; color: #10b981; font-weight: 700; }
.pricing-card .badge {
  position: absolute; top: -3mm; right: 6mm; background: #6366f1; color: #fff;
  font-size: 8pt; padding: 1.5mm 3mm; border-radius: 10mm; font-weight: 700;
  text-transform: uppercase; letter-spacing: 1px;
}

/* Feature row */
.feature-row { display: grid; grid-template-columns: 0.85fr 1.15fr; gap: 12mm; align-items: center; height: calc(210mm - 22mm - 22mm - 18mm); }
.feature-row .shot { border-radius: 4mm; overflow: hidden; box-shadow: 0 20px 40px -20px rgba(15,10,46,0.4); }
.feature-row .shot img { width: 100%; height: 100%; object-fit: cover; display: block; }
.feature-list { list-style: none; padding: 0; }
.feature-list li {
  padding: 2.5mm 0 2.5mm 7mm; font-size: 12pt; line-height: 1.4; color: #374151;
  position: relative;
}
.feature-list li::before {
  content: ""; position: absolute; left: 0; top: 5mm;
  width: 3mm; height: 3mm; background: linear-gradient(135deg, #6366f1, #f43f5e); border-radius: 50%;
}

/* Module grid */
.module-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 4mm; }
.module-card {
  padding: 5mm 5mm 5mm 6mm; border-radius: 3mm; background: #fff;
  border: 1px solid #e5e7eb; position: relative;
}
.module-card .m-id {
  font-size: 9pt; font-weight: 700; color: #6366f1; letter-spacing: 1px;
}
.module-card .m-title {
  font-size: 11pt; font-weight: 700; color: #1e1b4b; margin-top: 1.5mm; line-height: 1.25;
}
.module-card .m-desc {
  font-size: 8.5pt; color: #6b7280; margin-top: 2mm; line-height: 1.35;
}
.module-card .m-hours {
  position: absolute; top: 5mm; right: 5mm; font-size: 9pt; color: #9ca3af; font-weight: 600;
}

/* Roadmap */
.roadmap { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6mm; margin-top: 10mm; }
.phase {
  padding: 8mm; border-radius: 4mm; background: #fff; border-top: 4mm solid;
  border-image: linear-gradient(90deg, #6366f1, #f43f5e) 1;
}
.phase h4 { font-size: 13pt; font-weight: 700; color: #1e1b4b; margin-bottom: 2mm; }
.phase .phase-num { font-size: 9pt; color: #6366f1; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 1mm; }
.phase ul { list-style: disc; padding-left: 5mm; margin-top: 3mm; }
.phase li { font-size: 9.5pt; color: #4b5563; line-height: 1.35; margin-bottom: 1mm; }

/* Big number */
.bignum {
  font-size: 64pt; font-weight: 900; line-height: 1;
  background: linear-gradient(135deg, #6366f1 0%, #f43f5e 100%);
  -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; color: transparent;
}

/* CTA */
.cta-card {
  background: linear-gradient(135deg, #6366f1 0%, #f43f5e 100%);
  border-radius: 6mm; padding: 14mm 16mm; color: #fff; margin-top: 8mm;
}
.cta-card h3 { font-size: 22pt; font-weight: 800; margin-bottom: 4mm; }
.cta-card p { font-size: 13pt; opacity: 0.95; line-height: 1.5; }

/* Architecture diagram (simple svg-free) */
.arch-row { display: flex; gap: 6mm; margin-top: 8mm; }
.arch-box {
  flex: 1; padding: 6mm; border: 1.5px solid #e5e7eb; border-radius: 3mm;
  text-align: center; background: #fff;
}
.arch-box .arch-icon { font-size: 26pt; line-height: 1; margin-bottom: 3mm; }
.arch-box .arch-title { font-size: 11pt; font-weight: 700; color: #1e1b4b; }
.arch-box .arch-desc { font-size: 8.5pt; color: #6b7280; margin-top: 1.5mm; line-height: 1.3; }
"""


# ─────────────────────────────────────────────────────────────────────────────
# Слайды
# ─────────────────────────────────────────────────────────────────────────────

def footer(num: int, total: int, dark: bool = False) -> str:
    cls = "footer"
    return f"""
    <div class="{cls}">
      <div class="brand">
        <span class="brand-mark">{VINYL_SVG}</span>
        <span>GRAMMY</span>
      </div>
      <div>{num} / {total}</div>
      <div>Коммерческое предложение · 2026</div>
    </div>
    """


def slide_cover() -> str:
    # Grammy рисуем как SVG-text с linearGradient fill — это надёжно работает в PDF
    # (background-clip: text у Chromium PDF-renderer'а вылазит белым прямоугольником).
    return f"""
    <section class="slide dark cover">
      <div class="logo">{VINYL_SVG}</div>
      <div class="meta">Коммерческое предложение</div>
      <svg width="600" height="110" viewBox="0 0 600 110" xmlns="http://www.w3.org/2000/svg"
           style="width: 200mm; height: auto; display: block; margin-bottom: 4mm;">
        <defs>
          <linearGradient id="grammyGrad" gradientUnits="userSpaceOnUse"
                          x1="0" y1="0" x2="600" y2="110">
            <stop offset="0%" stop-color="#ffffff"/>
            <stop offset="55%" stop-color="#c7d2fe"/>
            <stop offset="100%" stop-color="#fda4af"/>
          </linearGradient>
        </defs>
        <text x="0" y="92"
              font-family="Helvetica, Arial, sans-serif"
              font-weight="900" font-size="108"
              fill="url(#grammyGrad)">Grammy</text>
      </svg>
      <p class="tagline">SaaS-платформа для продажи доступа в закрытые Telegram-каналы. Боты, воронки прогрева, аналитика и наблюдаемость в одной системе.</p>
      <div class="meta" style="position:absolute; bottom: 18mm; left: 28mm;">
        Подготовлено для заказчика · 2026
      </div>
    </section>
    """


def slide_problem(num: int, total: int) -> str:
    return f"""
    <section class="slide brand-band">
      <h2 class="section">Контекст</h2>
      <h1 class="slide-title">Инфобиз превращается в инфраструктурный продукт</h1>
      <div class="grid-2" style="margin-top: 12mm;">
        <div>
          <p class="lead" style="font-size: 14pt;">
            Эксперт продаёт доступ в закрытый Telegram-канал. Тысячи кликов из Instagram,
            YouTube, рассылок и эфиров. Конверсия требует: атрибуции каждого касания,
            прогрева воронкой, моментальной выдачи доступа после оплаты,
            автоматического отзыва по истечении подписки.
          </p>
        </div>
        <div>
          <p class="lead" style="font-size: 14pt;">
            Сделать это руками — невозможно. Готовых SaaS под русский Telegram-инфобиз —
            нет. Grammy решает эту задачу целиком: от подключения бота до Pareto-отчёта
            по UTM-кампаниям и алертов на падение бэкенда.
          </p>
        </div>
      </div>
      <div class="grid-4" style="margin-top: 14mm;">
        <div class="card"><div class="kpi">15</div><div class="kpi-label">сущностей в БД</div></div>
        <div class="card"><div class="kpi">~80</div><div class="kpi-label">API-эндпоинтов</div></div>
        <div class="card"><div class="kpi">21</div><div class="kpi-label">экран в админке</div></div>
        <div class="card"><div class="kpi">500+</div><div class="kpi-label">автоматических тестов</div></div>
      </div>
      {footer(num, total)}
    </section>
    """


def slide_architecture(num: int, total: int) -> str:
    return f"""
    <section class="slide brand-band">
      <h2 class="section">Архитектура решения</h2>
      <h1 class="slide-title">Четыре слоя · единая система</h1>
      <div class="arch-row">
        <div class="arch-box">
          <div class="arch-icon">🌐</div>
          <div class="arch-title">Admin Panel</div>
          <div class="arch-desc">Next.js 15 · React 19 · TailwindCSS · SWR · Recharts</div>
        </div>
        <div class="arch-box">
          <div class="arch-icon">⚙️</div>
          <div class="arch-title">Backend API</div>
          <div class="arch-desc">FastAPI · SQLAlchemy 2.0 async · Alembic · structlog</div>
        </div>
        <div class="arch-box">
          <div class="arch-icon">🤖</div>
          <div class="arch-title">Telegram-боты</div>
          <div class="arch-desc">aiogram 3.x · multi-bot polling · APScheduler workers</div>
        </div>
        <div class="arch-box">
          <div class="arch-icon">📊</div>
          <div class="arch-title">Observability</div>
          <div class="arch-desc">Prometheus · Grafana · Loki · Alertmanager · Sentry</div>
        </div>
      </div>
      <div class="grid-2" style="margin-top: 14mm;">
        <div>
          <h3 style="font-size: 14pt; font-weight: 700; color: #1e1b4b; margin-bottom: 4mm;">Инфраструктура</h3>
          <ul class="feature-list">
            <li>Один docker-compose → весь стек на любом VPS</li>
            <li>Let's Encrypt + автопродление сертификатов</li>
            <li>Автоматические миграции БД при деплое</li>
            <li>Daily Docker cache cleanup (не забивает диск)</li>
          </ul>
        </div>
        <div>
          <h3 style="font-size: 14pt; font-weight: 700; color: #1e1b4b; margin-bottom: 4mm;">Безопасность</h3>
          <ul class="feature-list">
            <li>JWT в HttpOnly Secure cookie</li>
            <li>RBAC: 3 роли (admin / manager / viewer)</li>
            <li>Аудит-журнал всех изменений с маскированием секретов</li>
            <li>Rate-limit на /login, gitleaks в CI</li>
          </ul>
        </div>
      </div>
      {footer(num, total)}
    </section>
    """


def slide_feature(num: int, total: int, *, title: str, kicker: str, shot: str, points: list[str], note: str = "") -> str:
    shot_data = img_b64(shot)
    return f"""
    <section class="slide brand-band">
      <h2 class="section">{kicker}</h2>
      <h1 class="slide-title">{title}</h1>
      <div class="feature-row">
        <div class="shot"><img src="{shot_data}" alt=""/></div>
        <div>
          <ul class="feature-list">
            {''.join(f'<li>{p}</li>' for p in points)}
          </ul>
          {f'<p style="margin-top: 8mm; font-size: 10pt; color: #6b7280; font-style: italic;">{note}</p>' if note else ''}
        </div>
      </div>
      {footer(num, total)}
    </section>
    """


def slide_modules(num: int, total: int, modules: list[dict]) -> str:
    cards = "".join(
        f"""
        <div class="module-card">
          <div class="m-hours">{m['hours']} ч</div>
          <div class="m-id">{m['id']}</div>
          <div class="m-title">{m['title']}</div>
          <div class="m-desc">{m['desc']}</div>
        </div>
        """ for m in modules
    )
    return f"""
    <section class="slide brand-band">
      <h2 class="section">Полная функциональная карта</h2>
      <h1 class="slide-title">16 модулей · гибкая комплектация</h1>
      <div class="module-grid">{cards}</div>
      <p style="font-size: 10pt; color: #6b7280; margin-top: 8mm;">Каждый модуль — независимый блок: ФТ, User Flow, Use Cases, оценка по фронту/бэку/QA/дизайну. Можно отгрузить пакетом или дозаказать позже.</p>
      {footer(num, total)}
    </section>
    """


def slide_pricing(num: int, total: int, packages: list[dict]) -> str:
    cards = ""
    for p in packages:
        featured = ' featured' if p.get('featured') else ''
        badge = '<div class="badge">Рекомендуется</div>' if p.get('featured') else ''
        feats = "".join(f'<li>{f}</li>' for f in p['features'])
        cards += f"""
        <div class="pricing-card{featured}">
          {badge}
          <div class="pkg-name">{p['name']}</div>
          <div class="pkg-price">{p['price']:,} ₽</div>
          <div class="pkg-hours">{p['hours']} часов · фикс или поэтапно</div>
          <ul>{feats}</ul>
        </div>
        """.replace(",", " ")
    return f"""
    <section class="slide brand-band">
      <h2 class="section">Стоимость</h2>
      <h1 class="slide-title">Три пакета комплектации</h1>
      <div class="grid-3">{cards}</div>
      <p style="font-size: 10pt; color: #6b7280; margin-top: 8mm;">
        Ставка: {HOURLY_RATE:,} ₽/час (всё включено: разработка, дизайн, QA, DevOps).
        Оплата поэтапно: 30% при старте · 40% на промежуточной приёмке · 30% при сдаче.
        Все цены без НДС.
      </p>
      {footer(num, total)}
    </section>
    """.replace(",", " ")


def slide_roadmap(num: int, total: int) -> str:
    return f"""
    <section class="slide brand-band">
      <h2 class="section">Дорожная карта</h2>
      <h1 class="slide-title">Поставка по фазам · 12 недель до полного релиза</h1>
      <div class="roadmap">
        <div class="phase">
          <div class="phase-num">Фаза 1 · нед. 1–3</div>
          <h4>Фундамент</h4>
          <ul>
            <li>Инфраструктура (M01)</li>
            <li>Аутентификация + RBAC (M02)</li>
            <li>Каталог продуктов / каналов / ботов (M03)</li>
            <li>Базовый UI/UX и брендинг (M12, M13)</li>
          </ul>
        </div>
        <div class="phase">
          <div class="phase-num">Фаза 2 · нед. 4–6</div>
          <h4>Продажи</h4>
          <ul>
            <li>Telegram-бот (M11)</li>
            <li>Пользователи (M04)</li>
            <li>Заявки (M05)</li>
            <li>Платежи и подписки (M06)</li>
          </ul>
        </div>
        <div class="phase">
          <div class="phase-num">Фаза 3 · нед. 7–10</div>
          <h4>Автоматизация</h4>
          <ul>
            <li>Воронки и Студия (M07)</li>
            <li>Лидмагниты (M08)</li>
            <li>Точки входа (M09)</li>
            <li>Аналитика (M10)</li>
          </ul>
        </div>
        <div class="phase">
          <div class="phase-num">Фаза 4 · нед. 11–12</div>
          <h4>Качество</h4>
          <ul>
            <li>Observability и алерты (M15)</li>
            <li>Аудит-журнал (M14)</li>
            <li>Полное покрытие тестами и CI/CD (M16)</li>
            <li>Передача в эксплуатацию</li>
          </ul>
        </div>
      </div>
      {footer(num, total)}
    </section>
    """


def slide_guarantees(num: int, total: int) -> str:
    return f"""
    <section class="slide brand-band">
      <h2 class="section">Что входит в стоимость</h2>
      <h1 class="slide-title">Не «голый код», а production-ready продукт</h1>
      <div class="grid-2" style="margin-top: 10mm;">
        <div>
          <ul class="feature-list">
            <li>Исходный код в Git-репозитории под управление заказчика</li>
            <li>Развёртывание на сервере заказчика «под ключ»</li>
            <li>SSL и автопродление сертификата</li>
            <li>Документация: ТЗ, гайд по использованию, ADR</li>
            <li>Обучающая сессия с командой заказчика (2 часа)</li>
          </ul>
        </div>
        <div>
          <ul class="feature-list">
            <li>Полное покрытие тестами критичных модулей (Премиум)</li>
            <li>CI/CD pipeline в GitHub Actions</li>
            <li>Гарантия на исправление багов: 3 месяца после сдачи</li>
            <li>Мониторинг и алерты «из коробки» (Стандарт+)</li>
            <li>Опция сопровождения: 5 000 ₽/мес/час на бэклог</li>
          </ul>
        </div>
      </div>
      <div class="cta-card">
        <h3>Готовы стартовать?</h3>
        <p>Подписываем рамочный договор, фиксируем выбранный пакет и плановый Бюджет.
        Начинаем Фазу 1 в течение 3 рабочих дней.</p>
      </div>
      {footer(num, total)}
    </section>
    """


def slide_contact(num: int, total: int) -> str:
    return f"""
    <section class="slide dark">
      <h2 class="section">Контакты</h2>
      <h1 class="slide-title" style="font-size: 36pt;">Обсудим детали?</h1>
      <p class="lead" style="margin-top: 8mm; max-width: 200mm;">
        Я готов созвониться и пройтись по техническому заданию модуль за модулем,
        ответить на вопросы по архитектуре, срокам и приоритизации.
      </p>
      <div class="grid-2" style="margin-top: 16mm;">
        <div>
          <h3 style="font-size: 14pt; font-weight: 700; color: #fff; margin-bottom: 4mm;">Что я пришлю после звонка</h3>
          <ul class="feature-list" style="color: #d1d5db;">
            <li style="color: #e5e7eb;">Финальный пакет ТЗ + смета (Excel)</li>
            <li style="color: #e5e7eb;">Договор с фиксированной ценой и сроком</li>
            <li style="color: #e5e7eb;">Доступ к dev-стенду для приёмки промежуточных результатов</li>
          </ul>
        </div>
        <div>
          <h3 style="font-size: 14pt; font-weight: 700; color: #fff; margin-bottom: 4mm;">Связь</h3>
          <p style="font-size: 14pt; color: #c7d2fe; line-height: 1.7;">
            Email: <br/>
            Telegram: <br/>
            Сайт: mediann.dev
          </p>
        </div>
      </div>
      <div style="position: absolute; left: 24mm; bottom: 12mm; width: 28mm; height: 28mm;">{VINYL_SVG}</div>
      <div class="footer" style="color: #6366f1;">
        <div class="brand"><span class="brand-mark">{VINYL_SVG}</span><span>GRAMMY</span></div>
        <div>{num} / {total}</div>
        <div>Спасибо за внимание</div>
      </div>
    </section>
    """


# ─────────────────────────────────────────────────────────────────────────────
# Контент модулей и пакетов
# ─────────────────────────────────────────────────────────────────────────────

MODULES_BRIEF = [
    {"id": "M01", "title": "Платформа", "desc": "Docker, Postgres, Nginx, SSL, авточистка кэша.", "hours": 39},
    {"id": "M02", "title": "Аутентификация и RBAC", "desc": "JWT в cookie, 3 роли, rate-limit на login.", "hours": 46},
    {"id": "M03", "title": "Каталог", "desc": "Боты, каналы, продукты с тарифами 3/6/12 мес.", "hours": 69},
    {"id": "M04", "title": "Пользователи", "desc": "Идемпотентный first-touch, профиль с историей.", "hours": 40},
    {"id": "M05", "title": "Заявки", "desc": "Лидоприём с FSM статусов + CSV экспорт.", "hours": 37},
    {"id": "M06", "title": "Платежи и подписки", "desc": "Авто-выдача доступа, Telegram Payments.", "hours": 79},
    {"id": "M07", "title": "Воронки (Студия)", "desc": "Drag-n-drop шагов, rich-text TG HTML, превью.", "hours": 201},
    {"id": "M08", "title": "Лидмагниты", "desc": "Drag-n-drop upload, file_id кэш для скорости.", "hours": 38},
    {"id": "M09", "title": "Точки входа", "desc": "Tracking-ссылки с UTM, кодовые слова.", "hours": 58},
    {"id": "M10", "title": "Аналитика", "desc": "Timeline, Pareto, last/first-touch, health.", "hours": 137},
    {"id": "M11", "title": "Telegram-бот", "desc": "Multi-bot polling, deep-link, crash isolation.", "hours": 52},
    {"id": "M12", "title": "UI/UX (база)", "desc": "Sidebar v2, Toast, glass-стиль, mobile.", "hours": 88},
    {"id": "M13", "title": "Брендинг и SEO", "desc": "Favicon-винил, OG, manifest, robots noindex.", "hours": 23},
    {"id": "M14", "title": "Аудит-журнал", "desc": "Лог действий с маской секретов, RBAC=admin.", "hours": 40},
    {"id": "M15", "title": "Observability", "desc": "Prometheus, Grafana, Loki, Alertmanager.", "hours": 43},
    {"id": "M16", "title": "QA и CI/CD", "desc": "~500 авто-тестов, GitHub Actions, pre-commit.", "hours": 148},
]

# Считаем пакеты ровно по той же логике, что в смете
def _hours_for(option: str, ids: list[str]) -> int:
    return sum(m['hours'] for m in MODULES_BRIEF if m['id'] in ids)

BASE_IDS = ["M01","M02","M03","M04","M05","M06","M11","M12","M13"]
STD_IDS  = BASE_IDS + ["M07","M08","M09","M10","M15"]
PRM_IDS  = STD_IDS + ["M14","M16"]

PACKAGES_DATA = [
    {
        "name": "Базовый · MVP",
        "hours": _hours_for("base", BASE_IDS),
        "price": _hours_for("base", BASE_IDS) * HOURLY_RATE,
        "features": [
            "Подключение ботов, каналов, продуктов",
            "Заявки и ручное создание платежей",
            "Авто-выдача доступа после оплаты",
            "Базовая админка + брендинг",
            "Telegram-бот с deep-link и /start",
            "Развёртывание под ключ, SSL",
        ],
    },
    {
        "name": "Стандарт",
        "hours": _hours_for("std", STD_IDS),
        "price": _hours_for("std", STD_IDS) * HOURLY_RATE,
        "featured": True,
        "features": [
            "Всё из «Базового»",
            "Воронки прогрева + Студия с превью",
            "Лидмагниты с drag-n-drop",
            "Tracking-ссылки и кодовые слова",
            "Полная страница аналитики с Recharts",
            "Observability: метрики, логи, алерты",
        ],
    },
    {
        "name": "Премиум",
        "hours": _hours_for("prm", PRM_IDS),
        "price": _hours_for("prm", PRM_IDS) * HOURLY_RATE,
        "features": [
            "Всё из «Стандарта»",
            "Аудит-журнал с маскированием секретов",
            "~500 автотестов (backend + frontend + e2e)",
            "GitHub Actions CI/CD",
            "Pre-commit + security сканирование",
            "Гарантия исправления багов 3 мес.",
        ],
    },
]


# ─────────────────────────────────────────────────────────────────────────────

def build_html() -> str:
    total = 11  # количество слайдов
    parts = [
        f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Grammy — Коммерческое предложение</title>
<style>{CSS}</style>
</head>
<body>""",
        slide_cover(),  # 1
        slide_problem(2, total),
        slide_architecture(3, total),
        slide_feature(
            4, total,
            kicker="Ключевая фича · Студия воронок",
            title="Прогрев на автопилоте",
            shot="17_funnel_studio.png",
            points=[
                "4-секционный конструктор: параметры → шаги → точки входа → запуск",
                "Drag-n-drop переупорядочивания шагов",
                "Rich-text редактор под весь Telegram HTML (жирный, моноширинный, цитаты, спойлеры)",
                "Real-time превью точно как в Telegram",
                "Защита активных воронок: warning с числом затронутых подписчиков",
            ],
            note="Скриншот: реальная Студия воронок на проде grammy.mediann.dev",
        ),
        slide_feature(
            5, total,
            kicker="Ключевая фича · Аналитика",
            title="Видно, что окупается",
            shot="13_analytics.png",
            points=[
                "Динамика лидов / оплат / выручки за 7 / 30 / 90 дней",
                "Разрез по источникам, кампаниям, продуктам",
                "Атрибуция: last-touch ↔ first-touch одним кликом",
                "Pareto-топ источников с CVR и выручкой",
                "Health-блок предупреждает о «дырявых» данных",
            ],
            note="Composite SQL индексы + DISTINCT-подзапросы. Страница на 1000+ оплат за 30 дней — менее 2 секунд.",
        ),
        slide_feature(
            6, total,
            kicker="Ключевая фича · Точки входа",
            title="Каждая ссылка — отдельный канал",
            shot="19_funnel_studio_entry_points.png",
            points=[
                "Auto-gen 8-символьный slug или custom 4–64",
                "UTM-разметка: source / medium / campaign / content",
                "Уникальный индекс на lower(word) для кодовых слов — закрыт race condition",
                "Счётчики кликов и уникальных юзеров на каждую ссылку",
                "Копирование в один клик с тостом «Ссылка скопирована»",
            ],
        ),
        slide_modules(7, total, MODULES_BRIEF),
        slide_pricing(8, total, PACKAGES_DATA),
        slide_roadmap(9, total),
        slide_guarantees(10, total),
        slide_contact(11, total),
        "</body></html>",
    ]
    return "".join(parts)


def main():
    html = build_html()
    OUT_HTML.write_text(html, encoding="utf-8")
    size_kb = OUT_HTML.stat().st_size // 1024
    print(f"✓ HTML собрано: {OUT_HTML} ({size_kb} KB)")


if __name__ == "__main__":
    main()
