"""
Генератор HTML-мокапов админки Grammy с реалистичными «боевыми» данными.

Запуск:
  python3 docs/proposal/mockups/build_mockups.py

Выход:
  docs/proposal/mockups/dashboard.html
  docs/proposal/mockups/analytics.html
  docs/proposal/mockups/leads.html
  docs/proposal/mockups/subscriptions.html

Далее → render_mockups.js рендерит каждый в PNG и складывает в docs/proposal/screenshots/
(заменяет существующие 02/06/08/13).
"""
from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).resolve().parent

# Тот же glass + brand из admin/app/globals.css
BASE_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
* { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --ink: #0b1020;
  --muted: #6b7280;
}
html, body {
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  color: var(--ink);
  -webkit-font-smoothing: antialiased;
  font-feature-settings: 'cv11', 'ss01', 'ss03';
}
body {
  background:
    radial-gradient(1200px 800px at -10% -10%, rgba(99, 102, 241, 0.18), transparent 60%),
    radial-gradient(900px 700px at 110% 10%, rgba(244, 114, 182, 0.16), transparent 55%),
    radial-gradient(900px 700px at 50% 120%, rgba(20, 184, 166, 0.12), transparent 50%),
    linear-gradient(180deg, #f8faff 0%, #f4f6fb 100%);
  min-height: 100vh;
}
.glass {
  background: rgba(255,255,255,0.65);
  backdrop-filter: saturate(160%) blur(14px);
  border: 1px solid rgba(255,255,255,0.55);
  box-shadow: 0 10px 30px -12px rgba(15,23,42,0.18), inset 0 1px 0 rgba(255,255,255,0.6);
}
.glass-strong {
  background: rgba(255,255,255,0.85);
  backdrop-filter: saturate(180%) blur(20px);
  border: 1px solid rgba(255,255,255,0.7);
  box-shadow: 0 24px 50px -18px rgba(15,23,42,0.25);
}
.glass-soft {
  background: rgba(255,255,255,0.55);
  backdrop-filter: saturate(150%) blur(10px);
  border: 1px solid rgba(255,255,255,0.5);
}
.gradient-text {
  background: linear-gradient(135deg, #4f46e5 0%, #9333ea 50%, #ec4899 100%);
  -webkit-background-clip: text; background-clip: text; color: transparent;
}
.gradient-primary {
  background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 60%, #a855f7 100%);
}

/* Layout */
.app {
  display: grid;
  grid-template-columns: 260px 1fr;
  min-height: 100vh;
  padding: 12px;
  gap: 12px;
}
aside.sidebar {
  border-radius: 16px;
  padding: 18px 14px;
  display: flex; flex-direction: column;
  gap: 8px;
  height: calc(100vh - 24px);
  position: sticky; top: 12px;
}
.brand-row {
  display: flex; align-items: center; gap: 10px;
  padding: 4px 6px 14px 6px;
}
.brand-mark {
  width: 36px; height: 36px; border-radius: 10px;
  background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 60%, #a855f7 100%);
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 8px 20px -8px rgba(124,58,237,0.6);
}
.brand-title { font-size: 14px; font-weight: 700; letter-spacing: -0.2px; }
.brand-sub { font-size: 9.5px; color: #6b7280; text-transform: uppercase; letter-spacing: 2px; }

nav .group-label {
  font-size: 10px; text-transform: uppercase; letter-spacing: 2px;
  color: #9ca3af; padding: 10px 12px 4px;
  display: flex; justify-content: space-between; align-items: center;
}
nav .item {
  display: flex; align-items: center; gap: 12px;
  padding: 9px 12px;
  border-radius: 10px;
  font-size: 13px;
  color: #4b5563;
  position: relative;
  cursor: pointer;
}
nav .item.active {
  background: rgba(255,255,255,0.85);
  color: #0b1020;
  font-weight: 600;
  box-shadow: 0 4px 12px -6px rgba(15,23,42,0.08);
}
nav .item.active::before {
  content: ""; position: absolute; left: 0; top: 6px; bottom: 6px;
  width: 3px; border-radius: 2px;
  background: linear-gradient(180deg, #6366f1 0%, #f43f5e 100%);
}
nav .item .ic { width: 18px; height: 18px; flex-shrink: 0; color: #94a3b8; }
nav .item.active .ic { color: #6366f1; }
nav .item .badge {
  margin-left: auto;
  background: #fef3c7; color: #92400e;
  font-size: 10px; font-weight: 700;
  padding: 1px 6px; border-radius: 999px;
}
nav .item.active .badge { background: #e0e7ff; color: #4338ca; }

.sidebar-footer {
  margin-top: auto;
  background: rgba(255,255,255,0.7);
  border-radius: 12px;
  padding: 10px;
  display: flex; align-items: center; gap: 10px;
}
.sidebar-footer .avatar {
  width: 30px; height: 30px; border-radius: 50%;
  background: linear-gradient(135deg, #4f46e5, #a855f7);
  color: #fff; font-weight: 700; font-size: 11px;
  display: flex; align-items: center; justify-content: center;
}
.sidebar-footer .name { font-size: 12px; font-weight: 600; }
.sidebar-footer .role { font-size: 9px; color: #9ca3af; text-transform: uppercase; letter-spacing: 1.5px; }

main.workspace { display: flex; flex-direction: column; gap: 12px; min-width: 0; }
header.topbar {
  border-radius: 16px;
  padding: 0 20px;
  height: 56px;
  display: flex; align-items: center; gap: 12px;
}
.crumbs { font-size: 13px; display: flex; align-items: center; }
.crumbs a { color: #9ca3af; text-decoration: none; }
.crumbs .sep { margin: 0 6px; color: #d1d5db; }
.crumbs b { color: #0b1020; font-weight: 600; }

.page-header { padding: 24px 28px 0; }
.page-header h1 {
  font-size: 26px; font-weight: 800; letter-spacing: -0.5px;
}
.page-header .subtitle {
  font-size: 13px; color: #6b7280; margin-top: 4px;
}

.section { padding: 20px 28px; }

/* Cards / KPI */
.kpi-grid {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px;
}
.kpi-card {
  border-radius: 16px; padding: 16px 18px;
}
.kpi-label {
  font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px;
  color: #6b7280; font-weight: 600;
}
.kpi-value {
  font-size: 28px; font-weight: 800; letter-spacing: -1px;
  margin-top: 4px;
}
.kpi-delta {
  font-size: 11px; font-weight: 600; margin-top: 6px;
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 8px; border-radius: 999px;
}
.kpi-delta.up { background: #dcfce7; color: #166534; }
.kpi-delta.down { background: #fee2e2; color: #991b1b; }

/* Tables */
.table {
  width: 100%;
  border-collapse: separate; border-spacing: 0;
  font-size: 13px;
}
.table thead th {
  text-align: left;
  font-size: 11px; text-transform: uppercase; letter-spacing: 1px;
  color: #6b7280; font-weight: 600;
  padding: 10px 14px;
  border-bottom: 1px solid rgba(15,23,42,0.06);
}
.table tbody td {
  padding: 12px 14px;
  border-bottom: 1px solid rgba(15,23,42,0.04);
}
.table tbody tr:last-child td { border-bottom: 0; }
.table tbody tr:hover { background: rgba(99,102,241,0.04); }

.avatar-cell {
  display: flex; align-items: center; gap: 10px;
}
.avatar-mini {
  width: 28px; height: 28px; border-radius: 50%;
  background: linear-gradient(135deg, #4f46e5, #a855f7);
  color: #fff; font-weight: 700; font-size: 11px;
  display: flex; align-items: center; justify-content: center;
}
.avatar-mini.alt-1 { background: linear-gradient(135deg, #06b6d4, #0ea5e9); }
.avatar-mini.alt-2 { background: linear-gradient(135deg, #f59e0b, #ef4444); }
.avatar-mini.alt-3 { background: linear-gradient(135deg, #10b981, #14b8a6); }
.avatar-mini.alt-4 { background: linear-gradient(135deg, #ec4899, #db2777); }
.avatar-mini.alt-5 { background: linear-gradient(135deg, #8b5cf6, #6366f1); }

.pill {
  display: inline-flex; align-items: center;
  font-size: 11px; font-weight: 600;
  padding: 3px 10px; border-radius: 999px;
}
.pill.amber { background: #fef3c7; color: #92400e; }
.pill.green { background: #dcfce7; color: #166534; }
.pill.gray { background: #f3f4f6; color: #6b7280; }
.pill.indigo { background: #e0e7ff; color: #4338ca; }
.pill.rose { background: #fce7f3; color: #be185d; }

.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }
.muted { color: #6b7280; }
.text-sm { font-size: 12.5px; }
.text-xs { font-size: 11px; }
.text-right { text-align: right; }

/* Cards section header */
.card-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 20px; border-bottom: 1px solid rgba(15,23,42,0.05);
}
.card-header .title { font-size: 14px; font-weight: 700; }
.card-header .link {
  font-size: 12px; color: #6366f1; font-weight: 600; text-decoration: none;
}

.card {
  border-radius: 16px;
  overflow: hidden;
}
"""


def _icon(name: str) -> str:
    """Минимальные SVG-иконки для navbar."""
    icons = {
        "home": '<path d="M3 11l9-8 9 8"/><path d="M5 10v10h14V10"/><path d="M9 21V14h6v7"/>',
        "leads": '<path d="M4 4h16v14H7l-3 3z"/><path d="M8 9h8M8 13h5"/>',
        "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>',
        "wallet": '<rect x="3" y="6" width="18" height="13" rx="2"/><path d="M16 12h3"/><path d="M3 10h18"/>',
        "subs": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
        "product": '<path d="M20 7l-8-4-8 4v10l8 4 8-4z"/><path d="M4 7l8 4 8-4"/><path d="M12 11v10"/>',
        "channel": '<path d="M3 11l18-8-8 18-2-8z"/>',
        "bot": '<rect x="3" y="8" width="18" height="12" rx="3"/><path d="M12 4v4"/><circle cx="8" cy="14" r="1"/><circle cx="16" cy="14" r="1"/>',
        "source": '<circle cx="6" cy="6" r="3"/><circle cx="18" cy="18" r="3"/><path d="M9 6h6l3 12"/>',
        "funnel": '<path d="M3 5h18l-7 8v6l-4 2v-8z"/>',
        "magnet": '<path d="M6 4v8a6 6 0 0 0 12 0V4"/>',
        "trigger": '<path d="M13 2L3 14h7l-1 8 10-12h-7z"/>',
        "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
        "chart": '<path d="M3 3v18h18"/><path d="M7 14l4-4 4 4 5-7"/>',
    }
    path = icons.get(name, "")
    return f'<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{path}</svg>'


def sidebar(active: str) -> str:
    """Sidebar матчится с реальным admin/app/(dash)/layout.tsx — 7 групп."""
    def item(key: str, label: str, icon: str, badge: str | None = None) -> str:
        cls = "item active" if key == active else "item"
        bd = f'<span class="badge">{badge}</span>' if badge else ""
        return f'<a class="{cls}">{_icon(icon)}<span>{label}</span>{bd}</a>'

    return f"""
    <aside class="sidebar glass-strong">
      <div class="brand-row">
        <div class="brand-mark">
          <svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="1.4" width="20" height="20">
            <circle cx="12" cy="12" r="10" opacity="0.9"/>
            <circle cx="12" cy="12" r="6.5" opacity="0.45"/>
            <circle cx="12" cy="12" r="3.2" fill="white"/>
            <circle cx="12" cy="12" r="0.9" fill="#1e1b4b"/>
          </svg>
        </div>
        <div>
          <div class="brand-title">Grammy</div>
          <div class="brand-sub">admin</div>
        </div>
      </div>
      <nav>
        {item("overview", "Обзор", "home")}

        <div class="group-label">Аналитика<span>▾</span></div>
        {item("analytics", "Эффективность", "chart")}
        {item("sources", "Источники", "source")}

        <div class="group-label">Продажи<span>▾</span></div>
        {item("leads", "Заявки", "leads", "12")}
        {item("payments", "Платежи", "wallet")}
        {item("subscriptions", "Подписки", "subs", "8")}

        <div class="group-label">Воронки<span>▾</span></div>
        {item("funnels", "Воронки", "funnel")}
        {item("magnets", "Лидмагниты", "magnet")}
        {item("triggers", "Кодовые слова", "trigger")}

        <div class="group-label">Каталог<span>▾</span></div>
        {item("products", "Продукты", "product")}
        {item("channels", "Каналы", "channel")}
        {item("bots", "Боты", "bot")}

        <div class="group-label">Аудитория<span>▾</span></div>
        {item("users", "Пользователи", "users")}

        <div class="group-label">Администрирование<span>▾</span></div>
        {item("audit", "Аудит-журнал", "shield")}
      </nav>
      <div class="sidebar-footer">
        <div class="avatar">A</div>
        <div style="flex:1;">
          <div class="name">admin</div>
          <div class="role">admin</div>
        </div>
      </div>
    </aside>
    """


def topbar(*crumbs: str) -> str:
    parts = []
    for i, c in enumerate(crumbs):
        if i > 0:
            parts.append('<span class="sep">/</span>')
        if i == len(crumbs) - 1:
            parts.append(f"<b>{c}</b>")
        else:
            parts.append(f"<a>{c}</a>")
    badge = '''<div style="margin-left:auto;display:flex;align-items:center;gap:8px;background:#fef3c7;color:#92400e;font-size:11.5px;font-weight:600;padding:5px 12px;border-radius:8px;border:1px solid #fde68a">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16v14H7l-3 3z"/></svg>
      12 новых заявок
    </div>'''
    return f"""
    <header class="topbar glass">
      <div class="crumbs">{''.join(parts)}</div>
      {badge}
    </header>
    """


def page_skeleton(active: str, crumbs: list[str], body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Grammy — admin</title>
<style>{BASE_CSS}</style>
</head>
<body>
<div class="app">
  {sidebar(active)}
  <main class="workspace">
    {topbar(*crumbs)}
    {body}
  </main>
</div>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# Данные мокапов
# ─────────────────────────────────────────────────────────────────────────────

RECENT_LEADS = [
    ("ИП", "Иван Петров",       "@ivan_petrov",   "Премиум-клуб", "new",       "12 минут назад",   "alt-1"),
    ("АС", "Анна Соколова",     "@anna_s",        "Премиум-клуб", "contacted", "1 час назад",      "alt-2"),
    ("ДК", "Дмитрий Кузнецов",  "@dim_k",         "Премиум-клуб", "paid",      "2 часа назад",     "alt-3"),
    ("МЛ", "Мария Лебедева",    "@maria_leb",     "Премиум-клуб", "new",       "4 часа назад",     "alt-4"),
    ("СМ", "Сергей Морозов",    "@morozov_s",     "Премиум-клуб", "contacted", "вчера, 18:45",     "alt-5"),
]

RECENT_PAYMENTS = [
    ("ДК", "Дмитрий Кузнецов",  "9 490 ₽",  "6 мес", "30 минут назад", "alt-3"),
    ("ЕВ", "Елена Васильева",   "4 990 ₽",  "3 мес", "2 часа назад",   "alt-4"),
    ("АИ", "Алексей Иванов",    "17 990 ₽", "12 мес", "вчера, 21:12",   "alt-1"),
    ("ОН", "Ольга Новикова",    "9 490 ₽",  "6 мес", "вчера, 14:33",   "alt-2"),
    ("МП", "Михаил Попов",      "4 990 ₽",  "3 мес", "позавчера",     "alt-5"),
]

STATUS_TR = {
    "new":       ('amber',  "новая"),
    "contacted": ('indigo', "связались"),
    "paid":      ('green',  "оплачено"),
    "closed":    ('gray',   "закрыто"),
}


# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────

def page_dashboard() -> str:
    lead_rows = ""
    for initials, name, username, product, status, when, alt in RECENT_LEADS:
        color, text = STATUS_TR[status]
        lead_rows += f"""
        <tr>
          <td>
            <div class="avatar-cell">
              <div class="avatar-mini {alt}">{initials}</div>
              <div>
                <div style="font-weight:600;">{name}</div>
                <div class="text-xs muted mono">{username}</div>
              </div>
            </div>
          </td>
          <td class="text-sm">{product}</td>
          <td><span class="pill {color}">{text}</span></td>
          <td class="text-sm muted text-right">{when}</td>
        </tr>
        """

    pay_rows = ""
    for initials, name, amount, period, when, alt in RECENT_PAYMENTS:
        pay_rows += f"""
        <tr>
          <td>
            <div class="avatar-cell">
              <div class="avatar-mini {alt}">{initials}</div>
              <div>
                <div style="font-weight:600;">{name}</div>
                <div class="text-xs muted">{period}</div>
              </div>
            </div>
          </td>
          <td class="text-right" style="font-weight:700;">{amount}</td>
          <td class="text-right text-sm muted">{when}</td>
        </tr>
        """

    body = f"""
    <div class="page-header">
      <h1>Обзор</h1>
      <div class="subtitle">Ключевые показатели за последние 30 дней</div>
    </div>

    <div class="section">
      <div class="kpi-grid">
        <div class="kpi-card glass">
          <div class="kpi-label">Пользователи</div>
          <div class="kpi-value">1 247</div>
          <div class="kpi-delta up">▲ +127 за месяц</div>
        </div>
        <div class="kpi-card glass">
          <div class="kpi-label">Новые заявки</div>
          <div class="kpi-value">24</div>
          <div class="kpi-delta up">▲ +9 к прошлой неделе</div>
        </div>
        <div class="kpi-card glass">
          <div class="kpi-label">Активные подписки</div>
          <div class="kpi-value">89</div>
          <div class="kpi-delta up">▲ +12 за месяц</div>
        </div>
        <div class="kpi-card glass">
          <div class="kpi-label">Выручка 30 дней</div>
          <div class="kpi-value gradient-text">458 410 ₽</div>
          <div class="kpi-delta up">▲ +23% к прошлому периоду</div>
        </div>
      </div>
    </div>

    <div class="section" style="display:grid; grid-template-columns: 1.1fr 0.9fr; gap:14px;">
      <div class="card glass">
        <div class="card-header">
          <div class="title">Последние заявки</div>
          <a class="link">Все заявки →</a>
        </div>
        <table class="table">
          <thead><tr><th>Клиент</th><th>Продукт</th><th>Статус</th><th class="text-right">Когда</th></tr></thead>
          <tbody>{lead_rows}</tbody>
        </table>
      </div>

      <div class="card glass">
        <div class="card-header">
          <div class="title">Последние платежи</div>
          <a class="link">Все →</a>
        </div>
        <table class="table">
          <thead><tr><th>Клиент</th><th class="text-right">Сумма</th><th class="text-right">Когда</th></tr></thead>
          <tbody>{pay_rows}</tbody>
        </table>
      </div>
    </div>
    """
    return page_skeleton("overview", ["Обзор"], body)


# ─────────────────────────────────────────────────────────────────────────────
# ANALYTICS
# ─────────────────────────────────────────────────────────────────────────────

def page_analytics() -> str:
    # Реалистичный stacked-area график за 30 дней с 4 источниками
    # Используем SVG напрямую — это надёжнее чем подгружать recharts
    days = 30
    width = 720
    height = 220
    pad_l, pad_r, pad_t, pad_b = 40, 10, 10, 28
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b

    # Серии: 4 источника, каждый день — кумулятивно (stacked)
    # Реалистичная картинка: instagram_reels растёт, остальные стабильнее
    import math, random
    random.seed(42)
    def gen_series(base, growth, noise):
        out = []
        for i in range(days):
            v = base + (i * growth) + (random.random() - 0.5) * noise + math.sin(i / 5) * noise * 0.3
            out.append(max(0, v))
        return out

    series = [
        ("Instagram Reels", gen_series(2.0, 0.35, 1.5), "#6366f1"),
        ("YouTube",         gen_series(2.5, 0.10, 1.2), "#06b6d4"),
        ("Telegram-чаты",   gen_series(1.5, 0.05, 0.9), "#f59e0b"),
        ("Подкасты",        gen_series(1.0, 0.02, 0.6), "#10b981"),
    ]

    # Стек: для каждого дня — кумулятивные значения
    stacked = [[0.0] * days for _ in range(len(series))]
    for d in range(days):
        cum = 0
        for s_idx in range(len(series)):
            cum += series[s_idx][1][d]
            stacked[s_idx][d] = cum

    max_val = max(stacked[-1])

    def to_x(i): return pad_l + (i / (days - 1)) * plot_w
    def to_y(v): return pad_t + plot_h - (v / max_val) * plot_h

    # Сверху вниз заливаем — от верхней серии к нижней
    areas = ""
    for s_idx in range(len(series) - 1, -1, -1):
        name, _, color = series[s_idx]
        top_points = [(to_x(i), to_y(stacked[s_idx][i])) for i in range(days)]
        if s_idx == 0:
            bottom_points = [(to_x(days - 1 - i), pad_t + plot_h) for i in range(days)]
        else:
            bottom_points = [(to_x(days - 1 - i), to_y(stacked[s_idx - 1][days - 1 - i])) for i in range(days)]
        all_points = top_points + bottom_points
        path = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in all_points) + " Z"
        areas += f'<path d="{path}" fill="{color}" opacity="0.62"/>'

    # X-axis labels: каждые 5 дней
    x_labels = ""
    for i in range(0, days, 5):
        x = to_x(i)
        date_offset = 30 - i
        day_label = f"{30 - date_offset}/05" if date_offset > 0 else "сегодня"
        # Проще: просто "д-N"
        x_labels += f'<text x="{x:.0f}" y="{height - 8}" font-size="9.5" fill="#9ca3af" text-anchor="middle">д-{30 - i}</text>'

    # Y axis labels
    y_labels = ""
    for frac in (0, 0.25, 0.5, 0.75, 1):
        v = max_val * frac
        y = to_y(v)
        y_labels += f'<text x="{pad_l - 6}" y="{y + 3:.0f}" font-size="9.5" fill="#9ca3af" text-anchor="end">{int(v * 4)}</text>'
        y_labels += f'<line x1="{pad_l}" x2="{width - pad_r}" y1="{y:.1f}" y2="{y:.1f}" stroke="#e4e4e7" stroke-dasharray="3,3" stroke-width="0.6"/>'

    # Legend под графиком
    legend = ""
    for name, _, color in series:
        legend += f'<div style="display:flex;align-items:center;gap:6px;font-size:11.5px;color:#374151;"><span style="width:10px;height:10px;background:{color};border-radius:2px;opacity:0.7;"></span>{name}</div>'

    chart_svg = f"""
    <svg viewBox="0 0 {width} {height}" style="width:100%;display:block;">
      <rect x="{pad_l}" y="{pad_t}" width="{plot_w}" height="{plot_h}" fill="none"/>
      {y_labels}
      {areas}
      {x_labels}
    </svg>
    """

    # Pareto rows
    pareto = [
        ("Instagram Reels",    "147", "32", "21.8%", "295 720 ₽"),
        ("YouTube канал",       "98", "14", "14.3%", "118 470 ₽"),
        ("Telegram-чат @smm",   "62",  "8", "12.9%",  "75 920 ₽"),
        ("Подкаст «Деньги»",    "34",  "5", "14.7%",  "44 950 ₽"),
        ("Органика",            "21",  "2",  "9.5%",  "17 980 ₽"),
    ]
    pareto_rows = ""
    for src, leads, payments, cvr, revenue in pareto:
        pareto_rows += f"""
        <tr>
          <td><span style="font-weight:600;">{src}</span></td>
          <td class="text-right">{leads}</td>
          <td class="text-right">{payments}</td>
          <td class="text-right muted">{cvr}</td>
          <td class="text-right" style="font-weight:700;">{revenue}</td>
        </tr>
        """

    body = f"""
    <div class="page-header">
      <h1>Эффективность</h1>
      <div class="subtitle">Источники, воронки и кампании — что приводит платящих клиентов</div>
    </div>

    <div class="section">
      <!-- Фильтры -->
      <div style="display:flex; gap:10px; flex-wrap:wrap; align-items:center;">
        <div class="glass-soft" style="border-radius:14px; padding:5px; display:inline-flex;">
          <button style="padding:6px 14px; font-size:12.5px; border:none; background:transparent; cursor:pointer; color:#6b7280;">7 дней</button>
          <button style="padding:6px 14px; font-size:12.5px; border:none; background:white; border-radius:10px; cursor:pointer; font-weight:600; box-shadow:0 2px 8px -4px rgba(15,23,42,0.1);">30 дней</button>
          <button style="padding:6px 14px; font-size:12.5px; border:none; background:transparent; cursor:pointer; color:#6b7280;">90 дней</button>
        </div>
        <select class="glass-soft" style="border:none; padding:7px 14px; font-size:12.5px; border-radius:14px; color:#374151;">
          <option>Все продукты</option>
        </select>
        <select class="glass-soft" style="border:none; padding:7px 14px; font-size:12.5px; border-radius:14px; color:#374151;">
          <option>По источнику</option>
        </select>
        <div class="glass-soft" style="border-radius:14px; padding:5px; display:inline-flex;">
          <button style="padding:6px 12px; font-size:12px; border:none; background:white; border-radius:10px; cursor:pointer; font-weight:600;">Последнее касание</button>
          <button style="padding:6px 12px; font-size:12px; border:none; background:transparent; cursor:pointer; color:#6b7280;">Первое касание</button>
        </div>
      </div>

      <!-- KPI -->
      <div class="kpi-grid" style="margin-top:14px;">
        <div class="kpi-card glass-soft"><div class="kpi-label">Лиды</div><div class="kpi-value">362</div><div class="kpi-delta up">▲ +18%</div></div>
        <div class="kpi-card glass-soft"><div class="kpi-label">Оплаты</div><div class="kpi-value">61</div><div class="kpi-delta up">▲ +24%</div></div>
        <div class="kpi-card glass-soft"><div class="kpi-label">Выручка</div><div class="kpi-value gradient-text">553 040 ₽</div><div class="kpi-delta up">▲ +27%</div></div>
        <div class="kpi-card glass-soft"><div class="kpi-label">Конверсия лид→оплата</div><div class="kpi-value">16.8 %</div><div class="kpi-delta up">▲ +1.2 пп</div></div>
      </div>
    </div>

    <div class="section">
      <div class="card glass">
        <div class="card-header">
          <div>
            <div class="title">Динамика по дням</div>
            <div class="text-xs muted">Сколько лидов приходило в каждый день · разрез по источникам</div>
          </div>
          <div class="glass-soft" style="border-radius:12px; padding:3px; display:inline-flex;">
            <button style="padding:4px 10px; font-size:11.5px; border:none; background:white; border-radius:8px; cursor:pointer; font-weight:600;">Лиды</button>
            <button style="padding:4px 10px; font-size:11.5px; border:none; background:transparent; cursor:pointer; color:#6b7280;">Оплаты</button>
            <button style="padding:4px 10px; font-size:11.5px; border:none; background:transparent; cursor:pointer; color:#6b7280;">Выручка</button>
          </div>
        </div>
        <div style="padding: 16px 18px 4px;">
          {chart_svg}
        </div>
        <div style="display:flex; gap:18px; padding: 0 22px 18px; flex-wrap:wrap;">
          {legend}
        </div>
      </div>
    </div>

    <div class="section">
      <div class="card glass">
        <div class="card-header">
          <div>
            <div class="title">Топ-источников за период</div>
            <div class="text-xs muted">Сортировка по выручке. Конверсия = оплат / лидов в этой группе</div>
          </div>
        </div>
        <table class="table">
          <thead>
            <tr><th>Источник</th><th class="text-right">Лидов</th><th class="text-right">Оплат</th><th class="text-right">Конверсия</th><th class="text-right">Выручка</th></tr>
          </thead>
          <tbody>{pareto_rows}</tbody>
        </table>
      </div>
    </div>
    """
    return page_skeleton("analytics", ["Обзор", "Эффективность"], body)


# ─────────────────────────────────────────────────────────────────────────────
# LEADS
# ─────────────────────────────────────────────────────────────────────────────

LEADS_FULL = [
    ("ИП", "Иван Петров",       "@ivan_petrov",   "instagram",   "new",       "сегодня, 14:32", "alt-1"),
    ("АС", "Анна Соколова",     "@anna_s",        "instagram",   "contacted", "сегодня, 13:08", "alt-2"),
    ("ДК", "Дмитрий Кузнецов",  "@dim_k",         "youtube",     "paid",      "сегодня, 12:14", "alt-3"),
    ("МЛ", "Мария Лебедева",    "@maria_leb",     "instagram",   "new",       "сегодня, 09:47", "alt-4"),
    ("СМ", "Сергей Морозов",    "@morozov_s",     "podcast",     "contacted", "вчера, 18:45",   "alt-5"),
    ("ЕВ", "Елена Васильева",   "@helen_v",       "instagram",   "paid",      "вчера, 17:22",   "alt-1"),
    ("АИ", "Алексей Иванов",    "@alex_iv",       "youtube",     "paid",      "вчера, 15:01",   "alt-2"),
    ("ОН", "Ольга Новикова",    "@olga_nov",      "tg_chat",     "paid",      "вчера, 12:33",   "alt-3"),
    ("МП", "Михаил Попов",      "@mike_p",        "instagram",   "paid",      "вчера, 11:18",   "alt-4"),
    ("ВЗ", "Виктория Захарова", "@vika_z",        "youtube",     "contacted", "позавчера",       "alt-5"),
    ("АН", "Артём Николаев",    "@art_n",         "organic",     "new",       "позавчера",       "alt-1"),
    ("ТК", "Татьяна Костина",   "@tanya_k",       "instagram",   "closed",    "3 дня назад",     "alt-2"),
]


def page_leads() -> str:
    rows = ""
    for initials, name, username, source, status, when, alt in LEADS_FULL:
        color, text = STATUS_TR[status]
        source_pill_color = {"instagram": "rose", "youtube": "amber", "tg_chat": "indigo", "podcast": "green", "organic": "gray"}.get(source, "gray")
        rows += f"""
        <tr>
          <td>
            <div class="avatar-cell">
              <div class="avatar-mini {alt}">{initials}</div>
              <div>
                <div style="font-weight:600;">{name}</div>
                <div class="text-xs muted mono">{username}</div>
              </div>
            </div>
          </td>
          <td class="text-sm">Премиум-клуб</td>
          <td><span class="pill {source_pill_color}">{source}</span></td>
          <td><span class="pill {color}">{text}</span></td>
          <td class="text-sm muted text-right">{when}</td>
        </tr>
        """

    body = f"""
    <div class="page-header">
      <h1>Заявки</h1>
      <div class="subtitle">Все заявки от пользователей, отсортированы по дате</div>
    </div>

    <div class="section">
      <!-- Tabs status -->
      <div style="display:flex; gap:8px;">
        <button style="padding:8px 16px; font-size:13px; border:none; background:white; border-radius:12px; cursor:pointer; font-weight:600; box-shadow:0 4px 12px -6px rgba(15,23,42,0.1);">
          Все <span style="background:#e5e7eb; color:#6b7280; font-size:11px; padding:1px 7px; border-radius:8px; margin-left:6px; font-weight:700;">132</span>
        </button>
        <button style="padding:8px 16px; font-size:13px; border:none; background:transparent; border-radius:12px; cursor:pointer; color:#6b7280;">
          Новые <span style="background:#fef3c7; color:#92400e; font-size:11px; padding:1px 7px; border-radius:8px; margin-left:6px; font-weight:700;">12</span>
        </button>
        <button style="padding:8px 16px; font-size:13px; border:none; background:transparent; border-radius:12px; cursor:pointer; color:#6b7280;">Связались <span style="color:#9ca3af; font-size:11px; margin-left:6px;">31</span></button>
        <button style="padding:8px 16px; font-size:13px; border:none; background:transparent; border-radius:12px; cursor:pointer; color:#6b7280;">Оплачено <span style="color:#9ca3af; font-size:11px; margin-left:6px;">71</span></button>
        <button style="padding:8px 16px; font-size:13px; border:none; background:transparent; border-radius:12px; cursor:pointer; color:#6b7280;">Закрытые <span style="color:#9ca3af; font-size:11px; margin-left:6px;">18</span></button>
      </div>

      <div class="card glass" style="margin-top:14px;">
        <table class="table">
          <thead>
            <tr><th>Клиент</th><th>Продукт</th><th>Источник</th><th>Статус</th><th class="text-right">Получена</th></tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </div>
    """
    return page_skeleton("leads", ["Обзор", "Заявки"], body)


# ─────────────────────────────────────────────────────────────────────────────
# SUBSCRIPTIONS
# ─────────────────────────────────────────────────────────────────────────────

SUBS = [
    ("ДК", "Дмитрий Кузнецов",  "@dim_k",    "Премиум-клуб", "active",  "до 30.11.2026", "+6 мес назад", "alt-3"),
    ("ЕВ", "Елена Васильева",   "@helen_v",  "Премиум-клуб", "active",  "до 22.08.2026", "+3 мес назад", "alt-1"),
    ("АИ", "Алексей Иванов",    "@alex_iv",  "Премиум-клуб", "active",  "до 21.05.2027", "+12 мес назад","alt-2"),
    ("ОН", "Ольга Новикова",    "@olga_nov", "Премиум-клуб", "active",  "до 21.11.2026", "+6 мес назад", "alt-3"),
    ("МП", "Михаил Попов",      "@mike_p",   "Премиум-клуб", "active",  "до 20.08.2026", "+3 мес назад", "alt-4"),
    ("СО", "Светлана Орлова",   "@sveta_o",  "Премиум-клуб", "expiring",  "до 28.05.2026 (через 5 дней)", "+3 мес назад", "alt-5"),
    ("РК", "Роман Куприянов",   "@roman_k",  "Премиум-клуб", "expiring",  "до 30.05.2026 (через 7 дней)", "+3 мес назад", "alt-1"),
    ("НГ", "Наталья Громова",   "@nataly_g", "Премиум-клуб", "expired", "истекла 14.05.2026", "—",           "alt-2"),
]

SUB_STATUS_TR = {
    "active":   ("green",  "активна"),
    "expiring": ("amber",  "скоро истекает"),
    "expired":  ("gray",   "истекла"),
}


def page_subscriptions() -> str:
    rows = ""
    for initials, name, username, product, status, until, started, alt in SUBS:
        color, text = SUB_STATUS_TR[status]
        rows += f"""
        <tr>
          <td>
            <div class="avatar-cell">
              <div class="avatar-mini {alt}">{initials}</div>
              <div>
                <div style="font-weight:600;">{name}</div>
                <div class="text-xs muted mono">{username}</div>
              </div>
            </div>
          </td>
          <td class="text-sm">{product}</td>
          <td><span class="pill {color}">{text}</span></td>
          <td class="text-sm">{until}</td>
          <td class="text-sm muted">{started}</td>
          <td class="text-right">
            <button style="padding:5px 12px; font-size:11.5px; background:#eef2ff; color:#4338ca; border:none; border-radius:8px; cursor:pointer; font-weight:600;">Продлить</button>
          </td>
        </tr>
        """

    body = f"""
    <div class="page-header">
      <h1>Подписки</h1>
      <div class="subtitle">89 активных, 3 скоро истекают, 12 истёкших за последние 30 дней</div>
    </div>

    <div class="section">
      <div class="kpi-grid">
        <div class="kpi-card glass-soft"><div class="kpi-label">Активные</div><div class="kpi-value">89</div><div class="kpi-delta up">▲ +12 за месяц</div></div>
        <div class="kpi-card glass-soft"><div class="kpi-label">Истекают в 7 дней</div><div class="kpi-value">8</div><div class="text-xs muted" style="margin-top:6px;">Подходящий момент для реактивации</div></div>
        <div class="kpi-card glass-soft"><div class="kpi-label">Доход в месяц</div><div class="kpi-value gradient-text">458 410 ₽</div><div class="kpi-delta up">▲ +27%</div></div>
        <div class="kpi-card glass-soft"><div class="kpi-label">Средний чек</div><div class="kpi-value">7 511 ₽</div><div class="text-xs muted" style="margin-top:6px;">по платежам за 30 дней</div></div>
      </div>

      <div class="card glass" style="margin-top:14px;">
        <div class="card-header">
          <div class="title">Список подписок</div>
          <div style="display:flex; gap:8px;">
            <button style="padding:6px 12px; font-size:11.5px; background:white; border:1px solid #e5e7eb; border-radius:8px; cursor:pointer; font-weight:600;">Активные</button>
            <button style="padding:6px 12px; font-size:11.5px; background:transparent; border:1px solid #e5e7eb; border-radius:8px; cursor:pointer; color:#6b7280;">Все</button>
          </div>
        </div>
        <table class="table">
          <thead>
            <tr><th>Клиент</th><th>Продукт</th><th>Статус</th><th>До какой даты</th><th>Куплено</th><th></th></tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </div>
    """
    return page_skeleton("subscriptions", ["Обзор", "Подписки"], body)


# ─────────────────────────────────────────────────────────────────────────────

def main():
    pages = {
        "dashboard.html":     page_dashboard(),
        "analytics.html":     page_analytics(),
        "leads.html":         page_leads(),
        "subscriptions.html": page_subscriptions(),
    }
    for name, html in pages.items():
        path = OUT / name
        path.write_text(html, encoding="utf-8")
        print(f"✓ {path.name} ({path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
