#!/usr/bin/env python3
"""Комплексная диагностика системы перерывов"""
import os
import sys
from datetime import datetime, date, timezone
from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

load_dotenv()

from supabase import create_client
from api_adapter import get_sheets_api
from admin_app.break_manager import BreakManager

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
client = create_client(url, key)

print("="*80)
print("КОМПЛЕКСНАЯ ДИАГНОСТИКА СИСТЕМЫ ПЕРЕРЫВОВ")
print("="*80)

# 1. Проверяем активные перерывы в БД
print("\n" + "="*80)
print("1. АКТИВНЫЕ ПЕРЕРЫВЫ В SUPABASE")
print("="*80)

today = date.today().isoformat()
response = client.table('break_log')\
    .select('*')\
    .is_('end_time', 'null')\
    .gte('start_time', f'{today}T00:00:00')\
    .order('start_time', desc=True)\
    .execute()

print(f"\nНайдено активных перерывов: {len(response.data)}")
for i, row in enumerate(response.data, 1):
    print(f"\n{i}. ID: {row['id']}")
    print(f"   Email: {row['email']}")
    print(f"   Тип: {row['break_type']}")
    print(f"   Начало: {row['start_time']}")
    print(f"   Статус: {row['status']}")
    print(f"   Session: {row.get('session_id', 'N/A')}")

# 2. Тестируем BreakManager.end_all_active_breaks()
print("\n" + "="*80)
print("2. ТЕСТ: BreakManager.end_all_active_breaks()")
print("="*80)

if response.data:
    test_email = response.data[0]['email']
    print(f"\nТестируем для email: {test_email}")
    print("Инициализируем BreakManager...")

    try:
        sheets_api = get_sheets_api()
        break_mgr = BreakManager(sheets_api)
        print("✅ BreakManager инициализирован")

        print(f"\nВызываем end_all_active_breaks('{test_email}')...")
        result = break_mgr.end_all_active_breaks(test_email)
        print(f"Результат: {result}")

        # Проверяем что изменилось
        response_after = client.table('break_log')\
            .select('*')\
            .is_('end_time', 'null')\
            .gte('start_time', f'{today}T00:00:00')\
            .eq('email', test_email)\
            .execute()

        print(f"\nАктивных перерывов после вызова: {len(response_after.data)}")

        if len(response_after.data) == 0:
            print("✅ Все перерывы завершены!")
        else:
            print("❌ Перерывы НЕ завершены!")
            for row in response_after.data:
                print(f"  - {row['break_type']} | {row['start_time']}")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

else:
    print("\nНет активных перерывов для теста")

# 3. Проверяем break_status_integration
print("\n" + "="*80)
print("3. ТЕСТ: break_status_integration")
print("="*80)

try:
    from shared.break_status_integration import get_integration

    integration = get_integration()
    if integration:
        print("✅ Integration инициализирован")
        print(f"   break_mgr: {integration.break_mgr}")
        print(f"   active_breaks: {integration.active_breaks}")

        # Проверяем есть ли активные перерывы
        if response.data:
            test_email = response.data[0]['email']
            print(f"\nТестируем _end_all_breaks('{test_email}')...")

            # Вызываем напрямую
            result = integration._end_all_breaks(test_email)
            print(f"Результат: {result}")

            # Проверяем
            response_check = client.table('break_log')\
                .select('*')\
                .is_('end_time', 'null')\
                .gte('start_time', f'{today}T00:00:00')\
                .eq('email', test_email)\
                .execute()

            print(f"Активных перерывов после: {len(response_check.data)}")

    else:
        print("❌ Integration НЕ инициализирован (None)")

except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()

# 4. Проверяем get_all_active_breaks()
print("\n" + "="*80)
print("4. ТЕСТ: BreakManager.get_all_active_breaks()")
print("="*80)

try:
    sheets_api = get_sheets_api()
    break_mgr = BreakManager(sheets_api)

    active = break_mgr.get_all_active_breaks()
    print(f"\nМетод вернул: {len(active)} активных перерывов")

    for i, br in enumerate(active, 1):
        print(f"\n{i}. Email: {br['Email']}")
        print(f"   Тип: {br['BreakType']}")
        print(f"   Начало: {br['StartTime']}")
        print(f"   Длительность: {br['Duration']} мин")
        print(f"   Нарушение: {br['is_over_limit']}")

except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()

# 5. Финальная проверка
print("\n" + "="*80)
print("5. ФИНАЛЬНАЯ ПРОВЕРКА АКТИВНЫХ ПЕРЕРЫВОВ")
print("="*80)

response_final = client.table('break_log')\
    .select('*')\
    .is_('end_time', 'null')\
    .gte('start_time', f'{today}T00:00:00')\
    .order('start_time', desc=True)\
    .execute()

print(f"\nАктивных перерывов в БД: {len(response_final.data)}")
if response_final.data:
    print("\n❌ ПРОБЛЕМА: Остались незавершенные перерывы!")
    for row in response_final.data:
        print(f"  - {row['email']} | {row['break_type']} | {row['start_time']}")
else:
    print("\n✅ Все перерывы завершены!")

print("="*80)
