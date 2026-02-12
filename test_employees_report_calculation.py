#!/usr/bin/env python3
"""
Тестовый скрипт для проверки расчета времени в отчете по сотрудникам
"""
import sys
import os
from datetime import datetime, timedelta
from collections import defaultdict

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from api_adapter import get_sheets_api
    from admin_app.repo import AdminRepo
    from admin_app.break_manager import BreakManager
    from admin_app.reports_tab import ReportsTab
    import logging
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    print("=" * 80)
    print("ТЕСТ: Проверка расчета времени в отчете по сотрудникам")
    print("=" * 80)
    
    # Инициализация
    print("\n1. Инициализация API и репозитория...")
    api = get_sheets_api()
    repo = AdminRepo(api)
    break_mgr = BreakManager(repo)
    
    print("✅ Инициализация завершена")
    
    # Получаем данные за последние 7 дней
    print("\n2. Получение данных из work_log за последние 7 дней...")
    date_to = datetime.now().date()
    date_from = date_to - timedelta(days=7)
    
    work_log_data = repo.get_work_log_data(
        date_from=date_from.isoformat(),
        date_to=date_to.isoformat()
    )
    
    print(f"✅ Получено записей: {len(work_log_data)}")
    
    # Группируем по сотрудникам
    print("\n3. Группировка данных по сотрудникам...")
    logs_by_email = defaultdict(list)
    for log_entry in work_log_data:
        email = log_entry.get('email', '').lower()
        if email:
            logs_by_email[email].append(log_entry)
    
    print(f"✅ Найдено сотрудников с данными: {len(logs_by_email)}")
    
    # Проверяем расчет времени для каждого сотрудника
    print("\n4. Проверка расчета времени для каждого сотрудника...")
    print("-" * 80)
    
    # Создаем экземпляр ReportsTab для доступа к методу расчета
    # Но нам нужен только метод, поэтому создадим временный объект или вызовем метод напрямую
    class TempReportsTab:
        def _calculate_time_from_logs(self, logs):
            """Копия метода из ReportsTab для тестирования"""
            from typing import Dict, List
            from collections import defaultdict
            
            result = {
                'total_seconds': 0,
                'productive_seconds': 0,
                'statuses': defaultdict(int),
                'sessions': set()
            }
            
            # Фильтруем только записи со статусами или важными action_type
            filtered_logs = []
            for log_entry in logs:
                status = log_entry.get('status', '')
                action_type = log_entry.get('action_type', '')
                if status or action_type in ['STATUS_CHANGE', 'LOGIN']:
                    filtered_logs.append(log_entry)
            
            if not filtered_logs:
                return result
            
            # Сортируем по timestamp
            sorted_logs = sorted(filtered_logs, key=lambda x: x.get('timestamp', ''))
            
            # Продуктивные статусы
            productive_statuses = {
                'В работе', 'На задаче', 'Чат', 'Запись', 
                'Стоматология', 'Входящие', 'Почта'
            }
            
            # Обрабатываем логи для расчета времени
            for i, log_entry in enumerate(sorted_logs):
                timestamp_str = log_entry.get('timestamp', '')
                status = log_entry.get('status', '')
                session_id = log_entry.get('session_id', '')
                
                if session_id:
                    result['sessions'].add(session_id)
                
                if not timestamp_str or not status:
                    continue
                
                # Парсим timestamp
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
                
                # Вычисляем длительность до следующей записи
                if i < len(sorted_logs) - 1:
                    next_timestamp_str = sorted_logs[i + 1].get('timestamp', '')
                    if next_timestamp_str:
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
                            elif duration > 28800:  # 8 часов
                                duration = 60
                        except Exception as e:
                            logger.warning(f"Failed to parse next timestamp '{next_timestamp_str}': {e}")
                            duration = 60
                    else:
                        duration = 60
                else:
                    duration = 60
                
                # Добавляем время к статусу
                result['statuses'][status] += duration
                result['total_seconds'] += duration
                
                if status in productive_statuses:
                    result['productive_seconds'] += duration
            
            return result
    
    temp_tab = TempReportsTab()
    
    # Проверяем топ-5 сотрудников по количеству записей
    sorted_emails = sorted(logs_by_email.items(), key=lambda x: len(x[1]), reverse=True)[:5]
    
    for email, logs in sorted_emails:
        print(f"\n📊 Сотрудник: {email}")
        print(f"   Всего записей: {len(logs)}")
        
        # Фильтруем записи со статусами
        filtered = [l for l in logs if l.get('status') or l.get('action_type') in ['STATUS_CHANGE', 'LOGIN']]
        print(f"   Записей со статусами: {len(filtered)}")
        
        # Рассчитываем время
        time_data = temp_tab._calculate_time_from_logs(logs)
        
        total_hours = int(time_data['total_seconds'] // 3600)
        total_mins = int((time_data['total_seconds'] % 3600) // 60)
        prod_hours = int(time_data['productive_seconds'] // 3600)
        prod_mins = int((time_data['productive_seconds'] % 3600) // 60)
        
        print(f"   Общее время: {total_hours}:{total_mins:02d} ({time_data['total_seconds']:.0f} сек)")
        print(f"   Продуктивное время: {prod_hours}:{prod_mins:02d} ({time_data['productive_seconds']:.0f} сек)")
        print(f"   Сессий: {len(time_data['sessions'])}")
        
        # Показываем распределение по статусам
        if time_data['statuses']:
            print(f"   Распределение по статусам:")
            for status, seconds in sorted(time_data['statuses'].items(), key=lambda x: x[1], reverse=True)[:5]:
                hours = int(seconds // 3600)
                mins = int((seconds % 3600) // 60)
                print(f"     - {status}: {hours}:{mins:02d} ({seconds:.0f} сек)")
        
        # Показываем первые и последние записи для проверки
        if filtered:
            sorted_filtered = sorted(filtered, key=lambda x: x.get('timestamp', ''))
            print(f"   Первая запись: {sorted_filtered[0].get('timestamp', 'N/A')} - {sorted_filtered[0].get('status', 'N/A')}")
            print(f"   Последняя запись: {sorted_filtered[-1].get('timestamp', 'N/A')} - {sorted_filtered[-1].get('status', 'N/A')}")
            
            # Показываем примеры расчетов длительности
            if len(sorted_filtered) >= 2:
                print(f"   Пример расчета длительности:")
                for i in range(min(3, len(sorted_filtered) - 1)):
                    ts1 = sorted_filtered[i].get('timestamp', '')
                    ts2 = sorted_filtered[i + 1].get('timestamp', '')
                    status1 = sorted_filtered[i].get('status', '')
                    
                    try:
                        clean1 = ts1.replace('Z', '+00:00')
                        if 'T' in clean1:
                            if '+' not in clean1 and '-' in clean1[-6:]:
                                clean1 = clean1 + '+00:00'
                            dt1 = datetime.fromisoformat(clean1)
                        else:
                            dt1 = datetime.strptime(clean1[:19], '%Y-%m-%d %H:%M:%S')
                        
                        clean2 = ts2.replace('Z', '+00:00')
                        if 'T' in clean2:
                            if '+' not in clean2 and '-' in clean2[-6:]:
                                clean2 = clean2 + '+00:00'
                            dt2 = datetime.fromisoformat(clean2)
                        else:
                            dt2 = datetime.strptime(clean2[:19], '%Y-%m-%d %H:%M:%S')
                        
                        duration = (dt2 - dt1).total_seconds()
                        mins = int(duration // 60)
                        print(f"     {status1}: {ts1[:19]} -> {ts2[:19]} = {mins} мин ({duration:.0f} сек)")
                    except Exception as e:
                        print(f"     Ошибка парсинга: {e}")
    
    print("\n" + "=" * 80)
    print("ТЕСТ ЗАВЕРШЕН")
    print("=" * 80)
    
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
