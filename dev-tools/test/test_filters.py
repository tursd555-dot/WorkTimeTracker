#!/usr/bin/env python3
# coding: utf-8
"""
Тест фильтров для аналитики нарушений
"""
import sys
from pathlib import Path
from datetime import date

ROOT = Path(__file__).parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api_adapter import get_sheets_api
from admin_app.break_manager import BreakManager

print("=" * 80)
print("ТЕСТ ФИЛЬТРОВ АНАЛИТИКИ")
print("=" * 80)
print()

sheets = get_sheets_api()
break_mgr = BreakManager(sheets)

# Параметры из UI (20.11.2025 - 27.11.2025)
date_from = "2025-11-20"
date_to = "2025-11-27"

print(f"Фильтры:")
print(f"  Дата от: {date_from}")
print(f"  Дата до: {date_to}")
print(f"  Сотрудник: (пусто)")
print(f"  Группа: Все группы")
print(f"  Тип нарушения: Все типы")
print()

# Вызов без фильтров
print("1. БЕЗ ФИЛЬТРОВ:")
all_violations = break_mgr.get_violations_report()
print(f"   Результат: {len(all_violations)} нарушений")
if all_violations:
    print(f"   Первое: {all_violations[0]}")
print()

# Вызов С фильтром по датам
print("2. С ФИЛЬТРОМ ПО ДАТАМ:")
filtered = break_mgr.get_violations_report(
    date_from=date_from,
    date_to=date_to
)
print(f"   Результат: {len(filtered)} нарушений")
if filtered:
    for v in filtered[:3]:
        print(f"   - {v.get('Timestamp')}: {v.get('Email')} | {v.get('ViolationType')}")
else:
    print("   ПУСТО!")
print()

# Проверим что вообще есть в BreakViolations
print("3. ПРЯМАЯ ПРОВЕРКА BREAKVIOLATIONS:")
ws = sheets.get_worksheet("BreakViolations")
rows = sheets._read_table(ws)
print(f"   Всего записей: {len(rows)}")

if rows:
    print()
    print("   Примеры записей:")
    for r in rows[:5]:
        ts = r.get('Timestamp', '')
        email = r.get('Email', '')
        vtype = r.get('ViolationType', '')
        print(f"   - {ts}: {email} | {vtype}")
    
    # Проверим форматы дат
    print()
    print("   АНАЛИЗ ФОРМАТА ДАТ:")
    for r in rows[:3]:
        ts = r.get('Timestamp', '')
        print(f"   Timestamp: '{ts}'")
        print(f"   Длина: {len(ts)}")
        print(f"   Начинается с '2025-11-27': {ts.startswith('2025-11-27')}")
        print(f"   Срез [:10]: '{ts[:10]}'")
        print()

print("=" * 80)
print("ВЫВОДЫ:")
print("=" * 80)
print()
print("Если 'БЕЗ ФИЛЬТРОВ' показывает записи,")
print("но 'С ФИЛЬТРОМ ПО ДАТАМ' возвращает пусто,")
print("то проблема в логике фильтрации метода get_violations_report()")
print()