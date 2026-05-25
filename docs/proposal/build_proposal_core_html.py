"""
Core-версия КП: только то, что заказчик просил, с явными опциями расширения.

Выход: docs/proposal/Grammy_KP_Core.html → Grammy_KP_Core.pdf

Цены:
  Core (сейчас)                        — 125 000 ₽
  Скидка 10% при участии в кейсе       — 112 500 ₽
  + Опция А: Прогрев и автоматизация   +150 000 ₽
  + Опция Б: Аналитика                 +70 000 ₽
  + Опция В: Наблюдаемость и качество  +100 000 ₽
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import build_proposal_html as bp

CORE_PRICE = 125_000
CORE_PRICE_CASE = 112_500  # –10% при участии в кейсе

UPGRADES = [
    {
        "name": "Прогрев и автоматизация",
        "modules": "M07 · M08 · M09",
        "price": 150_000,
        "weeks": "2–3 недели",
        "items": [
            "Воронки прогрева: серия отложенных сообщений с лидмагнитами",
            "Студия редактирования с drag-n-drop, rich-text Telegram HTML и превью",
            "Лидмагниты (PDF / видео / документ) с кэшем file_id для скорости",
            "Tracking-ссылки с UTM, кодовые слова для запуска из эфиров",
        ],
    },
    {
        "name": "Аналитика и метрики",
        "modules": "M10",
        "price": 70_000,
        "weeks": "1 неделя",
        "items": [
            "Страница «Эффективность» с фильтрами период / разрез / атрибуция",
            "Recharts: динамика лидов / оплат / выручки по дням",
            "Pareto-таблица топа источников с CVR",
            "Health-блок с предупреждениями о «дырявых» данных",
        ],
    },
    {
        "name": "Наблюдаемость и качество",
        "modules": "M14 · M15 · M16",
        "price": 100_000,
        "weeks": "1–2 недели",
        "items": [
            "Аудит-журнал всех действий с маскированием секретов",
            "Prometheus + Grafana + Loki с алертами при сбоях",
            "Автотесты ключевых сценариев + GitHub Actions CI",
            "Pre-commit hooks с проверкой секретов (gitleaks)",
        ],
    },
]

# Бизнес-карточки (вместо тех-модулей M01-M13) для слайда 6
BUSINESS_VALUES = [
    {
        "icon": "inbox",
        "title": "Ни одна заявка не теряется",
        "desc": "Каждая заявка из бота попадает в админку и подсвечивается оранжевым бейджем в сайдбаре. Менеджер видит её в течение секунд.",
    },
    {
        "icon": "invite",
        "title": "Никаких ручных приглашений",
        "desc": "Менеджер фиксирует оплату — бот сам генерирует одноразовую invite-ссылку с TTL равным сроку подписки. Клиент в канале за 5 секунд.",
    },
    {
        "icon": "kick",
        "title": "Подписки не висят вечно",
        "desc": "Worker раз в час проверяет истёкшие подписки и автоматически удаляет клиента из канала с уведомлением о продлении.",
    },
    {
        "icon": "profile",
        "title": "Менеджер знает, с кем говорит",
        "desc": "В профиле клиента — контакты, история заявок и платежей, прошлые подписки. Никаких «вспомни, кто это».",
    },
    {
        "icon": "tariffs",
        "title": "Гибкие тарифы",
        "desc": "Каждый продукт имеет цены на 3, 6 и 12 месяцев. При повторной оплате до истечения — срок продлевается, а не дублируется.",
    },
    {
        "icon": "scale",
        "title": "Любое число ботов и каналов",
        "desc": "Один продукт — один канал — один бот. Хотите запустить второй — добавляете через админку, без правок кода и деплоя.",
    },
    {
        "icon": "lock",
        "title": "Безопасно и закрыто",
        "desc": "JWT + HTTPS, защита от подбора пароля, маскирование секретов в логах, авто-продление SSL. От поисковиков закрыто.",
    },
    {
        "icon": "mobile",
        "title": "Работает со смартфона",
        "desc": "Адаптивный интерфейс. Менеджер обрабатывает заявки и фиксирует оплаты прямо с телефона, на встрече или в метро.",
    },
]

# Таблица апселов на слайд 8: каждый столбец = независимый апсел, продаётся отдельно.
# Галочка стоит только в столбце того апсела, который реально содержит эту фичу.
COMPARISON_FEATURES = [
    # (категория, фичи: [(описание, base, plus_funnel, plus_analytics, plus_quality)])
    ("Базовое — входит в Core", [
        ("Бот принимает заявки от клиентов",                  True,  False, False, False),
        ("Заявки в админке с фильтром по статусам",           True,  False, False, False),
        ("Ручной ввод платежа администратором",               True,  False, False, False),
        ("Автоматическая выдача доступа в канал",             True,  False, False, False),
        ("Авто-кик при истечении подписки",                   True,  False, False, False),
        ("Профиль клиента с историей",                        True,  False, False, False),
    ]),
    ("Прогрев и трафик — модуль №1", [
        ("Воронки: бот сам греет клиента сообщениями",        False, True,  False, False),
        ("Лидмагниты PDF / видео в воронке",                  False, True,  False, False),
        ("Tracking-ссылки с UTM-метками",                     False, True,  False, False),
        ("Кодовые слова для запуска воронок из эфиров",       False, True,  False, False),
    ]),
    ("Аналитика — модуль №2", [
        ("Видно, какой канал продвижения окупается",          False, False, True,  False),
        ("Графики динамики лидов / оплат / выручки",          False, False, True,  False),
        ("Pareto-таблица топа источников",                    False, False, True,  False),
        ("Атрибуция Last-touch ↔ First-touch",                False, False, True,  False),
    ]),
    ("Качество и безопасность — модуль №3", [
        ("Аудит-журнал действий админов",                     False, False, False, True),
        ("Метрики и алерты при сбоях бэкенда",                False, False, False, True),
        ("Автотесты + CI/CD",                                 False, False, False, True),
    ]),
]


# ─────────────────────────────────────────────────────────────────────────────
# Override CSS — патчим .shot (убираем серый ореол), даём SVG-иконки и т.п.
# ─────────────────────────────────────────────────────────────────────────────

OVERRIDE_CSS = """
/* Скриншоты — без серого border, тень в брендовом градиенте через ::after */
.feature-row {
  display: grid !important;
  grid-template-columns: 1.45fr 0.85fr !important;
  gap: 14mm !important;
  align-items: center !important;
  height: auto !important;
  margin-top: 6mm;
}
.feature-row .shot {
  position: relative;
  border: none !important;
  box-shadow: none !important;
  background: transparent !important;
  height: auto !important;
  overflow: visible !important;
}
.feature-row .shot::after {
  content: "";
  position: absolute;
  left: 6%; right: 6%; bottom: -3mm;
  height: 10mm;
  background: linear-gradient(135deg, #6366f1 0%, #f43f5e 100%);
  filter: blur(18px);
  opacity: 0.22;
  z-index: -1;
  border-radius: 8mm;
}
.feature-row .shot img {
  width: 100% !important;
  height: auto !important;
  object-fit: contain !important;
  display: block !important;
  background: transparent !important;
  border-radius: 4mm;
  position: relative;
  z-index: 1;
}

/* Иконки в архитектуре — SVG вместо emoji, нейтральный indigo цвет */
.arch-box .arch-svg {
  width: 12mm; height: 12mm; margin: 0 auto 3mm;
  display: flex; align-items: center; justify-content: center;
  color: #6366f1;
}
.arch-box .arch-svg svg { width: 100%; height: 100%; }

/* Бизнес-карточки на 6-м слайде */
.biz-grid {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 5mm;
  margin-top: 8mm;
}
.biz-card {
  padding: 6mm 6mm 5mm; border-radius: 4mm; background: #fff;
  border: 1px solid #e5e7eb; position: relative;
  display: flex; flex-direction: column; gap: 2mm;
}
.biz-card .biz-icon {
  width: 9mm; height: 9mm; border-radius: 50%;
  background: linear-gradient(135deg, #6366f1, #f43f5e);
  color: #fff;
  display: flex; align-items: center; justify-content: center;
  margin-bottom: 2mm;
}
.biz-card .biz-icon svg { width: 5mm; height: 5mm; }
.biz-card h4 {
  font-size: 11pt; font-weight: 700; color: #1e1b4b; line-height: 1.25;
}
.biz-card p {
  font-size: 9pt; color: #4b5563; line-height: 1.4; flex: 1;
}

/* Компактные KPI карточки для слайда 2 */
.kpi-compact { padding: 3.5mm 5mm !important; }
.kpi-compact .kpi { font-size: 17pt !important; line-height: 1.1; }
.kpi-compact .kpi-label { font-size: 8.5pt !important; }

/* Таблица сравнения тарифов — максимально компактная */
.compare-table {
  width: 100%; border-collapse: separate; border-spacing: 0;
  margin-top: 3mm; font-size: 9pt; line-height: 1.2;
}
.compare-table th, .compare-table td {
  padding: 0.7mm 3mm; text-align: left;
  border-bottom: 1px solid #f3f4f6;
  line-height: 1.15;
}
.compare-table th {
  font-size: 8.5pt; text-transform: uppercase; letter-spacing: 0.8px;
  color: #6b7280; font-weight: 600;
  background: #f9fafb; vertical-align: bottom;
  padding-top: 2mm; padding-bottom: 2mm;
}
.compare-table th.pkg-col { text-align: center; min-width: 24mm; }
.compare-table th.pkg-col .pkg-title { color: #1e1b4b; font-size: 10.5pt; letter-spacing: 0; text-transform: none; font-weight: 700; }
.compare-table th.pkg-col .pkg-price { color: #6366f1; font-size: 9pt; margin-top: 0.5mm; font-weight: 600; }
.compare-table th.pkg-col.featured { background: linear-gradient(135deg, rgba(99,102,241,0.10), rgba(244,63,94,0.10)); border-bottom: 2px solid #6366f1; }
.compare-table td.pkg-cell { text-align: center; font-size: 11pt; line-height: 1; }
.compare-table td.feat { font-size: 9pt; color: #374151; line-height: 1.2; }
.compare-table tr.cat-row td {
  background: #eef2ff; color: #4338ca;
  font-size: 8pt; text-transform: uppercase; letter-spacing: 1.2px; font-weight: 700;
  padding: 1.1mm 3mm 0.9mm;
}
.compare-yes { color: #10b981; font-weight: 700; }
.compare-no { color: #d1d5db; }

/* План развития — упрощённый, без серых подложек */
.dev-roadmap {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 5mm;
  margin-top: 8mm;
}
.dev-stage {
  background: #fff; border: 1px solid #e5e7eb; border-radius: 4mm;
  padding: 6mm 5mm; position: relative;
  display: flex; flex-direction: column;
}
.dev-stage .stage-week {
  font-size: 10pt; font-weight: 700; letter-spacing: 1.5px;
  text-transform: uppercase;
  padding: 1.5mm 4mm; border-radius: 999px; display: inline-block;
  align-self: flex-start; margin-bottom: 3mm;
  background: linear-gradient(135deg, #eef2ff, #fce7f3);
  color: #4338ca;
}
.dev-stage h4 { font-size: 12pt; font-weight: 700; color: #1e1b4b; margin-bottom: 1.5mm; }
.dev-stage p { font-size: 9pt; color: #4b5563; line-height: 1.4; flex: 1; }
.dev-stage .stage-price {
  font-size: 10pt; font-weight: 700; margin-top: 3mm;
  padding-top: 2.5mm; border-top: 1px dashed #e5e7eb;
}

/* Модель сотрудничества */
.collab-row {
  display: grid; grid-template-columns: 1fr 1fr; gap: 6mm;
  margin-top: 8mm;
}
.collab-card {
  background: #f9fafb; border-radius: 4mm; padding: 7mm;
  border: 1px solid #e5e7eb;
}
.collab-card.featured {
  background: linear-gradient(135deg, rgba(99,102,241,0.08), rgba(244,63,94,0.06));
  border-color: #c7d2fe;
}
.collab-card h4 {
  font-size: 13pt; font-weight: 700; color: #1e1b4b; margin-bottom: 3mm;
}
.collab-card p { font-size: 10.5pt; color: #374151; line-height: 1.5; }

/* Усиленная подсветка featured-карточки на слайде цены — gradient-glow вместо синей тени */
.pricing-card.featured {
  position: relative;
  background: linear-gradient(135deg, #6366f1 0%, #f43f5e 100%) !important;
  border: none !important;
  box-shadow: none !important;
  color: #fff !important;
}
.pricing-card.featured::after {
  content: "";
  position: absolute;
  left: 4%; right: 4%; bottom: -6mm;
  height: 18mm;
  background: linear-gradient(135deg, #6366f1 0%, #f43f5e 100%);
  filter: blur(28px);
  opacity: 0.35;
  z-index: -1;
  border-radius: 12mm;
}
.pricing-card.featured .pkg-name {
  color: rgba(255,255,255,0.92) !important;
}
.pricing-card.featured .pkg-price {
  color: #ffffff !important;
}
.pricing-card.featured .pkg-hours {
  color: rgba(255,255,255,0.85) !important;
}
.pricing-card.featured li {
  color: #ffffff !important;
}
.pricing-card.featured li::before {
  color: #ffffff !important;
}
.pricing-card.featured {
  padding-top: 14mm !important;  /* зарезервировать место под badge сверху */
}
.pricing-card.featured .badge {
  position: absolute !important;
  top: 4mm !important;
  left: 50% !important;
  right: auto !important;
  transform: translateX(-50%) !important;
  background: rgba(255,255,255,0.20) !important;
  color: #ffffff !important;
  font-size: 7.5pt !important;
  font-weight: 700 !important;
  padding: 1.2mm 4.5mm !important;
  border-radius: 20mm !important;
  border: 1.2px solid rgba(255,255,255,0.55) !important;
  box-shadow: none !important;
}
"""


def arch_svg(name: str) -> str:
    """SVG-иконки для слайда архитектуры (вместо emoji)."""
    paths = {
        # Globe / Web — фронтенд
        "web": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
        # Server / API — бэкенд
        "api": '<rect x="3" y="4" width="18" height="6" rx="1.5"/><rect x="3" y="14" width="18" height="6" rx="1.5"/><circle cx="7" cy="7" r="0.9" fill="currentColor"/><circle cx="7" cy="17" r="0.9" fill="currentColor"/>',
        # Chat bubble + bot
        "bot": '<path d="M3 6.5a3 3 0 0 1 3-3h12a3 3 0 0 1 3 3v8a3 3 0 0 1-3 3H9l-4 3v-3H6a3 3 0 0 1-3-3z"/><circle cx="9" cy="10" r="1.2" fill="currentColor"/><circle cx="15" cy="10" r="1.2" fill="currentColor"/>',
        # Chart bars
        "chart": '<path d="M3 21h18"/><rect x="5" y="13" width="3" height="6"/><rect x="11" y="9" width="3" height="10"/><rect x="17" y="5" width="3" height="14"/>',
    }
    return f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">{paths[name]}</svg>'


def biz_svg(name: str) -> str:
    """SVG-иконки для бизнес-карточек."""
    paths = {
        "inbox": '<path d="M3 13l2.5-7h13L21 13"/><path d="M3 13h6l1 2h4l1-2h6v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
        "invite": '<path d="M21 11l-9 9-4-4"/><rect x="2" y="2" width="14" height="14" rx="2"/>',
        "kick": '<circle cx="9" cy="8" r="3"/><path d="M3 21v-1a5 5 0 0 1 5-5h2"/><path d="M15 9l6 6m0-6l-6 6"/>',
        "profile": '<circle cx="12" cy="8" r="4"/><path d="M4 21v-1a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v1"/>',
        "tariffs": '<path d="M12 2v20M5 5l14 14M5 19L19 5"/>',
        "scale": '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
        "lock": '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 1 1 8 0v4"/>',
        "mobile": '<rect x="7" y="2" width="10" height="20" rx="2"/><circle cx="12" cy="18" r="0.8" fill="currentColor"/>',
    }
    return f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{paths[name]}</svg>'


# ─────────────────────────────────────────────────────────────────────────────
# Слайды
# ─────────────────────────────────────────────────────────────────────────────

def slide_problem_core(num: int, total: int) -> str:
    return f"""
    <section class="slide brand-band">
      <h2 class="section">Понимание задачи</h2>
      <h1 class="slide-title">Что вы просили</h1>
      <div class="grid-2" style="margin-top: 10mm;">
        <div>
          <p class="lead" style="font-size: 13pt;">
            <strong>Telegram-бот</strong> принимает заявки от пользователей.
            Заявки приходят в админ-панель, менеджер связывается с клиентом
            и фиксирует факт оплаты вручную в системе.
          </p>
          <p class="lead" style="font-size: 13pt; margin-top: 5mm;">
            После фиксации оплаты бот <strong>автоматически добавляет</strong>
            пользователя в закрытый канал. По истечении подписки —
            <strong>автоматически удаляет</strong>. На вопросы вне сценария
            бот отвечает «свяжитесь с менеджером».
          </p>
        </div>
        <div style="background: #f5f3ff; border-radius: 4mm; padding: 7mm;">
          <h3 style="font-size: 12pt; color: #4f46e5; margin-bottom: 3mm;">Решение покрывает:</h3>
          <ul class="feature-list" style="font-size: 10.5pt;">
            <li>Множественные боты и закрытые каналы</li>
            <li>Тарифы 3 / 6 / 12 месяцев на продукт</li>
            <li>Заявка через бота → таблица в админке → статусы</li>
            <li>Ручной ввод платежа администратором</li>
            <li>Одноразовый invite-link в канал с TTL = срок подписки</li>
            <li>Worker каждый час: кик из канала по истечении</li>
            <li>Журнал заявок, платежей, активных подписок</li>
          </ul>
        </div>
      </div>
      <div class="grid-4" style="margin-top: 5mm;">
        <div class="card kpi-compact"><div class="kpi-label">срок поставки</div><div class="kpi" style="margin-top: 1mm;">2 нед.</div></div>
        <div class="card kpi-compact"><div class="kpi-label">цена</div><div class="kpi" style="margin-top: 1mm;">фикс</div></div>
        <div class="card kpi-compact"><div class="kpi-label">гарантия на баги</div><div class="kpi" style="margin-top: 1mm;">3 мес.</div></div>
        <div class="card kpi-compact"><div class="kpi-label">исходники у заказчика</div><div class="kpi" style="margin-top: 1mm;">100%</div></div>
      </div>
      {bp.footer(num, total)}
    </section>
    """


def slide_architecture_core(num: int, total: int) -> str:
    """Архитектура с SVG-иконками вместо emoji."""
    return f"""
    <section class="slide brand-band">
      <h2 class="section">Архитектура решения</h2>
      <h1 class="slide-title">Четыре слоя · единая система</h1>
      <div class="arch-row">
        <div class="arch-box">
          <div class="arch-svg">{arch_svg("web")}</div>
          <div class="arch-title">Admin Panel</div>
          <div class="arch-desc">Next.js 15 · React 19 · TailwindCSS · SWR · Recharts</div>
        </div>
        <div class="arch-box">
          <div class="arch-svg">{arch_svg("api")}</div>
          <div class="arch-title">Backend API</div>
          <div class="arch-desc">FastAPI · SQLAlchemy 2.0 async · Alembic · structlog</div>
        </div>
        <div class="arch-box">
          <div class="arch-svg">{arch_svg("bot")}</div>
          <div class="arch-title">Telegram-боты</div>
          <div class="arch-desc">aiogram 3.x · multi-bot polling · APScheduler workers</div>
        </div>
        <div class="arch-box">
          <div class="arch-svg">{arch_svg("chart")}</div>
          <div class="arch-title">Observability</div>
          <div class="arch-desc">Prometheus · Grafana · Loki · Alertmanager · Sentry</div>
        </div>
      </div>
      <div class="grid-2" style="margin-top: 9mm;">
        <div>
          <h3 style="font-size: 13pt; font-weight: 700; color: #1e1b4b; margin-bottom: 3mm;">Что это значит для бизнеса</h3>
          <ul class="feature-list" style="font-size: 10.5pt;">
            <li>Запускается на любом сервере одной командой — не зависим от провайдера, переезд за день</li>
            <li>HTTPS-замок в браузере всегда — сертификат продлевается сам, без напоминаний</li>
            <li>Обновления раскатываются за минуты — без остановки бота и потери данных клиентов</li>
            <li>Сервер не забивается мусором — чистится каждую ночь автоматически</li>
          </ul>
        </div>
        <div>
          <h3 style="font-size: 13pt; font-weight: 700; color: #1e1b4b; margin-bottom: 3mm;">Что это значит для вас как владельца</h3>
          <ul class="feature-list" style="font-size: 10.5pt;">
            <li>Сотрудник не сможет «украсть» сессию админки — даже при вирусе на его компьютере</li>
            <li>Разные права: менеджер не удалит продукт, помощник не увидит платежи</li>
            <li>Любое изменение фиксируется: кто, когда, что поменял — для разбора инцидентов</li>
            <li>Подбор пароля невозможен, ключи и пароли не утекут в открытый код</li>
          </ul>
        </div>
      </div>
      {bp.footer(num, total)}
    </section>
    """


def slide_feature_bot(num: int, total: int) -> str:
    return f"""
    <section class="slide brand-band">
      <h2 class="section">Ключевая функция · бот и заявки</h2>
      <h1 class="slide-title">Telegram-бот → заявка → менеджер</h1>
      <div class="feature-row">
        <div class="shot"><img src="{bp.img_b64('06_leads.png')}" alt=""/></div>
        <div>
          <ul class="feature-list">
            <li>Бот по команде <code>/start</code> показывает карточку продукта с тарифами</li>
            <li>Пользователь нажимает «Оставить заявку» — создаётся запись в админке</li>
            <li>Менеджер в админке видит новые заявки (счётчик в сайдбаре)</li>
            <li>Открывает заявку, видит контакты пользователя, ведёт по статусам new → contacted → paid → closed</li>
            <li>Если пользователь пишет любой другой текст — бот вежливо просит написать менеджеру</li>
          </ul>
        </div>
      </div>
      {bp.footer(num, total)}
    </section>
    """


def slide_feature_access(num: int, total: int) -> str:
    return f"""
    <section class="slide brand-band">
      <h2 class="section">Ключевая функция · авто-доступ</h2>
      <h1 class="slide-title">Оплата → доступ в канал → автоматический кик</h1>
      <div class="feature-row">
        <div class="shot"><img src="{bp.img_b64('08_subscriptions.png')}" alt=""/></div>
        <div>
          <ul class="feature-list">
            <li>Администратор вводит платёж: выбирает пользователя, продукт, период (3/6/12 мес)</li>
            <li>Система автоматически создаёт подписку с датой истечения</li>
            <li>Бот генерирует одноразовый invite-link в канал (одно использование, TTL = подписка)</li>
            <li>Ссылка приходит пользователю в личку — он переходит и попадает в канал</li>
            <li>Раз в час worker проверяет истёкшие подписки и кикает из канала с уведомлением</li>
            <li>Подписку можно продлить или досрочно отозвать одной кнопкой</li>
          </ul>
        </div>
      </div>
      {bp.footer(num, total)}
    </section>
    """


def slide_business_values(num: int, total: int) -> str:
    """Слайд 6 — бизнес-ценности вместо технических модулей."""
    cards = "".join(
        f"""
        <div class="biz-card">
          <div class="biz-icon">{biz_svg(v["icon"])}</div>
          <h4>{v["title"]}</h4>
          <p>{v["desc"]}</p>
        </div>
        """ for v in BUSINESS_VALUES
    )
    return f"""
    <section class="slide brand-band">
      <h2 class="section">Что это даёт бизнесу</h2>
      <h1 class="slide-title">8 болей, которые Grammy закрывает</h1>
      <p style="font-size: 11pt; color: #6b7280; max-width: 220mm; margin-top: 2mm;">
        Не «что мы написали», а «что вы получите». Каждая карточка — конкретная боль эксперта,
        которая снимается «из коробки».
      </p>
      <div class="biz-grid">{cards}</div>
      {bp.footer(num, total)}
    </section>
    """


def slide_pricing_core(num: int, total: int) -> str:
    """Слайд 7 — 3 варианта цены: 125K / 112.5K с кейсом / рассрочка 170K на 3 мес."""
    price_str = f"{CORE_PRICE:,} ₽".replace(",", " ")
    case_str = f"{CORE_PRICE_CASE:,} ₽".replace(",", " ")
    instalment_total = 170_000
    instalment_str = f"{instalment_total:,} ₽".replace(",", " ")
    # 3 платежа: 60К + 55К + 55К = 170К
    p1, p2, p3 = 60_000, 55_000, 55_000
    p1_s = f"{p1:,} ₽".replace(",", " ")
    p2_s = f"{p2:,} ₽".replace(",", " ")
    p3_s = f"{p3:,} ₽".replace(",", " ")

    return f"""
    <section class="slide brand-band">
      <h2 class="section">Стоимость</h2>
      <h1 class="slide-title">Три варианта · вы выбираете</h1>
      <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 6mm; margin-top: 8mm;">

        <!-- Variant 1: Стандарт -->
        <div class="pricing-card">
          <div class="pkg-name">Стандарт</div>
          <div class="pkg-price">{price_str}</div>
          <div class="pkg-hours">2 недели · оплата 50/50</div>
          <ul>
            <li>Полный функционал Core</li>
            <li>Исходный код у заказчика</li>
            <li>Развёртывание под ключ</li>
            <li>Гарантия 3 месяца на баги</li>
            <li>Оплата: 50% при старте · 50% при сдаче</li>
          </ul>
        </div>

        <!-- Variant 2: Партнёрский кейс (featured) -->
        <div class="pricing-card featured">
          <div class="badge">Рекомендуется</div>
          <div class="pkg-name">Партнёрский кейс</div>
          <div class="pkg-price">{case_str}</div>
          <div class="pkg-hours">скидка 10% · 2 недели</div>
          <ul>
            <li>Всё из «Стандарт»</li>
            <li>Через 3 месяца после запуска вы делитесь обезличенными показателями для публикации кейса</li>
            <li>Это маркетинг — он же берёт на себя часть стоимости</li>
            <li>Никаких эксклюзивных прав, только согласие на пост</li>
          </ul>
        </div>

        <!-- Variant 3: Рассрочка -->
        <div class="pricing-card">
          <div class="pkg-name">Рассрочка · 3 мес</div>
          <div class="pkg-price">{instalment_str}</div>
          <div class="pkg-hours">3 платежа в течение 3 месяцев</div>
          <ul>
            <li>Тот же функционал, что в «Стандарт»</li>
            <li>1-й платёж {p1_s} — при сдаче</li>
            <li>2-й платёж {p2_s} — через 30 дней</li>
            <li>3-й платёж {p3_s} — через 60 дней</li>
            <li>Наценка покрывает кассовый разрыв исполнителя</li>
          </ul>
        </div>

      </div>
      <p style="font-size: 10pt; color: #6b7280; margin-top: 9mm;">
        Все цены без НДС. График и форма оплаты — согласовываются индивидуально.
      </p>
      {bp.footer(num, total)}
    </section>
    """


def slide_comparison_table(num: int, total: int) -> str:
    """Слайд 8 — таблица сравнения тарифов с user-story."""
    rows = ""
    for category, features in COMPARISON_FEATURES:
        rows += f'<tr class="cat-row"><td colspan="5">{category}</td></tr>'
        for desc, *checks in features:
            cells = ""
            for c in checks:
                if c:
                    cells += '<td class="pkg-cell"><span class="compare-yes">✓</span></td>'
                else:
                    cells += '<td class="pkg-cell"><span class="compare-no">—</span></td>'
            rows += f'<tr><td class="feat">{desc}</td>{cells}</tr>'

    return f"""
    <section class="slide brand-band">
      <h2 class="section">Куда можно расти</h2>
      <h1 class="slide-title" style="margin-bottom: 3mm;">Независимые модули, не пакеты</h1>
      <p style="font-size: 10pt; color: #6b7280; max-width: 230mm; margin-bottom: 1mm;">
        Каждый столбец — отдельный модуль со своей ценой. Галочка стоит ровно в тех строках, что входят в этот модуль. Модули не вложены друг в друга — можно докупить любой в любом порядке, поверх Core.
      </p>

      <table class="compare-table">
        <thead>
          <tr>
            <th style="width: 95mm;">Что может делать админ</th>
            <th class="pkg-col">
              <div class="pkg-title">Core</div>
              <div class="pkg-price">125 000 ₽</div>
            </th>
            <th class="pkg-col">
              <div class="pkg-title">+ Прогрев</div>
              <div class="pkg-price">+150 000 ₽</div>
            </th>
            <th class="pkg-col">
              <div class="pkg-title">+ Аналитика</div>
              <div class="pkg-price">+70 000 ₽</div>
            </th>
            <th class="pkg-col featured">
              <div class="pkg-title">+ Премиум</div>
              <div class="pkg-price">+100 000 ₽</div>
            </th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>

      {bp.footer(num, total)}
    </section>
    """


def slide_roadmap_dev(num: int, total: int) -> str:
    """Слайд 9 — план развития, сроки в неделях, без сломанных подложек."""
    stages = [
        ("+1 нед", "Аналитика и метрики", "Через 50–100 заявок включаются отчёты «Эффективность» и «Источники»: видно, какие каналы окупаются.", "+ 70 000 ₽"),
        ("+3 нед", "Воронки прогрева", "Серия отложенных сообщений с лидмагнитами прогревает к покупке тех, кто не купил сразу. Конверсия обычно растёт на 15–30%.", "+ 150 000 ₽"),
        ("+5 нед", "A/B-тесты воронок", "Сравнивайте варианты приветственного сообщения, тарифа или кнопки — система сама покажет, какой даёт больше конверсии.", "по запросу"),
        ("+7 нед", "Партнёрская программа", "Каждый клиент получает свою ссылку и процент от продаж тех, кого он привёл — превращает аудиторию в команду продавцов.", "по запросу"),
    ]
    cards = "".join(
        f"""
        <div class="dev-stage">
          <div class="stage-week">{w}</div>
          <h4>{title}</h4>
          <p>{desc}</p>
          <div class="stage-price" style="color: #6366f1;">{price}</div>
        </div>
        """ for w, title, desc, price in stages
    )
    return f"""
    <section class="slide brand-band">
      <h2 class="section">План развития</h2>
      <h1 class="slide-title">Куда вырастет ваш Grammy</h1>
      <p style="font-size: 11pt; color: #6b7280; max-width: 220mm; margin-top: 2mm;">
        Если запуск пройдёт успешно — продукт растёт вместе с бизнесом. Каждые 1–3 недели
        работы добавляется новый блок, без переписывания того, что уже работает.
      </p>
      <div class="dev-roadmap">{cards}</div>
      <p style="font-size: 9pt; color: #9ca3af; margin-top: 6mm; text-align: center; font-style: italic;">
        Архитектура спроектирована так, чтобы добавление любого блока не ломало уже работающее ядро.
      </p>
      {bp.footer(num, total)}
    </section>
    """


def slide_roadmap_core(num: int, total: int) -> str:
    """Слайд 10 — план поставки + модель сотрудничества."""
    return f"""
    <section class="slide brand-band">
      <h2 class="section">Дорожная карта · 2 недели</h2>
      <h1 class="slide-title">От договора до запуска</h1>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6mm; margin-top: 7mm;">
        <div class="phase">
          <div class="phase-num">Неделя 1 · фундамент</div>
          <h4>Инфраструктура и каркас</h4>
          <ul>
            <li>Развёртывание сервера, SSL, БД</li>
            <li>Каркас админки с аутентификацией</li>
            <li>Подключение бота, создание канала и продукта</li>
            <li>Базовый бот: /start, карточка, заявка</li>
          </ul>
        </div>
        <div class="phase">
          <div class="phase-num">Неделя 2 · продажи</div>
          <h4>Платежи и приёмка</h4>
          <ul>
            <li>Платежи в админке, генерация invite-ссылок</li>
            <li>Worker авто-кика по истечении</li>
            <li>Тестирование сквозного сценария</li>
            <li>Обучение команды + сдача</li>
          </ul>
        </div>
      </div>

      <h3 style="font-size: 13pt; font-weight: 700; color: #1e1b4b; margin-top: 9mm;">Модель сотрудничества</h3>
      <div class="collab-row">
        <div class="collab-card featured">
          <h4>Опционально: оплатить пакет вперёд</h4>
          <p>Берёте Core + любую опцию из таблицы (Прогрев / Аналитика / Премиум) в рассрочку.
          Релиз — поэтапный, начинаем сразу после подписания. Получаете продукт целиком.</p>
        </div>
        <div class="collab-card">
          <h4>Опционально: часы на улучшения</h4>
          <p>Если после сдачи Core часы не «выработаны» — оставшиеся идут на улучшения по вашему запросу.
          Не нужно ждать целый модуль — точечные доработки тоже считаются.</p>
        </div>
      </div>

      {bp.footer(num, total)}
    </section>
    """


def slide_guarantees_core(num: int, total: int) -> str:
    return f"""
    <section class="slide brand-band">
      <h2 class="section">Что входит в стоимость</h2>
      <h1 class="slide-title">Продукт под ключ · ничего больше платить не нужно</h1>
      <div class="grid-2" style="margin-top: 10mm;">
        <div>
          <ul class="feature-list">
            <li>Исходный код в Git-репозитории под управление заказчика</li>
            <li>Развёртывание на сервере заказчика «под ключ»</li>
            <li>HTTPS + автопродление SSL-сертификата</li>
            <li>Краткая документация: гайд по использованию (PDF)</li>
            <li>Обучающая сессия с командой заказчика (2 часа)</li>
          </ul>
        </div>
        <div>
          <ul class="feature-list">
            <li>Гарантия на исправление багов: 3 месяца после сдачи</li>
            <li>Поддержка по вопросам эксплуатации в Telegram-чате</li>
            <li>Передача доступов и пошаговый онбординг</li>
            <li>Опция сопровождения: 25 000 ₽/мес на бэклог-задачи</li>
            <li>Опции апгрейда — отдельной строкой в договоре (см. слайд 8)</li>
          </ul>
        </div>
      </div>
      <div class="cta-card">
        <h3>Готовы стартовать?</h3>
        <p>Подписываем простой договор оферты с фиксированной ценой и сроком.
        Старт — в течение 3 рабочих дней с момента подписания.</p>
      </div>
      {bp.footer(num, total)}
    </section>
    """


def slide_contact_core(num: int, total: int) -> str:
    """Контакты — без большого винила внизу (он наезжал на колонтитул)."""
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
          <p style="font-size: 13pt; color: #c7d2fe; line-height: 1.7;">
            <span style="color: #a5b4fc;">Email:</span> <span style="color: #fff;">malik@protopopov.xyz</span><br/>
            <span style="color: #a5b4fc;">Telegram:</span> <span style="color: #fff;">@mal1k_pro</span><br/>
            <span style="color: #a5b4fc;">Сайт:</span> <span style="color: #fff;">mediann.dev</span>
          </p>
        </div>
      </div>

      <!-- Маленький винил в правом верхнем углу, не пересекается с колонтитулом -->
      <div style="position: absolute; top: 18mm; right: 22mm; width: 18mm; height: 18mm; opacity: 0.7;">{bp.VINYL_SVG}</div>

      <div class="footer" style="color: #6366f1;">
        <div class="brand"><span class="brand-mark">{bp.VINYL_SVG}</span><span>GRAMMY</span></div>
        <div>{num} / {total}</div>
        <div>Спасибо за внимание</div>
      </div>
    </section>
    """


# ─────────────────────────────────────────────────────────────────────────────

def build_html() -> str:
    total = 12
    parts = [
        f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Grammy · Core — Коммерческое предложение</title>
<style>{bp.CSS}</style>
<style>{OVERRIDE_CSS}</style>
</head>
<body>""",
        bp.slide_cover(),                  # 1
        slide_problem_core(2, total),      # 2 — компактный
        slide_architecture_core(3, total), # 3 — SVG-иконки
        slide_feature_bot(4, total),       # 4 — без серого border
        slide_feature_access(5, total),    # 5 — без серого border
        slide_business_values(6, total),   # 6 — НОВЫЙ: бизнес-ценности
        slide_pricing_core(7, total),      # 7 — 3 варианта цены
        slide_comparison_table(8, total),  # 8 — НОВЫЙ: таблица сравнения
        slide_roadmap_dev(9, total),       # 9 — недели, без сломанных подложек
        slide_roadmap_core(10, total),     # 10 — + модель сотрудничества
        slide_guarantees_core(11, total),  # 11
        slide_contact_core(12, total),     # 12 — винил в углу, не на колонтитуле
        "</body></html>",
    ]
    return "".join(parts)


def main():
    out = Path(__file__).resolve().parent / "Grammy_KP_Core.html"
    out.write_text(build_html(), encoding="utf-8")
    print(f"✓ HTML Core: {out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
