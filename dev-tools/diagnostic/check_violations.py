#!/usr/bin/env python3
# coding: utf-8
"""
Проверка данных в BreakViolations для диагностики аналитики
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api_adapter import get_sheets_api
from datetime import date

print("=" * 80)
print("ПРОВЕРКА BreakViolations")
print("=" * 80)
print()

sheets = get_sheets_api()

# Проверяем BreakViolations
print("1. Содержимое BreakViolations:")
print("-" * 80)
try:
    ws = sheets.get_worksheet("BreakViolations")
    rows = sheets._read_table(ws)
    
    if not rows:
        print("❌ ТАБЛИЦА ПУСТА!")
        print()
        print("Это причина почему аналитика пустая.")
        print("Нарушения должны логироваться при start_break() и end_break()")
    else:
        print(f"✓ Найдено записей: {len(rows)}")
        print()
        
        today = date.today().isoformat()
        today_violations = [r for r in rows if r.get("Timestamp", "").startswith(today)]
        
        print(f"Сегодняшних записей: {len(today_violations)}")
        print()
        
        if today_violations:
            print("ЗАПИСИ ЗА СЕГОДНЯ:")
            for v in today_violations:
                print(f"  - {v.get('Timestamp')}: {v.get('Email')} | {v.get('ViolationType')} | {v.get('Details')}")
        else:
            print("❌ НЕТ ЗАПИСЕЙ ЗА СЕГОДНЯ")
            print()
            print("Последние 5 записей:")
            for v in rows[-5:]:
                print(f"  - {v.get('Timestamp')}: {v.get('Email')} | {v.get('ViolationType')}")

except Exception as e:
    print(f"❌ ОШИБКА: {e}")

print()
print("=" * 80)

# Проверяем BreakUsageLog
print("2. Содержимое BreakUsageLog:")
print("-" * 80)
try:
    ws = sheets.get_worksheet("BreakUsageLog")
    rows = sheets._read_table(ws)
    
    print(f"✓ Найдено записей: {len(rows)}")
    print()
    
    today = date.today().isoformat()
    today_usage = [r for r in rows if r.get("StartTime", "").startswith(today)]
    
    print(f"Сегодняшних записей: {len(today_usage)}")
    
    if today_usage:
        print()
        print("ЗАПИСИ ЗА СЕГОДНЯ:")
        for u in today_usage:
            print(f"  - {u.get('Email')}: {u.get('BreakType')} | {u.get('StartTime')} - {u.get('EndTime')} | {u.get('ActualDuration')} мин")

except Exception as e:
    print(f"❌ ОШИБКА: {e}")

print()
print("=" * 80)
print("3. ТЕСТ: get_violations_report()")
print("=" * 80)

try:
    from admin_app.break_manager import BreakManager
    
    break_mgr = BreakManager(sheets)
    
    today = date.today().isoformat()
    
    # Тест 1: Все нарушения за сегодня
    violations = break_mgr.get_violations_report(
        date_from=today,
        date_to=today
    )
    
    print(f"Все нарушения за сегодня: {len(violations)}")
    
    # Тест 2: Нарушения для конкретного email
    violations_filtered = break_mgr.get_violations_report(
        email="9@ya.ru",
        date_from=today,
        date_to=today
    )
    
    print(f"Нарушения для 9@ya.ru: {len(violations_filtered)}")
    
    if violations:
        print()
        print("Примеры нарушений:")
        for v in violations[:5]:
            print(f"  - {v.get('Timestamp')}: {v.get('Email')} | {v.get('ViolationType')}")
    else:
        print()
        print("❌ get_violations_report() возвращает пустой список!")
        print("   Это причина пустой аналитики")

except Exception as e:
    print(f"❌ ОШИБКА: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 80)
print("ДИАГНОЗ:")
print("=" * 80)
print("""
Если BreakViolations пустая:
  → Нарушения не логируются
  → Проблема в методах _log_violation() или start_break()/end_break()

Если get_violations_report() возвращает пустой список:
  → Проблема в фильтрации данных
  → Проверить формат даты в Timestamp

Если данные есть, но аналитика пустая:
  → Проблема в break_analytics_tab.py
  → Проверить apply_filters()
""")