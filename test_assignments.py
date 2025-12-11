#!/usr/bin/env python3
"""
Тестовый скрипт для проверки структуры таблицы назначений шаблонов перерывов
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
print("ТЕСТ СТРУКТУРЫ ТАБЛИЦЫ НАЗНАЧЕНИЙ")
print("=" * 80)
print()

api = get_sheets_api()

# Проверяем структуру таблицы назначений
print("1. ПРОВЕРКА СТРУКТУРЫ ТАБЛИЦЫ user_break_assignments")
print("-" * 80)
try:
    if hasattr(api, 'client'):
        # Пробуем разные варианты названий таблиц
        for table_name in ['user_break_assignments', 'break_assignments', 'user_break_schedules']:
            try:
                response = api.client.table(table_name).select('*').limit(5).execute()
                print(f"\n✅ Таблица {table_name} найдена: {len(response.data)} записей")
                
                if response.data:
                    print(f"\nКлючи первой записи:")
                    for key, value in response.data[0].items():
                        print(f"  {key}: {value}")
                    
                    print(f"\nВсе записи:")
                    for i, record in enumerate(response.data, 1):
                        print(f"\n  Запись {i}:")
                        for key, value in record.items():
                            print(f"    {key}: {value}")
                else:
                    print(f"  Таблица пуста")
                
                # Пробуем создать тестовую запись
                print(f"\n2. ТЕСТ СОЗДАНИЯ НАЗНАЧЕНИЯ")
                print("-" * 80)
                test_data_variants = [
                    {
                        'email': 'test@example.com',
                        'schedule_id': 'TEST_SCHEDULE',
                        'effective_date': '2025-12-11',
                        'assigned_by': 'admin'
                    },
                    {
                        'user_email': 'test@example.com',
                        'break_schedule_id': 'TEST_SCHEDULE',
                        'effective_date': '2025-12-11',
                        'assigned_by': 'admin'
                    },
                    {
                        'email': 'test@example.com',
                        'schedule_name': 'TEST_SCHEDULE',
                        'effective_date': '2025-12-11',
                        'assigned_by': 'admin'
                    }
                ]
                
                for i, test_data in enumerate(test_data_variants, 1):
                    try:
                        print(f"\nПопытка {i}: {test_data}")
                        response = api.client.table(table_name).insert(test_data).execute()
                        print(f"✅ Успешно создано назначение!")
                        # Удаляем тестовую запись
                        if response.data and 'id' in response.data[0]:
                            api.client.table(table_name).delete().eq('id', response.data[0]['id']).execute()
                            print(f"✅ Тестовая запись удалена")
                        break
                    except Exception as e:
                        print(f"❌ Ошибка: {e}")
                        continue
                        
            except Exception as e:
                print(f"❌ Таблица {table_name} не найдена или ошибка: {e}")
    else:
        print("⚠️  API не имеет атрибута 'client'")
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
print()

# Проверяем через get_worksheet
print("2. ПРОВЕРКА ЧЕРЕЗ get_worksheet")
print("-" * 80)
try:
    ws = api.get_worksheet("UserBreakAssignments")
    if ws:
        print(f"✅ get_worksheet вернул объект с table_name={ws.table_name}")
        rows = api._read_table(ws)
        print(f"✅ Прочитано строк: {len(rows)}")
        
        if rows:
            print(f"\nПервая строка (преобразованные ключи):")
            for key, value in rows[0].items():
                print(f"  {key}: {value}")
    else:
        print("❌ get_worksheet вернул None")
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
print()

print("=" * 80)
print("ТЕСТ ЗАВЕРШЕН")
print("=" * 80)
