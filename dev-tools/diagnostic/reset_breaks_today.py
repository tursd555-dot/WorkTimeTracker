#!/usr/bin/env python3
# coding: utf-8
"""
Полный сброс перерывов за сегодня

Удаляет все записи за сегодняшний день из BreakUsageLog
"""
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api_adapter import get_sheets_api

print("=" * 80)
print("СБРОС ПЕРЕРЫВОВ ЗА СЕГОДНЯ")
print("=" * 80)
print()

sheets = get_sheets_api()
ws = sheets.get_worksheet("BreakUsageLog")

all_values = ws.get_all_values()

if len(all_values) < 2:
    print("✓ Таблица уже пуста")
    sys.exit(0)

header = all_values[0]
today = datetime.now().date().isoformat()

print(f"Сегодня: {today}")
print()

# Находим сегодняшние записи
today_rows = []
start_idx = header.index("StartTime")

for idx in range(1, len(all_values)):
    row = all_values[idx]
    if idx < len(row):
        start_time = row[start_idx] if start_idx < len(row) else ""
        if start_time.startswith(today):
            today_rows.append(idx + 1)  # +1 т.к. нумерация с 1

if not today_rows:
    print("✓ Нет записей за сегодня")
    sys.exit(0)

print(f"Найдено записей за сегодня: {len(today_rows)}")
print(f"Строки: {today_rows}")
print()

confirm = input("Удалить эти строки? (yes/no): ").strip().lower()

if confirm != "yes":
    print("Отменено")
    sys.exit(0)

print()
print("Удаление строк...")

# Удаляем с конца (чтобы номера не сбивались)
for row_num in sorted(today_rows, reverse=True):
    ws.delete_rows(row_num)
    print(f"  ✓ Удалена строка {row_num}")

print()
print("=" * 80)
print("✓ СБРОС ЗАВЕРШЁН")
print("=" * 80)
print()
print("Теперь можно запустить:")
print("  python diagnose_breaks.py")