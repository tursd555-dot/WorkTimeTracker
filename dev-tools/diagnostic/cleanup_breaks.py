#!/usr/bin/env python3
# coding: utf-8
"""
Очистка старых незавершённых записей в BreakUsageLog

Находит записи без EndTime и удаляет или завершает их
"""
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api_adapter import get_sheets_api

print("=" * 80)
print("ОЧИСТКА СТАРЫХ НЕЗАВЕРШЁННЫХ ПЕРЕРЫВОВ")
print("=" * 80)
print()

# Инициализация
sheets = get_sheets_api()
ws = sheets.get_worksheet("BreakUsageLog")

print("Загрузка данных из BreakUsageLog...")
all_values = ws.get_all_values()

if len(all_values) < 2:
    print("Таблица пуста или содержит только заголовок")
    sys.exit(0)

header = all_values[0]

try:
    email_idx = header.index("Email")
    start_idx = header.index("StartTime")
    end_idx = header.index("EndTime")
    break_type_idx = header.index("BreakType")
except ValueError as e:
    print(f"ERROR: Не найдена колонка: {e}")
    sys.exit(1)

print(f"✓ Загружено строк: {len(all_values) - 1}")
print()

# Ищем незавершённые записи
incomplete = []
today = datetime.now().date().isoformat()

for idx in range(1, len(all_values)):
    row = all_values[idx]
    if len(row) > max(email_idx, start_idx, end_idx, break_type_idx):
        email = row[email_idx]
        start_time = row[start_idx]
        end_time = row[end_idx] if end_idx < len(row) else ""
        break_type = row[break_type_idx]
        
        # Если нет EndTime
        if not end_time and start_time:
            is_today = start_time.startswith(today)
            incomplete.append({
                'row_num': idx + 1,
                'email': email,
                'break_type': break_type,
                'start_time': start_time,
                'is_today': is_today
            })

if not incomplete:
    print("✓ Все записи завершены, очистка не требуется")
    sys.exit(0)

print(f"Найдено незавершённых записей: {len(incomplete)}")
print()

# Показываем записи
print("НЕЗАВЕРШЁННЫЕ ЗАПИСИ:")
print("-" * 80)
for item in incomplete:
    status = "СЕГОДНЯ" if item['is_today'] else "СТАРАЯ"
    print(f"[{status}] Строка {item['row_num']}: {item['email']} | {item['break_type']} | {item['start_time']}")
print("-" * 80)
print()

# Спрашиваем что делать
print("ВАРИАНТЫ ДЕЙСТВИЙ:")
print("1. Удалить ВСЕ незавершённые записи (рекомендуется)")
print("2. Завершить все записи (установить EndTime = StartTime + 15 минут)")
print("3. Удалить только СТАРЫЕ (не сегодняшние)")
print("4. Отмена")
print()

choice = input("Ваш выбор (1-4): ").strip()

if choice == "1":
    # Удаление всех
    print()
    print("Удаление всех незавершённых записей...")
    
    # Удаляем строки с конца (чтобы не сбивались номера)
    for item in sorted(incomplete, key=lambda x: x['row_num'], reverse=True):
        ws.delete_rows(item['row_num'])
        print(f"  ✓ Удалена строка {item['row_num']}")
    
    print()
    print(f"✓ Удалено записей: {len(incomplete)}")

elif choice == "2":
    # Завершение всех
    print()
    print("Завершение всех записей...")
    
    for item in incomplete:
        row_num = item['row_num']
        start = datetime.strptime(item['start_time'], "%Y-%m-%d %H:%M:%S")
        end = start  # Завершаем сразу (duration=0)
        
        # Обновляем EndTime
        end_col = chr(ord('A') + end_idx)
        ws.update(f"{end_col}{row_num}", [[end.strftime("%Y-%m-%d %H:%M:%S")]])
        
        # Обновляем ActualDuration
        duration_idx = header.index("ActualDuration")
        duration_col = chr(ord('A') + duration_idx)
        ws.update(f"{duration_col}{row_num}", [["0"]])
        
        print(f"  ✓ Завершена строка {row_num}")
    
    print()
    print(f"✓ Завершено записей: {len(incomplete)}")

elif choice == "3":
    # Удаление только старых
    old_records = [item for item in incomplete if not item['is_today']]
    
    if not old_records:
        print()
        print("Нет старых записей для удаления")
        sys.exit(0)
    
    print()
    print(f"Удаление {len(old_records)} старых записей...")
    
    for item in sorted(old_records, key=lambda x: x['row_num'], reverse=True):
        ws.delete_rows(item['row_num'])
        print(f"  ✓ Удалена строка {item['row_num']}")
    
    print()
    print(f"✓ Удалено записей: {len(old_records)}")
    print(f"Осталось сегодняшних: {len(incomplete) - len(old_records)}")

else:
    print()
    print("Отменено")
    sys.exit(0)

print()
print("=" * 80)
print("ОЧИСТКА ЗАВЕРШЕНА")
print("=" * 80)