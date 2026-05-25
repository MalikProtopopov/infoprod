"""
Lean-версия ТЗ/сметы: пересчёт часов под «один senior + современный стек»,
ставка 5000 ₽/ч, итог в районе 700K ₽ за полный пакет.

Запуск:
  python3 docs/proposal/lean.py

Выход:
  docs/proposal/Grammy_TZ_Lean.docx
  docs/proposal/Grammy_Smeta_Lean.xlsx

Логика: импортируем оригинальные MODULES (с задачами и часами) и применяем
к каждой задаче понижающий коэффициент SCALE по модулю. Часы каждого ресурса
(backend / frontend / design / devops / qa) скейлим пропорционально,
с округлением и минимумом 1 час для непустых значений.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import generate

# Коэффициент уменьшения часов по модулям.
# Подбирается так, чтобы итог был ~140 часов на полный пакет.
# Целевые часы по модулю (для одного senior с современным AI-стеком).
# Скейл задач внутри модуля считается как (TARGET / current_total).
TARGET_HOURS = {
    "M01": 5,    # инфра «по шаблону»
    "M02": 8,
    "M03": 12,
    "M04": 6,
    "M05": 5,
    "M06": 14,
    "M07": 28,   # Студия — все ещё самый дорогой модуль
    "M08": 5,
    "M09": 9,
    "M10": 16,   # аналитика
    "M11": 10,
    "M12": 12,
    "M13": 4,
    "M14": 6,
    "M15": 7,
    "M16": 12,   # QA
}

LEAN_RATE = 5000  # ₽/ч (senior tier)


def _scale_field(value: int, scale: float) -> int:
    """Скейлим без min=1: мелкие подзадачи могут схлопнуться в ноль."""
    if not value:
        return 0
    return round(value * scale)


def main():
    # 1. Скейлим часы в копии MODULES под целевой total
    new_modules = copy.deepcopy(generate.MODULES)
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

        # Если из-за округления вниз итог получился сильно меньше target —
        # подбросим разницу в самую тяжёлую задачу модуля.
        diff = target - m.total_hours
        if diff > 0 and m.tasks:
            biggest = max(m.tasks, key=lambda t: t.total)
            # докидываем в самое тяжёлое поле этой задачи
            field = max(
                ("backend", "frontend", "design", "devops", "qa"),
                key=lambda f: getattr(biggest, f),
            )
            setattr(biggest, field, getattr(biggest, field) + diff)

    # 2. Подменяем в модуле generate глобальные значения
    generate.MODULES = new_modules
    generate.HOURLY_RATE = LEAN_RATE
    generate.DOCX_PATH = generate.OUT_DIR / f"{generate.PROJECT_NAME}_TZ_Lean.docx"
    generate.XLSX_PATH = generate.OUT_DIR / f"{generate.PROJECT_NAME}_Smeta_Lean.xlsx"

    # 3. Запускаем стандартные генераторы
    docx_path = generate.generate_docx()
    xlsx_path = generate.generate_xlsx()
    print(f"✓ ТЗ Lean:    {docx_path}")
    print(f"✓ Смета Lean: {xlsx_path}")
    print()

    # 4. Сводка
    print(f"Ставка: {LEAN_RATE:,} ₽/ч".replace(",", " "))
    print(f"{'ID':<5} {'Модуль':<40} {'Часы':>6} {'Цена':>14}")
    print("─" * 70)
    grand = 0
    for m in new_modules:
        cost = m.total_hours * LEAN_RATE
        grand += cost
        print(f"{m.id:<5} {m.title[:40]:<40} {m.total_hours:>6} {cost:>10,} ₽".replace(",", " "))
    print("─" * 70)
    total_h = sum(m.total_hours for m in new_modules)
    print(f"{'ИТОГО':<46} {total_h:>6} {grand:>10,} ₽".replace(",", " "))

    # Пакеты
    print()
    BASE_IDS = {"M01","M02","M03","M04","M05","M06","M11","M12","M13"}
    STD_IDS  = BASE_IDS | {"M07","M08","M09","M10","M15"}
    PRM_IDS  = STD_IDS  | {"M14","M16"}
    for name, ids in [("Базовый", BASE_IDS), ("Стандарт", STD_IDS), ("Премиум", PRM_IDS)]:
        h = sum(m.total_hours for m in new_modules if m.id in ids)
        c = h * LEAN_RATE
        print(f"  {name:<10} {h:>4} ч  →  {c:>10,} ₽".replace(",", " "))


if __name__ == "__main__":
    main()
