#!/usr/bin/env python3
"""
Тестовый скрипт для проверки статуса сессии после разлогинивания
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
print("ТЕСТ ПРОВЕРКИ СТАТУСА СЕССИИ ПОСЛЕ РАЗЛОГИНИВАНИЯ")
print("=" * 80)
print()

api = get_sheets_api()

# Тестовый email и session_id
test_email = input("Введите email: ").strip().lower()
test_session_id = input("Введите session_id: ").strip()

if not test_email or not test_session_id:
    print("Используются тестовые значения")
    test_email = "9@ya.ru"
    test_session_id = "9@ya.ru_20251211113720"

print()

# 1. Проверить статус через метод check_user_session_status
print("1. ПРОВЕРКА СТАТУСА ЧЕРЕЗ check_user_session_status")
print("-" * 80)
try:
    status = api.check_user_session_status(test_email, test_session_id)
    print(f"✅ Статус: {status}")
    print()
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
    print()

# 2. Прямой запрос к work_sessions
print("2. ПРЯМОЙ ЗАПРОС К work_sessions")
print("-" * 80)
try:
    if hasattr(api, 'client'):
        response = api.client.table('work_sessions')\
            .select('*')\
            .eq('email', test_email)\
            .eq('session_id', test_session_id)\
            .execute()
        
        if response.data:
            session = response.data[0]
            print(f"✅ Сессия найдена в work_sessions:")
            print(f"   Email: {session.get('email')}")
            print(f"   SessionID: {session.get('session_id')}")
            print(f"   Status: {session.get('status')}")
            print(f"   LoginTime: {session.get('login_time')}")
            print(f"   LogoutTime: {session.get('logout_time')}")
            print(f"   Все поля: {list(session.keys())}")
        else:
            print(f"⚠️  Сессия не найдена в work_sessions")
    else:
        print("⚠️  API не имеет атрибута 'client'")
    print()
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
    print()

# 3. Проверить все сессии пользователя
print("3. ВСЕ СЕССИИ ПОЛЬЗОВАТЕЛЯ")
print("-" * 80)
try:
    if hasattr(api, 'client'):
        response = api.client.table('work_sessions')\
            .select('*')\
            .eq('email', test_email)\
            .order('login_time', desc=True)\
            .limit(5)\
            .execute()
        
        print(f"Найдено сессий: {len(response.data)}")
        for i, s in enumerate(response.data, 1):
            print(f"\n  Сессия {i}:")
            print(f"    SessionID: {s.get('session_id')}")
            print(f"    Status: {s.get('status')}")
            print(f"    LoginTime: {s.get('login_time')}")
            print(f"    LogoutTime: {s.get('logout_time')}")
    print()
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
    print()

# 4. Тест разлогинивания
print("4. ТЕСТ РАЗЛОГИНИВАНИЯ")
print("-" * 80)
try:
    from datetime import datetime, timezone
    result = api.kick_active_session(
        email=test_email,
        session_id=test_session_id,
        logout_time=datetime.now(timezone.utc).isoformat()
    )
    
    if result:
        print("✅ Разлогинивание выполнено")
        
        # Проверить статус после разлогинивания
        import time
        time.sleep(1)  # Небольшая задержка
        
        status_after = api.check_user_session_status(test_email, test_session_id)
        print(f"✅ Статус после разлогинивания: {status_after}")
        
        if status_after == 'kicked':
            print("✅ Статус правильно установлен на 'kicked'")
        else:
            print(f"⚠️  Статус: {status_after} (ожидалось 'kicked')")
    else:
        print("❌ Разлогинивание не удалось")
    print()
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
    print()

print("=" * 80)
print("ТЕСТ ЗАВЕРШЕН")
print("=" * 80)
