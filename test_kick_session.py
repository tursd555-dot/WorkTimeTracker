#!/usr/bin/env python3
"""
Тестовый скрипт для проверки разлогинивания
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv()

from api_adapter import get_sheets_api
from datetime import datetime, timezone

print("=" * 80)
print("ТЕСТ РАЗЛОГИНИВАНИЯ")
print("=" * 80)
print()

api = get_sheets_api()

# Тестовый email (замените на реальный)
test_email = input("Введите email пользователя для теста: ").strip().lower()

if not test_email:
    test_email = "test@example.com"
    print(f"Используется тестовый email: {test_email}")

print()

# 1. Проверить активные сессии
print("1. ПРОВЕРКА АКТИВНЫХ СЕССИЙ")
print("-" * 80)
try:
    sessions = api.get_all_active_sessions()
    user_sessions = [s for s in sessions if s.get('Email', '').lower() == test_email]
    
    print(f"Всего активных сессий: {len(sessions)}")
    print(f"Сессий для {test_email}: {len(user_sessions)}")
    
    if user_sessions:
        print("\nАктивные сессии пользователя:")
        for s in user_sessions:
            print(f"  Email: {s.get('Email')}")
            print(f"  Status: {s.get('Status')}")
            print(f"  SessionID: {s.get('SessionID')}")
            print(f"  LoginTime: {s.get('LoginTime')}")
            print()
    else:
        print(f"⚠️  Активных сессий для {test_email} не найдено")
        print()
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
    print()

# 2. Проверить прямую сессию
print("2. ПРОВЕРКА ПРЯМОЙ СЕССИИ")
print("-" * 80)
try:
    session = api.get_active_session(test_email)
    if session:
        print(f"✅ Сессия найдена:")
        print(f"  Email: {session.get('Email')}")
        print(f"  Status: {session.get('Status')}")
        print(f"  SessionID: {session.get('SessionID')}")
        session_id = session.get('SessionID')
    else:
        print(f"⚠️  Сессия не найдена")
        session_id = None
    print()
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
    session_id = None
    print()

# 3. Тест разлогинивания
if session_id:
    print("3. ТЕСТ РАЗЛОГИНИВАНИЯ")
    print("-" * 80)
    try:
        print(f"Попытка разлогинить: email={test_email}, session_id={session_id}")
        result = api.kick_active_session(
            email=test_email,
            session_id=session_id,
            logout_time=datetime.now(timezone.utc).isoformat()
        )
        
        if result:
            print("✅ Разлогинивание успешно!")
        else:
            print("❌ Разлогинивание не удалось (сессия не найдена)")
        print()
    except Exception as e:
        print(f"❌ Ошибка при разлогинивании: {e}")
        import traceback
        traceback.print_exc()
        print()
    
    # Проверить статус после разлогинивания
    print("4. ПРОВЕРКА СТАТУСА ПОСЛЕ РАЗЛОГИНИВАНИЯ")
    print("-" * 80)
    try:
        status = api.check_user_session_status(test_email, session_id)
        print(f"Статус сессии: {status}")
        if status == 'kicked':
            print("✅ Сессия успешно помечена как 'kicked'")
        else:
            print(f"⚠️  Статус сессии: {status} (ожидалось 'kicked')")
    except Exception as e:
        print(f"❌ Ошибка проверки статуса: {e}")
        import traceback
        traceback.print_exc()
else:
    print("3. ТЕСТ РАЗЛОГИНИВАНИЯ - ПРОПУЩЕН (нет активной сессии)")
    print()

print("=" * 80)
print("ТЕСТ ЗАВЕРШЕН")
print("=" * 80)
