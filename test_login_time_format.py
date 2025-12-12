#!/usr/bin/env python3
"""
Тестовый скрипт для проверки формата login_time из Supabase
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from api_adapter import SheetsAPI

print("=" * 80)
print("ТЕСТ ФОРМАТА LOGIN_TIME ИЗ SUPABASE")
print("=" * 80)

api = SheetsAPI()

# Получаем активные сессии
sessions = api.get_all_active_sessions()

if not sessions:
    print("\n❌ Нет активных сессий")
    sys.exit(0)

print(f"\n✅ Найдено {len(sessions)} активных сессий\n")

for i, session in enumerate(sessions, 1):
    email = session.get('Email', 'N/A')
    login_time = session.get('LoginTime', 'N/A')

    print(f"Сессия {i}:")
    print(f"  Email: {email}")
    print(f"  LoginTime RAW: {login_time!r}")
    print(f"  LoginTime TYPE: {type(login_time)}")

    # Проверяем, что это строка
    if isinstance(login_time, str):
        print(f"  Содержит 'Z': {'Z' in login_time}")
        print(f"  Содержит '+': {'+' in login_time}")
        print(f"  Содержит 'T': {'T' in login_time}")

        # Пробуем распарсить
        from datetime import datetime
        try:
            dt = datetime.fromisoformat(login_time.replace('Z', '+00:00'))
            print(f"  Parsed datetime: {dt}")
            print(f"  Parsed timezone: {dt.tzinfo}")
        except Exception as e:
            print(f"  ❌ Failed to parse: {e}")
    else:
        print(f"  ⚠️ LoginTime is not a string!")

    print()

# Также проверим, что возвращает прямой запрос к Supabase
if hasattr(api, 'client'):
    print("\n" + "=" * 80)
    print("ПРЯМОЙ ЗАПРОС К SUPABASE")
    print("=" * 80)

    try:
        response = api.client.table('active_sessions').select('*').limit(1).execute()
        if response.data:
            raw_session = response.data[0]
            print(f"\nПервая сессия (RAW из Supabase):")
            print(f"  login_time: {raw_session.get('login_time')!r}")
            print(f"  type: {type(raw_session.get('login_time'))}")
    except Exception as e:
        print(f"❌ Ошибка прямого запроса: {e}")

print("\n" + "=" * 80)
