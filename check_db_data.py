#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт для проверки данных в БД Supabase
"""
import os
from datetime import date
from dotenv import load_dotenv

load_dotenv()

from api_adapter import get_sheets_api

def check_database():
    """Проверяет наличие данных в таблицах"""
    api = get_sheets_api()

    print("=" * 80)
    print("ПРОВЕРКА БАЗЫ ДАННЫХ SUPABASE")
    print("=" * 80)

    # 1. Проверка break_schedules
    print("\n1. Таблица break_schedules:")
    print("-" * 80)
    try:
        response = api.client.table('break_schedules').select('*').execute()
        schedules = response.data
        print(f"   Всего записей: {len(schedules)}")
        for schedule in schedules:
            print(f"   - ID: {schedule.get('id')}")
            print(f"     Название: {schedule.get('name')}")
            print(f"     Смена: {schedule.get('shift_start')} - {schedule.get('shift_end')}")
            print(f"     Активен: {schedule.get('is_active')}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")

    # 2. Проверка break_limits
    print("\n2. Таблица break_limits:")
    print("-" * 80)
    try:
        response = api.client.table('break_limits').select('*').execute()
        limits = response.data
        print(f"   Всего записей: {len(limits)}")
        for limit in limits:
            print(f"   - Schedule ID: {limit.get('schedule_id')}")
            print(f"     Тип: {limit.get('break_type')}")
            print(f"     Длительность: {limit.get('duration_minutes')} мин")
            print(f"     Количество в день: {limit.get('daily_count')}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")

    # 3. Проверка break_windows
    print("\n3. Таблица break_windows:")
    print("-" * 80)
    try:
        response = api.client.table('break_windows').select('*').execute()
        windows = response.data
        print(f"   Всего записей: {len(windows)}")
        for window in windows:
            print(f"   - Schedule ID: {window.get('schedule_id')}")
            print(f"     Тип: {window.get('break_type')}")
            print(f"     Окно: {window.get('window_start')} - {window.get('window_end')}")
            print(f"     Приоритет: {window.get('priority')}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")

    # 4. Проверка break_log
    print("\n4. Таблица break_log:")
    print("-" * 80)
    try:
        response = api.client.table('break_log').select('*').execute()
        breaks = response.data
        print(f"   Всего записей: {len(breaks)}")

        # Активные перерывы (без end_time)
        today = date.today().isoformat()
        active = [b for b in breaks if not b.get('end_time') and b.get('date') == today]
        print(f"   Активных перерывов сегодня: {len(active)}")

        if active:
            print("\n   АКТИВНЫЕ ПЕРЕРЫВЫ:")
            for b in active:
                print(f"   - Email: {b.get('email')}")
                print(f"     Имя: {b.get('name')}")
                print(f"     Тип: {b.get('break_type')}")
                print(f"     Начало: {b.get('start_time')}")
                print(f"     Статус: {b.get('status')}")
                print()

        # Последние 5 записей
        print(f"\n   Последние 5 записей:")
        for b in breaks[-5:]:
            print(f"   - Email: {b.get('email')}, Тип: {b.get('break_type')}, Начало: {b.get('start_time')}, Конец: {b.get('end_time')}")

    except Exception as e:
        print(f"   ❌ Ошибка: {e}")

    # 5. Проверка user_break_assignments
    print("\n5. Таблица user_break_assignments:")
    print("-" * 80)
    try:
        response = api.client.table('user_break_assignments').select('*').execute()
        assignments = response.data
        print(f"   Всего записей: {len(assignments)}")
        for assignment in assignments:
            print(f"   - Email: {assignment.get('email')}")
            print(f"     Schedule ID: {assignment.get('schedule_id')}")
            print(f"     Назначен: {assignment.get('assigned_date')}")
            print(f"     Активен: {assignment.get('is_active')}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")

    # 6. Проверка work_sessions
    print("\n6. Таблица work_sessions:")
    print("-" * 80)
    try:
        response = api.client.table('work_sessions')\
            .select('*')\
            .eq('status', 'active')\
            .execute()
        sessions = response.data
        print(f"   Активных сессий: {len(sessions)}")
        for session in sessions:
            print(f"   - Email: {session.get('email')}")
            print(f"     Session ID: {session.get('session_id')}")
            print(f"     Логин: {session.get('login_time')}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")

    print("\n" + "=" * 80)
    print("ПРОВЕРКА ЗАВЕРШЕНА")
    print("=" * 80)

if __name__ == "__main__":
    check_database()
