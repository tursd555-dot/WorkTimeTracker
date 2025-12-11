#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работы с шаблонами перерывов в Supabase
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv()

from api_adapter import get_sheets_api

print("=" * 80)
print("ТЕСТ РАБОТЫ С ШАБЛОНАМИ ПЕРЕРЫВОВ")
print("=" * 80)
print()

api = get_sheets_api()

# 1. Проверка чтения таблицы
print("1. ПРОВЕРКА ЧТЕНИЯ ТАБЛИЦЫ break_schedules")
print("-" * 80)
try:
    ws = api.get_worksheet("BreakSchedules")
    if ws is None:
        print("❌ get_worksheet вернул None")
    else:
        print(f"✅ get_worksheet вернул объект с table_name={ws.table_name}")
        
        # Читаем данные
        rows = api._read_table(ws)
        print(f"✅ Прочитано строк: {len(rows)}")
        
        if rows:
            print("\nПервая строка:")
            for key, value in rows[0].items():
                print(f"  {key}: {value}")
        else:
            print("⚠️  Таблица пуста или данные не найдены")
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
print()

# 2. Проверка записи в таблицу
print("2. ПРОВЕРКА ЗАПИСИ В ТАБЛИЦУ break_schedules")
print("-" * 80)
try:
    test_values = [
        "TEST_001",
        "Тестовый шаблон",
        "09:00",
        "18:00",
        "Перерыв",
        "15",
        "10:00",
        "12:00",
        "1"
    ]
    
    ws = api.get_worksheet("BreakSchedules")
    if ws:
        result = ws.append_row(test_values)
        print(f"✅ append_row вернул: {result}")
        
        # Проверяем, что данные записались
        import time
        time.sleep(1)  # Небольшая задержка
        
        rows = api._read_table(ws)
        test_rows = [r for r in rows if r.get("ScheduleID") == "TEST_001"]
        if test_rows:
            print(f"✅ Тестовый шаблон найден в таблице: {len(test_rows)} строк(и)")
            for row in test_rows:
                print(f"  ScheduleID: {row.get('ScheduleID')}, Name: {row.get('Name')}")
        else:
            print("⚠️  Тестовый шаблон не найден в таблице после записи")
    else:
        print("❌ Не удалось получить worksheet")
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
print()

# 3. Прямой запрос к Supabase
print("3. ПРЯМОЙ ЗАПРОС К SUPABASE")
print("-" * 80)
try:
    if hasattr(api, 'client'):
        response = api.client.table('break_schedules').select('*').execute()
        print(f"✅ Прямой запрос: найдено {len(response.data)} строк")
        
        if response.data:
            print("\nПервая строка (сырые данные):")
            for key, value in response.data[0].items():
                print(f"  {key}: {value}")
    else:
        print("⚠️  API не имеет атрибута 'client'")
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
print()

print("=" * 80)
print("ТЕСТ ЗАВЕРШЕН")
print("=" * 80)
