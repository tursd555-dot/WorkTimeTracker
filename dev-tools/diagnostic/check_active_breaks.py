#!/usr/bin/env python3
# coding: utf-8
"""
Проверка метода _get_active_breaks()
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
print("ПРОВЕРКА _get_active_breaks()")
print("=" * 80)
print()

# Инициализация
sheets = get_sheets_api()
break_mgr = BreakManager(sheets)

# Проверяем активные перерывы
print("Проверка активных перерывов в BreakUsageLog...")

# Прямая проверка
ws = sheets.get_worksheet("BreakUsageLog")
rows = sheets._read_table(ws)

today = date.today().isoformat()

print(f"Всего записей в BreakUsageLog: {len(rows)}")
print()

# Ищем записи без EndTime за сегодня
active = [r for r in rows if not r.get('EndTime') and r.get('StartTime', '').startswith(today)]

print(f"Активные перерывы (без EndTime) за сегодня: {len(active)}")


if active:
    print()
    print("АКТИВНЫЕ ПЕРЕРЫВЫ:")
    for r in active:
            print(f"  - {r.get('Email')}: {r.get('BreakType')}")
            print(f"    StartTime: {r.get('StartTime')}")
            print(f"    EndTime: {r.get('EndTime')}")
            print()
    
    print("=" * 80)
    print("ПРОБЛЕМА: Метод _get_active_breaks() НЕ СУЩЕСТВУЕТ!")
    print("=" * 80)
    print()
    print("Нужно добавить метод get_all_active_breaks() в break_manager.py")
else:
    print()
    print("❌ Активных перерывов НЕТ")
    print()
    print("Попробуйте:")
    print("  1. Переключитесь на 'Перерыв' в user_app")
    print("  2. Подождите 5 секунд")
    print("  3. Запустите скрипт снова")

print()