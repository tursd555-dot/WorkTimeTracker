#!/usr/bin/env python3
"""
Тестовый скрипт для проверки фильтрации по дате и корректности расчетов в отчетах
"""
import sys
import os
from datetime import datetime, timedelta, date
from collections import defaultdict

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from api_adapter import get_sheets_api
    from admin_app.repo import AdminRepo
    from admin_app.break_manager import BreakManager
    import logging
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    
    print("=" * 80)
    print("ТЕСТ: Проверка фильтрации по дате и расчетов в отчетах")
    print("=" * 80)
    
    # Инициализация
    print("\n1. Инициализация API и репозитория...")
    api = get_sheets_api()
    repo = AdminRepo(api)
    break_mgr = BreakManager(repo)
    
    print("✅ Инициализация завершена")
    
    # Тестируем конкретную дату
    test_date = date(2025, 12, 12)  # 12.12.2025
    date_str = test_date.isoformat()
    
    print(f"\n2. Проверка данных за дату: {date_str}")
    print("-" * 80)
    
    # Проверяем, что возвращает get_work_log_data
    print(f"\n2.1. Вызов get_work_log_data(date_from='{date_str}', date_to='{date_str}')...")
    work_log_data = repo.get_work_log_data(
        date_from=date_str,
        date_to=date_str
    )
    
    print(f"✅ Получено записей: {len(work_log_data)}")
    
    if work_log_data:
        print(f"\n2.2. Примеры записей (первые 5):")
        for i, entry in enumerate(work_log_data[:5], 1):
            timestamp = entry.get('timestamp', 'N/A')
            email = entry.get('email', 'N/A')
            status = entry.get('status', 'N/A')
            action_type = entry.get('action_type', 'N/A')
            print(f"   {i}. {timestamp[:19]} | {email} | {action_type} | {status}")
        
        # Проверяем распределение по датам
        print(f"\n2.3. Анализ дат в записях:")
        dates_in_data = defaultdict(int)
        for entry in work_log_data:
            timestamp_str = entry.get('timestamp', '')
            if timestamp_str:
                try:
                    if 'T' in timestamp_str:
                        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    else:
                        dt = datetime.strptime(timestamp_str[:19], '%Y-%m-%d %H:%M:%S')
                    entry_date = dt.date()
                    dates_in_data[entry_date.isoformat()] += 1
                except Exception as e:
                    print(f"   ⚠️ Ошибка парсинга даты '{timestamp_str}': {e}")
        
        print(f"   Найдено записей по датам:")
        for d, count in sorted(dates_in_data.items()):
            print(f"     {d}: {count} записей")
        
        # Проверяем распределение по сотрудникам
        print(f"\n2.4. Распределение по сотрудникам:")
        emails_in_data = defaultdict(int)
        for entry in work_log_data:
            email = entry.get('email', '').lower()
            if email:
                emails_in_data[email] += 1
        
        print(f"   Найдено сотрудников: {len(emails_in_data)}")
        for email, count in sorted(emails_in_data.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"     {email}: {count} записей")
        
        # Проверяем наличие статусов
        print(f"\n2.5. Распределение по статусам:")
        statuses_in_data = defaultdict(int)
        for entry in work_log_data:
            status = entry.get('status', '')
            if status:
                statuses_in_data[status] += 1
        
        print(f"   Найдено статусов: {len(statuses_in_data)}")
        for status, count in sorted(statuses_in_data.items(), key=lambda x: x[1], reverse=True):
            print(f"     {status}: {count} записей")
        
        # Проверяем наличие LOGIN/LOGOUT
        print(f"\n2.6. Распределение по action_type:")
        action_types_in_data = defaultdict(int)
        for entry in work_log_data:
            action_type = entry.get('action_type', '')
            if action_type:
                action_types_in_data[action_type] += 1
        
        print(f"   Найдено типов действий: {len(action_types_in_data)}")
        for action_type, count in sorted(action_types_in_data.items(), key=lambda x: x[1], reverse=True):
            print(f"     {action_type}: {count} записей")
    else:
        print("   ⚠️ Данных не найдено!")
    
    # Проверяем расширенный диапазон дат
    print(f"\n3. Проверка расширенного диапазона дат (11.12 - 13.12)...")
    date_from_extended = date(2025, 12, 11).isoformat()
    date_to_extended = date(2025, 12, 13).isoformat()
    
    work_log_extended = repo.get_work_log_data(
        date_from=date_from_extended,
        date_to=date_to_extended
    )
    
    print(f"✅ Получено записей за период: {len(work_log_extended)}")
    
    if work_log_extended:
        # Анализируем даты в расширенном наборе
        dates_extended = defaultdict(int)
        for entry in work_log_extended:
            timestamp_str = entry.get('timestamp', '')
            if timestamp_str:
                try:
                    if 'T' in timestamp_str:
                        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    else:
                        dt = datetime.strptime(timestamp_str[:19], '%Y-%m-%d %H:%M:%S')
                    entry_date = dt.date()
                    dates_extended[entry_date.isoformat()] += 1
                except:
                    pass
        
        print(f"   Распределение по датам в расширенном периоде:")
        for d, count in sorted(dates_extended.items()):
            marker = " <-- ТЕСТОВАЯ ДАТА" if d == date_str else ""
            print(f"     {d}: {count} записей{marker}")
    
    # Проверяем конкретного сотрудника
    print(f"\n4. Проверка данных для конкретного сотрудника...")
    if work_log_data:
        # Берем первого сотрудника с данными
        test_email = None
        for entry in work_log_data:
            email = entry.get('email', '').lower()
            if email:
                test_email = email
                break
        
        if test_email:
            print(f"   Тестируем сотрудника: {test_email}")
            
            # Получаем данные только для этого сотрудника
            user_data = repo.get_work_log_data(
                date_from=date_str,
                date_to=date_str,
                email=test_email
            )
            
            print(f"   ✅ Получено записей для сотрудника: {len(user_data)}")
            
            if user_data:
                print(f"   Примеры записей сотрудника:")
                for i, entry in enumerate(user_data[:10], 1):
                    timestamp = entry.get('timestamp', 'N/A')
                    status = entry.get('status', 'N/A')
                    action_type = entry.get('action_type', 'N/A')
                    print(f"     {i}. {timestamp[:19]} | {action_type} | {status}")
                
                # Проверяем расчет времени
                print(f"\n   Проверка расчета времени...")
                from admin_app.reports_tab import ReportsTab
                
                # Создаем временный объект для доступа к методу
                class TempTab:
                    def _calculate_time_from_logs(self, logs):
                        from typing import Dict, List
                        from collections import defaultdict
                        
                        result = {
                            'total_seconds': 0,
                            'productive_seconds': 0,
                            'statuses': defaultdict(int),
                            'sessions': set()
                        }
                        
                        filtered_logs = []
                        for log_entry in logs:
                            status = log_entry.get('status', '')
                            action_type = log_entry.get('action_type', '')
                            if status or action_type in ['STATUS_CHANGE', 'LOGIN']:
                                filtered_logs.append(log_entry)
                        
                        if not filtered_logs:
                            return result
                        
                        sorted_logs = sorted(filtered_logs, key=lambda x: x.get('timestamp', ''))
                        
                        productive_statuses = {
                            'В работе', 'На задаче', 'Чат', 'Запись', 
                            'Стоматология', 'Входящие', 'Почта'
                        }
                        
                        for i, log_entry in enumerate(sorted_logs):
                            timestamp_str = log_entry.get('timestamp', '')
                            status = log_entry.get('status', '')
                            session_id = log_entry.get('session_id', '')
                            
                            if session_id:
                                result['sessions'].add(session_id)
                            
                            if not timestamp_str or not status:
                                continue
                            
                            try:
                                clean_timestamp = timestamp_str.replace('Z', '+00:00')
                                if 'T' in clean_timestamp:
                                    if '+' not in clean_timestamp and '-' in clean_timestamp[-6:]:
                                        clean_timestamp = clean_timestamp + '+00:00'
                                    dt = datetime.fromisoformat(clean_timestamp)
                                else:
                                    dt = datetime.strptime(clean_timestamp[:19], '%Y-%m-%d %H:%M:%S')
                            except Exception as e:
                                logger.warning(f"Failed to parse timestamp '{timestamp_str}': {e}")
                                continue
                            
                            if i < len(sorted_logs) - 1:
                                next_timestamp_str = sorted_logs[i + 1].get('timestamp', '')
                                next_session_id = sorted_logs[i + 1].get('session_id', '')
                                
                                if (next_session_id and session_id and 
                                    next_session_id != session_id and 
                                    next_session_id.strip() and session_id.strip()):
                                    duration = 60
                                elif next_timestamp_str:
                                    try:
                                        clean_next = next_timestamp_str.replace('Z', '+00:00')
                                        if 'T' in clean_next:
                                            if '+' not in clean_next and '-' in clean_next[-6:]:
                                                clean_next = clean_next + '+00:00'
                                            next_dt = datetime.fromisoformat(clean_next)
                                        else:
                                            next_dt = datetime.strptime(next_timestamp_str[:19], '%Y-%m-%d %H:%M:%S')
                                        
                                        duration = (next_dt - dt).total_seconds()
                                        
                                        if duration < 1:
                                            duration = 1
                                        elif duration > 7200:
                                            duration = 60
                                    except Exception as e:
                                        logger.warning(f"Failed to parse next timestamp: {e}")
                                        duration = 60
                                else:
                                    duration = 60
                            else:
                                try:
                                    now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
                                    time_since_last = (now - dt).total_seconds()
                                    
                                    if time_since_last < 7200:
                                        duration = min(time_since_last, 7200)
                                        if duration < 1:
                                            duration = 1
                                    else:
                                        duration = 60
                                except Exception:
                                    duration = 60
                            
                            result['statuses'][status] += duration
                            result['total_seconds'] += duration
                            
                            if status in productive_statuses:
                                result['productive_seconds'] += duration
                        
                        return result
                
                temp_tab = TempTab()
                time_data = temp_tab._calculate_time_from_logs(user_data)
                
                total_hours = int(time_data['total_seconds'] // 3600)
                total_mins = int((time_data['total_seconds'] % 3600) // 60)
                prod_hours = int(time_data['productive_seconds'] // 3600)
                prod_mins = int((time_data['productive_seconds'] % 3600) // 60)
                
                print(f"   ✅ Расчет времени:")
                print(f"      Общее время: {total_hours}:{total_mins:02d} ({time_data['total_seconds']:.0f} сек)")
                print(f"      Продуктивное время: {prod_hours}:{prod_mins:02d} ({time_data['productive_seconds']:.0f} сек)")
                print(f"      Сессий: {len(time_data['sessions'])}")
                
                if time_data['statuses']:
                    print(f"      Распределение по статусам:")
                    for status, seconds in sorted(time_data['statuses'].items(), key=lambda x: x[1], reverse=True)[:5]:
                        hours = int(seconds // 3600)
                        mins = int((seconds % 3600) // 60)
                        print(f"        {status}: {hours}:{mins:02d} ({seconds:.0f} сек)")
    
    # Проверяем формат запроса к базе
    print(f"\n5. Проверка формата запроса к базе...")
    print(f"   Используемый формат даты: '{date_str}T00:00:00+00:00' - '{date_str}T23:59:59+00:00'")
    print(f"   (Это формат, который используется в get_work_log_data для Supabase)")
    
    print("\n" + "=" * 80)
    print("ТЕСТ ЗАВЕРШЕН")
    print("=" * 80)
    
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
