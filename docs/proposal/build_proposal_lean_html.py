"""
Lean-версия КП. Импортирует слайды из build_proposal_html, переопределяет
часы / цены / ставку / некоторые формулировки. Выход:
  docs/proposal/Grammy_KP_Lean.html  →  Grammy_KP_Lean.pdf
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import build_proposal_html as bp

LEAN_RATE = 5000

# Часы взяты из расчёта lean.py (target-based, после rounding adjustment)
LEAN_HOURS = {
    "M01": 5,  "M02": 9,  "M03": 13, "M04": 6,
    "M05": 5,  "M06": 14, "M07": 28, "M08": 5,
    "M09": 9,  "M10": 16, "M11": 11, "M12": 13,
    "M13": 4,  "M14": 6,  "M15": 7,  "M16": 12,
}

# Переопределяем брифы модулей с новыми часами
LEAN_MODULES_BRIEF = []
for m in bp.MODULES_BRIEF:
    new = dict(m)
    new["hours"] = LEAN_HOURS.get(m["id"], m["hours"])
    LEAN_MODULES_BRIEF.append(new)

BASE_IDS = ["M01","M02","M03","M04","M05","M06","M11","M12","M13"]
STD_IDS  = BASE_IDS + ["M07","M08","M09","M10","M15"]
PRM_IDS  = STD_IDS  + ["M14","M16"]


def _hours_for(ids: list[str]) -> int:
    return sum(m["hours"] for m in LEAN_MODULES_BRIEF if m["id"] in ids)


LEAN_PACKAGES = [
    {
        "name": "Базовый · MVP",
        "hours": _hours_for(BASE_IDS),
        "price": _hours_for(BASE_IDS) * LEAN_RATE,
        "features": [
            "Подключение ботов, каналов, продуктов",
            "Заявки и ручное создание платежей",
            "Авто-выдача доступа после оплаты",
            "Базовая админка + брендинг Grammy",
            "Telegram-бот с deep-link",
            "Развёртывание под ключ, SSL",
        ],
    },
    {
        "name": "Стандарт",
        "hours": _hours_for(STD_IDS),
        "price": _hours_for(STD_IDS) * LEAN_RATE,
        "featured": True,
        "features": [
            "Всё из «Базового»",
            "Воронки прогрева + Студия с превью",
            "Лидмагниты с drag-n-drop",
            "Tracking-ссылки и кодовые слова",
            "Аналитика с Recharts и health-блоком",
            "Observability: метрики, логи, алерты",
        ],
    },
    {
        "name": "Премиум",
        "hours": _hours_for(PRM_IDS),
        "price": _hours_for(PRM_IDS) * LEAN_RATE,
        "features": [
            "Всё из «Стандарта»",
            "Аудит-журнал с маскированием секретов",
            "Покрытие тестами критичных модулей",
            "GitHub Actions CI/CD",
            "Pre-commit + security сканирование",
            "Гарантия исправления багов 3 мес.",
        ],
    },
]


def slide_roadmap_lean(num: int, total: int) -> str:
    """4-недельный roadmap вместо 12-недельного."""
    return f"""
    <section class="slide brand-band">
      <h2 class="section">Дорожная карта</h2>
      <h1 class="slide-title">Поставка за 4 недели · фиксированный срок</h1>
      <div class="roadmap">
        <div class="phase">
          <div class="phase-num">Неделя 1</div>
          <h4>Фундамент</h4>
          <ul>
            <li>Инфраструктура и SSL (M01)</li>
            <li>Аутентификация + RBAC (M02)</li>
            <li>Каталог: боты/каналы/продукты (M03)</li>
            <li>Бренд и базовый UI (M12, M13)</li>
          </ul>
        </div>
        <div class="phase">
          <div class="phase-num">Неделя 2</div>
          <h4>Продажи</h4>
          <ul>
            <li>Telegram-бот мульти-бот (M11)</li>
            <li>Пользователи + first-touch (M04)</li>
            <li>Заявки (M05)</li>
            <li>Платежи и подписки (M06)</li>
          </ul>
        </div>
        <div class="phase">
          <div class="phase-num">Неделя 3</div>
          <h4>Автоматизация</h4>
          <ul>
            <li>Воронки + Студия (M07)</li>
            <li>Лидмагниты (M08)</li>
            <li>Точки входа: tracking, триггеры (M09)</li>
            <li>Аналитика (M10)</li>
          </ul>
        </div>
        <div class="phase">
          <div class="phase-num">Неделя 4</div>
          <h4>Качество и приёмка</h4>
          <ul>
            <li>Observability и алерты (M15)</li>
            <li>Аудит-журнал (M14, по пакету)</li>
            <li>Тесты и CI/CD (M16, по пакету)</li>
            <li>Передача и обучение команды</li>
          </ul>
        </div>
      </div>
      {bp.footer(num, total)}
    </section>
    """


def slide_problem_lean(num: int, total: int) -> str:
    """Слегка скорректированный messaging — про компактную поставку."""
    return f"""
    <section class="slide brand-band">
      <h2 class="section">Контекст</h2>
      <h1 class="slide-title">Инфобиз — это уже инфраструктура</h1>
      <div class="grid-2" style="margin-top: 12mm;">
        <div>
          <p class="lead" style="font-size: 14pt;">
            Эксперт продаёт доступ в закрытый Telegram-канал. Тысячи кликов
            из Instagram, YouTube, рассылок и эфиров. Для управляемой конверсии
            нужны: атрибуция каждого касания, прогрев воронкой, моментальная
            выдача доступа после оплаты, автоматический отзыв по истечении.
          </p>
        </div>
        <div>
          <p class="lead" style="font-size: 14pt;">
            Готовых SaaS-решений под русский Telegram-инфобиз нет.
            Grammy решает задачу целиком: от бота до Pareto-отчёта по UTM.
            Поставляется компактной командой за 4 недели с фиксированной
            ценой и гарантией.
          </p>
        </div>
      </div>
      <div class="grid-4" style="margin-top: 14mm;">
        <div class="card"><div class="kpi">15</div><div class="kpi-label">сущностей в БД</div></div>
        <div class="card"><div class="kpi">~80</div><div class="kpi-label">API-эндпоинтов</div></div>
        <div class="card"><div class="kpi">21</div><div class="kpi-label">экран в админке</div></div>
        <div class="card"><div class="kpi">4 нед.</div><div class="kpi-label">от старта до сдачи</div></div>
      </div>
      {bp.footer(num, total)}
    </section>
    """


def slide_pricing_lean(num: int, total: int) -> str:
    """Версия с lean-ценами и формулировкой про фикс."""
    cards = ""
    for p in LEAN_PACKAGES:
        featured = ' featured' if p.get('featured') else ''
        badge = '<div class="badge">Рекомендуется</div>' if p.get('featured') else ''
        feats = "".join(f'<li>{f}</li>' for f in p['features'])
        price_str = f"{p['price']:,} ₽".replace(",", " ")
        cards += f"""
        <div class="pricing-card{featured}">
          {badge}
          <div class="pkg-name">{p['name']}</div>
          <div class="pkg-price">{price_str}</div>
          <div class="pkg-hours">{p['hours']} часов · фикс-цена, без часовых ставок</div>
          <ul>{feats}</ul>
        </div>
        """
    rate_str = f"{LEAN_RATE:,}".replace(",", " ")
    return f"""
    <section class="slide brand-band">
      <h2 class="section">Стоимость</h2>
      <h1 class="slide-title">Три пакета · фиксированная цена</h1>
      <div class="grid-3">{cards}</div>
      <p style="font-size: 10pt; color: #6b7280; margin-top: 8mm;">
        Внутренняя ставка калькуляции: {rate_str} ₽/час (включает разработку, дизайн, QA, DevOps).
        Заказчику выставляется <strong>фиксированная цена</strong> за пакет — без сюрпризов по часам.
        Поэтапная оплата: 40% при старте · 40% при промежуточной приёмке · 20% при сдаче.
      </p>
      {bp.footer(num, total)}
    </section>
    """


def slide_guarantees_lean(num: int, total: int) -> str:
    return f"""
    <section class="slide brand-band">
      <h2 class="section">Что входит в стоимость</h2>
      <h1 class="slide-title">Продукт под ключ, без скрытых затрат</h1>
      <div class="grid-2" style="margin-top: 10mm;">
        <div>
          <ul class="feature-list">
            <li>Исходный код в Git-репозитории под управление заказчика</li>
            <li>Развёртывание на сервере заказчика «под ключ»</li>
            <li>HTTPS + автопродление SSL-сертификата</li>
            <li>ТЗ, гайд по использованию, документация</li>
            <li>Обучающая сессия с командой заказчика (2 часа)</li>
          </ul>
        </div>
        <div>
          <ul class="feature-list">
            <li>Покрытие тестами критичных модулей (Премиум)</li>
            <li>CI/CD pipeline в GitHub Actions (Премиум)</li>
            <li>Мониторинг и алерты «из коробки» (Стандарт+)</li>
            <li>Гарантия на исправление багов: 3 месяца после сдачи</li>
            <li>Опция сопровождения: 30 000 ₽/мес на бэклог</li>
          </ul>
        </div>
      </div>
      <div class="cta-card">
        <h3>Готовы стартовать?</h3>
        <p>Подписываем договор с фиксированной ценой и сроком. Стартуем первую
        неделю в течение 3 рабочих дней с момента подписания.</p>
      </div>
      {bp.footer(num, total)}
    </section>
    """


# ─────────────────────────────────────────────────────────────────────────────

def build_html() -> str:
    total = 11
    parts = [
        f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Grammy — Коммерческое предложение</title>
<style>{bp.CSS}</style>
</head>
<body>""",
        bp.slide_cover(),                              # 1
        slide_problem_lean(2, total),                  # 2 (свой)
        bp.slide_architecture(3, total),               # 3
        bp.slide_feature(                               # 4
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
        bp.slide_feature(                               # 5
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
            note="Composite SQL индексы + DISTINCT-подзапросы. 1000+ оплат за 30 дней — менее 2 секунд.",
        ),
        bp.slide_feature(                               # 6
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
        bp.slide_modules(7, total, LEAN_MODULES_BRIEF), # 7 (наши часы)
        slide_pricing_lean(8, total),                  # 8 (свой)
        slide_roadmap_lean(9, total),                  # 9 (свой)
        slide_guarantees_lean(10, total),              # 10 (свой)
        bp.slide_contact(11, total),                   # 11
        "</body></html>",
    ]
    return "".join(parts)


def main():
    out = Path(__file__).resolve().parent / "Grammy_KP_Lean.html"
    out.write_text(build_html(), encoding="utf-8")
    size_kb = out.stat().st_size // 1024
    print(f"✓ HTML Lean: {out} ({size_kb} KB)")


if __name__ == "__main__":
    main()
