#!/usr/bin/env python3
"""
Диагностика проблемы с kick - проверка статуса сессий
"""
import os
import sys
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api_adapter import get_sheets_api

def diagnose():
    """Полная диагностика"""

    print("=" * 80)
    print("ДИАГНОСТИКА: Проверка механизма kick")
    print("=" * 80)

    try:
        api = get_sheets_api()
        print(f"✅ API инициализирован: {type(api).__name__}")

        # Проверяем наличие методов
        print("\n1. Проверка методов API:")
        methods = [
            'get_all_active_sessions',
            'get_active_session',
            'check_user_session_status',
            'kick_active_session'
        ]
        for method in methods:
            exists = hasattr(api, method)
            print(f"   {'✅' if exists else '❌'} {method}")

        # Получаем все активные сессии
        print("\n2. Получаем все активные сессии...")
        if hasattr(api, 'get_all_active_sessions'):
            try:
                sessions = api.get_all_active_sessions()
                print(f"   Всего активных сессий: {len(sessions)}")

                if not sessions:
                    print("   ⚠️  Нет активных сессий")
                    print("\n   Для создания активной сессии:")
                    print("     1. Запустите: python user_app/main.py")
                    print("     2. Войдите под любым пользователем")
                    print("     3. Запустите диагностику снова")
                else:
                    print("\n   Активные сессии:")
                    for i, s in enumerate(sessions, 1):
                        email = s.get('Email', 'N/A')
                        name = s.get('Name', 'N/A')
                        session_id = s.get('SessionID', 'N/A')
                        status = s.get('Status', 'N/A')
                        login_time = s.get('LoginTime', 'N/A')

                        print(f"\n   [{i}] Email: {email}")
                        print(f"       Name: {name}")
                        print(f"       SessionID: {session_id[:20]}..." if len(session_id) > 20 else f"       SessionID: {session_id}")
                        print(f"       Status: {status}")
                        print(f"       LoginTime: {login_time}")

                        # Проверяем статус через check_user_session_status
                        if hasattr(api, 'check_user_session_status') and status != 'N/A':
                            try:
                                checked_status = api.check_user_session_status(email, session_id)
                                if checked_status != status:
                                    print(f"       ⚠️  check_user_session_status вернул: {checked_status}")
                                else:
                                    print(f"       ✅ check_user_session_status подтверждает: {checked_status}")
                            except Exception as e:
                                print(f"       ❌ Ошибка check_user_session_status: {e}")

            except Exception as e:
                print(f"   ❌ Ошибка get_all_active_sessions: {e}")
                import traceback
                traceback.print_exc()

        # Проверяем прямой доступ к Supabase
        print("\n3. Проверка прямого доступа к Supabase...")
        if hasattr(api, 'client'):
            try:
                print("   Пытаемся получить данные из work_sessions...")
                response = api.client.table('work_sessions')\
                    .select('email, session_id, status, login_time')\
                    .eq('status', 'active')\
                    .limit(5)\
                    .execute()

                print(f"   ✅ Получено записей: {len(response.data)}")

                if response.data:
                    for row in response.data:
                        print(f"      - {row.get('email')}: {row.get('status')} (session: {row.get('session_id')[:20]}...)")

            except Exception as e:
                print(f"   ❌ Ошибка прямого запроса: {e}")

                # Проверяем RLS
                print("\n   ⚠️  Возможная проблема: Row Level Security (RLS)")
                print("      RLS может блокировать запросы к Supabase")
                print("\n      Решение:")
                print("      1. Откройте Supabase Dashboard")
                print("      2. Перейдите в Authentication > Policies")
                print("      3. Для таблицы work_sessions создайте политику:")
                print("         - Включите 'Enable read access for all users'")
                print("      Или отключите RLS для таблицы work_sessions (для разработки)")

        print("\n" + "=" * 80)
        print("ДИАГНОСТИКА ЗАВЕРШЕНА")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    diagnose()
