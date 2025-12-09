#!/usr/bin/env python3
"""
Скрипт для тестирования kick механизма в реальном времени
"""
import os
import sys
from dotenv import load_dotenv
from datetime import datetime
import time

# Загружаем переменные окружения
load_dotenv()

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api_adapter import get_sheets_api

def test_kick_mechanism():
    """Тестируем kick механизм в реальном времени"""

    print("=" * 80)
    print("ТЕСТ: Kick механизм в реальном времени")
    print("=" * 80)

    try:
        api = get_sheets_api()
        print(f"✅ API инициализирован: {type(api).__name__}\n")

        # Получаем все активные сессии
        print("1. Получаем текущие активные сессии...")
        sessions = api.get_all_active_sessions()

        if not sessions:
            print("❌ Нет активных сессий")
            print("\nДля теста:")
            print("  1. Запустите: python user_app/main.py")
            print("  2. Войдите под пользователем")
            print("  3. Запустите этот скрипт снова")
            return False

        # Показываем только активные сессии
        active_sessions = [s for s in sessions if s.get('Status', '').lower() == 'active']

        if not active_sessions:
            print("❌ Нет активных сессий (только kicked/finished)")
            print("\nВсе сессии:")
            for i, s in enumerate(sessions, 1):
                print(f"  [{i}] {s.get('Email')} - {s.get('Status')} (LoginTime: {s.get('LoginTime')})")
            return False

        print(f"✅ Найдено активных сессий: {len(active_sessions)}\n")

        # Показываем активные сессии и предлагаем выбрать
        for i, session in enumerate(active_sessions, 1):
            email = session.get('Email', 'N/A')
            name = session.get('Name', 'N/A')
            session_id = session.get('SessionID', 'N/A')
            login_time = session.get('LoginTime', 'N/A')

            print(f"[{i}] {name} ({email})")
            print(f"    SessionID: {session_id[:40]}..." if len(session_id) > 40 else f"    SessionID: {session_id}")
            print(f"    LoginTime: {login_time}\n")

        # Выбираем первую активную сессию для теста
        target_session = active_sessions[0]
        email = target_session.get('Email')
        name = target_session.get('Name')
        session_id = target_session.get('SessionID')

        print("=" * 80)
        print(f"ЦЕЛЕВАЯ СЕССИЯ: {name} ({email})")
        print(f"SessionID: {session_id}")
        print("=" * 80)

        # Проверяем текущий статус
        print("\n2. Проверяем текущий статус через check_user_session_status...")
        current_status = api.check_user_session_status(email, session_id)
        print(f"   Статус: '{current_status}'")

        if current_status != 'active':
            print(f"   ⚠️  Сессия не active, пропускаем kick")
            return False

        # Kick сессии
        print("\n3. Выполняем kick сессии...")
        input("   Нажмите ENTER для kick сессии (или Ctrl+C для отмены)...")

        success = api.kick_active_session(
            email=email,
            session_id=session_id,
            status="kicked",
            remote_cmd="FORCE_LOGOUT"
        )

        if success:
            print(f"   ✅ Kick выполнен успешно!")
        else:
            print(f"   ❌ Kick не удался")
            return False

        # Проверяем статус после kick
        print("\n4. Проверяем статус после kick...")
        time.sleep(1)  # Даём время на обновление БД

        new_status = api.check_user_session_status(email, session_id)
        print(f"   Новый статус: '{new_status}'")

        if new_status == 'kicked':
            print(f"   ✅ Статус изменён на 'kicked'")
        else:
            print(f"   ❌ Статус не изменился: '{new_status}'")
            return False

        # Мониторинг - проверяем закроется ли user app
        print("\n5. Мониторинг (user app должен закрыться через ~30 секунд)...")
        print("   Таймер user app проверяет статус каждые 30 секунд")
        print("   Следите за приложением...\n")

        for i in range(6):  # 60 секунд
            time.sleep(10)

            # Проверяем статус снова
            check_status = api.check_user_session_status(email, session_id)
            print(f"   [{datetime.now().strftime('%H:%M:%S')}] Статус: '{check_status}' (прошло {(i+1)*10} сек)")

            # Проверяем есть ли ещё активная сессия
            sessions_check = api.get_all_active_sessions()
            active_for_email = [s for s in sessions_check
                              if s.get('Email', '').lower() == email.lower()
                              and s.get('Status', '').lower() == 'active']

            if not active_for_email:
                print(f"\n   ✅ Активных сессий для {email} больше нет!")
                print(f"   ✅ User app должен был закрыться!")
                return True

        print("\n   ⚠️  Прошло 60 секунд, но user app всё ещё работает")
        print("   Это может означать:")
        print("     1. Таймер в user app не запускается")
        print("     2. Метод _is_session_finished_remote() не работает")
        print("     3. User app не видит изменение статуса")

        return False

    except KeyboardInterrupt:
        print("\n\n❌ Тест прерван пользователем")
        return False
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_kick_mechanism()
    print("\n" + "=" * 80)
    if success:
        print("✅ ТЕСТ ПРОЙДЕН: Kick механизм работает корректно")
    else:
        print("❌ ТЕСТ НЕ ПРОЙДЕН: Проверьте логи user app")
    print("=" * 80)
    sys.exit(0 if success else 1)
