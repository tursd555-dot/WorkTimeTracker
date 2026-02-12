#!/usr/bin/env python3
"""
Тестовый скрипт для проверки логирования статусов

Проверяет:
1. Как записываются статусы в локальную БД
2. Как синхронизируются статусы в Supabase work_log
3. Корректность записи статусов для разных групп
"""
import sys
import os
from datetime import datetime, timedelta, date

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api_adapter import get_sheets_api
from admin_app.repo import AdminRepo

def test_status_logging():
    """Тестирует логирование статусов"""
    print("=" * 80)
    print("ТЕСТ: Проверка логирования статусов")
    print("=" * 80)
    print()
    
    try:
        # Инициализация API
        print("1. Инициализация API...")
        api = get_sheets_api()
        print(f"   ✅ API тип: {type(api).__name__}")
        print()
        
        # Инициализация репозитория
        print("2. Инициализация репозитория...")
        repo = AdminRepo(api)
        print()
        
        # Проверка метода log_action в API
        print("3. Проверка метода log_action в API...")
        try:
            if hasattr(api, 'log_action'):
                print(f"   ✅ Метод log_action доступен")
                print(f"   📋 Сигнатура: {api.log_action.__doc__ or 'Нет документации'}")
            else:
                print(f"   ⚠️  Метод log_action не найден в API")
        except Exception as e:
            print(f"   ❌ Ошибка при проверке метода: {e}")
        print()
        
        # Тест записи статуса
        print("4. Тест записи статуса...")
        try:
            test_email = "test_status@example.com"
            test_name = "Тест Статус"
            test_status = "В работе"
            
            print(f"   Создаём тестовую запись:")
            print(f"      Email: {test_email}")
            print(f"      Name: {test_name}")
            print(f"      Status: {test_status}")
            print(f"      Action Type: STATUS_CHANGE")
            
            if hasattr(api, 'log_action'):
                api.log_action(
                    email=test_email,
                    name=test_name,
                    action_type="STATUS_CHANGE",
                    status=test_status,
                    details=f"Тест записи статуса из скрипта",
                    session_id="test_session_status"
                )
                print(f"   ✅ Статус записан")
                
                # Проверяем, что он появился
                import time
                time.sleep(1)
                
                work_log_data = repo.get_work_log_data(
                    email=test_email,
                    date_from=date.today().isoformat(),
                    date_to=date.today().isoformat()
                )
                
                if work_log_data:
                    print(f"   ✅ Запись найдена в work_log: {len(work_log_data)} записей")
                    for entry in work_log_data:
                        print(f"      Status: {entry.get('status')}, Timestamp: {entry.get('timestamp')}")
                else:
                    print(f"   ⚠️  Запись не найдена в work_log (возможно, требуется синхронизация)")
            else:
                print(f"   ⚠️  Метод log_action недоступен, пропускаем тест")
        except Exception as e:
            print(f"   ❌ Ошибка при записи статуса: {e}")
            import traceback
            traceback.print_exc()
        print()
        
        # Проверка записей для реальных пользователей
        print("5. Проверка записей для реальных пользователей целевых групп...")
        try:
            users = repo.list_users()
            target_groups = ["Входящие", "Почта", "Запись", "Стоматология"]
            
            date_from = (date.today() - timedelta(days=7)).isoformat()
            date_to = date.today().isoformat()
            
            for group in target_groups:
                print(f"\n   📊 Группа: {group}")
                group_users = [u for u in users if u.get('Group', '') == group]
                
                if not group_users:
                    print(f"      ⚠️  Нет пользователей в группе")
                    continue
                
                print(f"      Сотрудников: {len(group_users)}")
                
                for user in group_users:
                    email = user.get('Email', '').lower()
                    name = user.get('Name', '')
                    
                    if not email:
                        continue
                    
                    # Проверяем записи для этого пользователя
                    user_work_log = repo.get_work_log_data(
                        email=email,
                        date_from=date_from,
                        date_to=date_to
                    )
                    
                    if user_work_log:
                        # Анализируем статусы
                        statuses = {}
                        statuses_with_value = 0
                        statuses_none = 0
                        
                        for entry in user_work_log:
                            status = entry.get('status') or entry.get('Status')
                            if status:
                                statuses[status] = statuses.get(status, 0) + 1
                                statuses_with_value += 1
                            else:
                                statuses_none += 1
                        
                        print(f"      ✅ {name} ({email}):")
                        print(f"         Записей: {len(user_work_log)}")
                        print(f"         Со статусом: {statuses_with_value}")
                        print(f"         Без статуса: {statuses_none}")
                        if statuses:
                            print(f"         Статусы: {dict(statuses)}")
                    else:
                        print(f"      ⚠️  {name} ({email}): нет записей в work_log")
        except Exception as e:
            print(f"   ❌ Ошибка при проверке: {e}")
            import traceback
            traceback.print_exc()
        print()
        
        # Проверка структуры записей work_log
        print("6. Анализ структуры записей work_log...")
        try:
            work_log_data = repo.get_work_log_data(
                date_from=(date.today() - timedelta(days=1)).isoformat(),
                date_to=date.today().isoformat()
            )
            
            if work_log_data:
                # Анализируем action_type
                action_types = defaultdict(int)
                action_types_with_status = defaultdict(int)
                action_types_without_status = defaultdict(int)
                
                for entry in work_log_data:
                    action_type = entry.get('action_type', '') or entry.get('ActionType', '')
                    status = entry.get('status') or entry.get('Status')
                    
                    if action_type:
                        action_types[action_type] += 1
                        if status:
                            action_types_with_status[action_type] += 1
                        else:
                            action_types_without_status[action_type] += 1
                
                print(f"   📋 Action types в work_log:")
                for action_type, count in sorted(action_types.items(), key=lambda x: x[1], reverse=True):
                    with_status = action_types_with_status.get(action_type, 0)
                    without_status = action_types_without_status.get(action_type, 0)
                    print(f"      {action_type}: {count} записей (со статусом: {with_status}, без статуса: {without_status})")
                
                # Проверяем, какие action_type должны иметь статус
                status_required_types = ['STATUS_CHANGE', 'LOGIN']
                print(f"\n   📋 Проверка action_type, которые должны иметь статус:")
                for action_type in status_required_types:
                    total = action_types.get(action_type, 0)
                    with_status = action_types_with_status.get(action_type, 0)
                    without_status = action_types_without_status.get(action_type, 0)
                    
                    if total > 0:
                        if without_status > 0:
                            print(f"      ⚠️  {action_type}: {without_status}/{total} записей без статуса")
                        else:
                            print(f"      ✅ {action_type}: все записи имеют статус")
                    else:
                        print(f"      ℹ️  {action_type}: нет записей")
            else:
                print(f"   ⚠️  Нет данных за последний день")
        except Exception as e:
            print(f"   ❌ Ошибка при анализе: {e}")
            import traceback
            traceback.print_exc()
        print()
        
        print("=" * 80)
        print("ТЕСТ ЗАВЕРШЕН")
        print("=" * 80)
        
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    from collections import defaultdict
    success = test_status_logging()
    sys.exit(0 if success else 1)
