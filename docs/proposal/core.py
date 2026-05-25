"""
Core-версия ТЗ/сметы: только то, что заказчик реально просил.
Bot собирает заявки, связь с менеджером, ввод платежей, авто-доступ/кик.

Запуск:
  python3 docs/proposal/core.py

Выход:
  docs/proposal/Grammy_TZ_Core.docx
  docs/proposal/Grammy_Smeta_Core.xlsx

Принцип:
- Из MODULES беру только core-subset (без воронок, лидмагнитов, аналитики,
  аудита, observability, тестов).
- Целевые часы — для 2 недель работы senior с современным стеком.
- Ставка 4 000 ₽/ч → итог в районе 140 000 ₽.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import generate

CORE_IDS = {"M01", "M02", "M03", "M04", "M05", "M06", "M11", "M12", "M13"}

# Целевые часы по модулю (для core-конфигурации, ~140K при 4000 ₽/ч).
TARGET_HOURS = {
    "M01": 3,    # инфра — по шаблону, полдня
    "M02": 4,    # auth — однодневная задача
    "M03": 6,    # каталог — 3 CRUD-формы
    "M04": 3,    # пользователи — минимум: поиск + контакты
    "M05": 4,    # заявки — таблица + статусы
    "M06": 8,    # платежи + подписки — ключевой модуль (авто-доступ)
    "M11": 5,    # tg-бот — простой polling, deep-link
    "M12": 4,    # UI/UX — минимальный sidebar, общие формы
    "M13": 3,    # брендинг — favicon + название
}

CORE_RATE = 3500  # ₽/ч (стандартная для прямого заказчика)


def _scale_field(value: int, scale: float) -> int:
    if not value:
        return 0
    return round(value * scale)


def main():
    # 1. Фильтруем модули и скейлим часы под target
    all_modules = copy.deepcopy(generate.MODULES)
    new_modules = [m for m in all_modules if m.id in CORE_IDS]

    for m in new_modules:
        target = TARGET_HOURS.get(m.id)
        if target is None or m.total_hours == 0:
            continue
        s = target / m.total_hours
        for t in m.tasks:
            t.backend = _scale_field(t.backend, s)
            t.frontend = _scale_field(t.frontend, s)
            t.design = _scale_field(t.design, s)
            t.devops = _scale_field(t.devops, s)
            t.qa = _scale_field(t.qa, s)

        # Компенсируем округление вниз
        diff = target - m.total_hours
        if diff > 0 and m.tasks:
            biggest = max(m.tasks, key=lambda t: t.total)
            field = max(
                ("backend", "frontend", "design", "devops", "qa"),
                key=lambda f: getattr(biggest, f),
            )
            setattr(biggest, field, getattr(biggest, field) + diff)

    # 2. Подменяем в generate
    generate.MODULES = new_modules
    generate.HOURLY_RATE = CORE_RATE
    generate.DOCX_PATH = generate.OUT_DIR / f"{generate.PROJECT_NAME}_TZ_Core.docx"
    generate.XLSX_PATH = generate.OUT_DIR / f"{generate.PROJECT_NAME}_Smeta_Core.xlsx"

    docx_path = generate.generate_docx()
    xlsx_path = generate.generate_xlsx()
    print(f"✓ ТЗ Core:    {docx_path}")
    print(f"✓ Смета Core: {xlsx_path}")
    print()

    print(f"Ставка: {CORE_RATE:,} ₽/ч".replace(",", " "))
    print(f"{'ID':<5} {'Модуль':<40} {'Часы':>6} {'Цена':>14}")
    print("─" * 70)
    grand = 0
    for m in new_modules:
        cost = m.total_hours * CORE_RATE
        grand += cost
        print(f"{m.id:<5} {m.title[:40]:<40} {m.total_hours:>6} {cost:>10,} ₽".replace(",", " "))
    print("─" * 70)
    total_h = sum(m.total_hours for m in new_modules)
    print(f"{'ИТОГО CORE':<46} {total_h:>6} {grand:>10,} ₽".replace(",", " "))


if __name__ == "__main__":
    main()
