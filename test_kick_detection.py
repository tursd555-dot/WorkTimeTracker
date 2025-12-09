#!/usr/bin/env python3
"""
Тест для проверки обнаружения kicked статуса
"""
import os
import sys
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api_adapter import get_sheets_api

def test_kick_detection():
    """Тестируем обнаружение kicked статуса"""

    # Используем email из последнего теста
    test_email = "9@ya.ru"

    print("=" * 80)
    print("ТЕСТ: Обнаружение принудительного завершения (kicked)")
    print("=" * 80)

    try:
        api = get_sheets_api()
        print(f"✅ API инициализирован: {type(api).__name__}")

        # Получаем активную сессию пользователя
        print(f"\n1. Проверяем активную сессию для {test_email}...")
        session = api.get_active_session(test_email)

        if not session:
            print(f"❌ Активной сессии нет для {test_email}")
            print("\nВозможные причины:")
            print("  - Пользователь не залогинен в user_app")
            print("  - Сессия уже была завершена")
            print("\nДля проверки запустите:")
            print("  1. python user_app/main.py")
            print("  2. Войдите под пользователем 9@ya.ru")
            print("  3. Запустите этот тест снова")
            return False

        print(f"✅ Активная сессия найдена:")
        print(f"   Email: {session.get('Email')}")
        print(f"   Name: {session.get('Name')}")
        print(f"   SessionID: {session.get('SessionID')}")
        print(f"   Status: {session.get('Status')}")
        print(f"   LoginTime: {session.get('LoginTime')}")

        session_id = session.get('SessionID')

        # Проверяем статус через check_user_session_status
        print(f"\n2. Проверяем статус через check_user_session_status...")
        if hasattr(api, 'check_user_session_status'):
            status = api.check_user_session_status(test_email, session_id)
            print(f"   Статус: '{status}'")

            if status in ("kicked", "finished"):
                print(f"✅ Статус '{status}' обнаружен - приложение должно закрыться!")
                return True
            elif status == "active":
                print(f"⚠️  Статус 'active' - сессия всё ещё активна")
                print("\nДля проверки kick:")
                print("  1. Откройте админ панель: python admin_app/main_admin.py")
                print("  2. Найдите активную сессию пользователя 9@ya.ru")
                print("  3. Нажмите 'Разлогинить'")
                print("  4. Запустите этот тест снова")
                return False
            else:
                print(f"❓ Неизвестный статус: '{status}'")
                return False
        else:
            print("❌ Метод check_user_session_status не найден в API")
            return False

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_kick_detection()
    sys.exit(0 if success else 1)
