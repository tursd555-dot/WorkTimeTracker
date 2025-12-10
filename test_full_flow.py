#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Полный тест записи данных в Supabase
"""
import os
from datetime import datetime, date
from dotenv import load_dotenv

load_dotenv()

from api_adapter import get_sheets_api

def test_full_flow():
    """Тестирует полный флоу: логин -> перерыв -> проверка"""
    api = get_sheets_api()

    print("=" * 80)
    print("ТЕСТ ПОЛНОГО ФЛОУ ЗАПИСИ ДАННЫХ")
    print("=" * 80)

    # Тестовые данные
    test_email = "9@ya.ru"
    test_name = "Кот в Пальто"
    test_session_id = "TEST_SESSION_001"

    # 1. Тест: Создание активной сессии (логин)
    print("\n1. ТЕСТ: Создание активной сессии (логин)")
    print("-" * 80)
    try:
        result = api.set_active_session(
            email=test_email,
            name=test_name,
            session_id=test_session_id,
            login_time=datetime.now().isoformat()
        )
        print(f"   Результат: {result}")

        # Проверяем
        response = api.client.table('work_sessions')\
            .select('*')\
            .eq('session_id', test_session_id)\
            .execute()

        if response.data:
            print(f"   ✅ Сессия создана: {response.data[0]}")
        else:
            print(f"   ❌ Сессия НЕ создана!")

    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

    # 2. Тест: Начало перерыва (прямая запись в break_log)
    print("\n2. ТЕСТ: Начало перерыва (прямая запись)")
    print("-" * 80)
    try:
        # Получаем user_id
        user_response = api.client.table('users')\
            .select('id, name')\
            .eq('email', test_email)\
            .execute()

        if not user_response.data:
            print(f"   ❌ Пользователь {test_email} не найден в БД!")
            print(f"   Создаем пользователя...")

            # Создаем пользователя
            user_data = {
                'email': test_email,
                'name': test_name,
                'is_active': True
            }
            create_response = api.client.table('users').insert(user_data).execute()
            user_id = create_response.data[0]['id']
            print(f"   ✅ Пользователь создан: {user_id}")
        else:
            user_id = user_response.data[0]['id']
            actual_name = user_response.data[0]['name']
            print(f"   ✅ Пользователь найден: {user_id}, Имя: {actual_name}")

        # Записываем перерыв
        break_data = {
            'user_id': user_id,
            'email': test_email,
            'name': test_name,
            'break_type': 'Перерыв',
            'start_time': datetime.now().isoformat(),
            'date': date.today().isoformat(),
            'status': 'Active',
            'session_id': test_session_id
        }

        break_response = api.client.table('break_log').insert(break_data).execute()

        if break_response.data:
            break_id = break_response.data[0]['id']
            print(f"   ✅ Перерыв записан: {break_id}")
            print(f"   Данные: {break_response.data[0]}")
        else:
            print(f"   ❌ Перерыв НЕ записан!")

    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

    # 3. Тест: Проверка active_breaks view
    print("\n3. ТЕСТ: Проверка active_breaks view")
    print("-" * 80)
    try:
        response = api.client.table('active_breaks').select('*').execute()

        print(f"   Всего активных перерывов: {len(response.data)}")

        if response.data:
            for brk in response.data:
                print(f"   - Email: {brk.get('email')}")
                print(f"     Тип: {brk.get('break_type')}")
                print(f"     Начало: {brk.get('start_time')}")
                print(f"     Длительность: {brk.get('duration_minutes')} мин")
        else:
            print(f"   ❌ Нет активных перерывов в view!")

    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

    # 4. Тест: Чтение через BreakManager
    print("\n4. ТЕСТ: Чтение через BreakManager")
    print("-" * 80)
    try:
        from admin_app.break_manager import BreakManager

        break_mgr = BreakManager(api)
        active_breaks = break_mgr.get_all_active_breaks()

        print(f"   Активных перерывов через BreakManager: {len(active_breaks)}")

        if active_breaks:
            for brk in active_breaks:
                print(f"   - Email: {brk.get('Email')}")
                print(f"     Имя: {brk.get('Name')}")
                print(f"     Тип: {brk.get('BreakType')}")
                print(f"     Начало: {brk.get('StartTime')}")
        else:
            print(f"   ❌ BreakManager не видит активные перерывы!")

    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

    # 5. Тест: Назначение графика
    print("\n5. ТЕСТ: Назначение графика пользователю")
    print("-" * 80)
    try:
        # Получаем активные графики
        schedules = api.client.table('break_schedules')\
            .select('*')\
            .eq('is_active', True)\
            .execute()

        if not schedules.data:
            print(f"   ❌ Нет активных графиков!")
        else:
            schedule_id = schedules.data[0]['id']
            schedule_name = schedules.data[0]['name']
            print(f"   График для назначения: {schedule_name} ({schedule_id})")

            # Удаляем старые назначения
            api.client.table('user_break_assignments')\
                .delete()\
                .eq('email', test_email)\
                .execute()

            # Назначаем график
            assignment_data = {
                'user_id': user_id,
                'email': test_email,
                'schedule_id': schedule_id,
                'is_active': True,
                'assigned_by': 'test_script'
            }

            assign_response = api.client.table('user_break_assignments')\
                .insert(assignment_data)\
                .execute()

            if assign_response.data:
                print(f"   ✅ График назначен: {assign_response.data[0]}")
            else:
                print(f"   ❌ График НЕ назначен!")

    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

    # 6. Финальная проверка
    print("\n6. ФИНАЛЬНАЯ ПРОВЕРКА")
    print("-" * 80)
    print(f"   work_sessions: ", end="")
    sessions = api.client.table('work_sessions').select('*').eq('status', 'active').execute()
    print(f"{len(sessions.data)} активных")

    print(f"   break_log: ", end="")
    breaks = api.client.table('break_log').select('*').eq('status', 'Active').execute()
    print(f"{len(breaks.data)} активных")

    print(f"   user_break_assignments: ", end="")
    assignments = api.client.table('user_break_assignments')\
        .select('*')\
        .eq('email', test_email)\
        .eq('is_active', True)\
        .execute()
    print(f"{len(assignments.data)} назначений")

    print("\n" + "=" * 80)
    print("ТЕСТ ЗАВЕРШЕН")
    print("=" * 80)

    # Итоги
    print("\n📊 ИТОГИ:")
    if len(sessions.data) > 0:
        print("   ✅ Логин работает")
    else:
        print("   ❌ Логин НЕ работает")

    if len(breaks.data) > 0:
        print("   ✅ Перерывы записываются")
    else:
        print("   ❌ Перерывы НЕ записываются")

    if len(assignments.data) > 0:
        print("   ✅ Графики назначаются")
    else:
        print("   ❌ Графики НЕ назначаются")

if __name__ == "__main__":
    test_full_flow()
