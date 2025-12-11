#!/usr/bin/env python3
"""
Тестовый скрипт для проверки фильтрации по дате в отчетах
Запустите этот скрипт на вашей машине для диагностики проблемы
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
    import logging
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    
    print("=" * 80)
    print("ТЕСТ: Проверка фильтрации по дате в отчетах")
    print("=" * 80)
    
    # Инициализация
    print("\n1. Инициализация API и репозитория...")
    api = get_sheets_api()
    repo = AdminRepo(api)
    
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
    
    if not work_log_data:
        print("\n⚠️ ВНИМАНИЕ: Данных не найдено!")
        print("   Проверяем расширенный диапазон...")
        
        # Проверяем расширенный диапазон
        date_from_extended = date(2025, 12, 11).isoformat()
        date_to_extended = date(2025, 12, 13).isoformat()
        
        work_log_extended = repo.get_work_log_data(
            date_from=date_from_extended,
            date_to=date_to_extended
        )
        
        print(f"   За период 11.12-13.12 получено: {len(work_log_extended)} записей")
        
        if work_log_extended:
            # Анализируем даты
            dates_extended = defaultdict(int)
            timestamps_by_date = defaultdict(list)
            
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
                        timestamps_by_date[entry_date.isoformat()].append({
                            'timestamp': timestamp_str,
                            'dt': dt,
                            'entry': entry
                        })
                    except Exception as e:
                        print(f"     ⚠️ Ошибка парсинга '{timestamp_str}': {e}")
            
            print(f"   Распределение по датам:")
            for d, count in sorted(dates_extended.items()):
                marker = " <-- ТЕСТОВАЯ ДАТА" if d == date_str else ""
                print(f"     {d}: {count} записей{marker}")
            
            # Показываем примеры timestamp за каждую дату
            print(f"\n   Примеры timestamp по датам:")
            for d in sorted(timestamps_by_date.keys()):
                print(f"     {d}:")
                for ts_info in timestamps_by_date[d][:3]:
                    ts_str = ts_info['timestamp']
                    dt_obj = ts_info['dt']
                    entry = ts_info['entry']
                    email = entry.get('email', 'N/A')
                    status = entry.get('status', 'N/A')
                    # Показываем UTC и локальное время
                    utc_str = dt_obj.strftime('%Y-%m-%d %H:%M:%S UTC')
                    # Предполагаем UTC+3 для Москвы
                    local_dt = dt_obj.replace(tzinfo=None)  # Убираем timezone для сравнения
                    print(f"       {ts_str[:25]} -> UTC: {utc_str} | {email} | {status}")
            
            # Проверяем, есть ли записи, которые должны попасть в 12.12
            print(f"\n   Проверка записей, которые могут попасть в {date_str} из-за часовых поясов:")
            found_potential = False
            for entry in work_log_extended:
                timestamp_str = entry.get('timestamp', '')
                if timestamp_str:
                    try:
                        if 'T' in timestamp_str:
                            dt_utc = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        else:
                            dt_utc = datetime.strptime(timestamp_str[:19], '%Y-%m-%d %H:%M:%S')
                        
                        # Проверяем, попадает ли UTC дата в диапазон 12.12
                        utc_date = dt_utc.date()
                        
                        # Также проверяем локальное время (UTC+3 для Москвы)
                        dt_local = dt_utc.replace(tzinfo=None) + timedelta(hours=3)
                        local_date = dt_local.date()
                        
                        if utc_date.isoformat() == date_str or local_date.isoformat() == date_str:
                            if not found_potential:
                                print(f"     Найдены записи, которые могут относиться к {date_str}:")
                                found_potential = True
                            email = entry.get('email', 'N/A')
                            status = entry.get('status', 'N/A')
                            print(f"       UTC: {utc_date} {dt_utc.strftime('%H:%M:%S')} | Локальное (UTC+3): {local_date} {dt_local.strftime('%H:%M:%S')} | {email} | {status}")
                    except Exception as e:
                        pass
            
            if not found_potential:
                print(f"     Записей, которые могут относиться к {date_str}, не найдено")
                print(f"     Возможно, данные за {date_str} еще не были созданы на момент теста")
    
    if work_log_data:
        print(f"\n2.2. Анализ полученных данных:")
        
        # Проверяем распределение по датам
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
            marker = " <-- ОЖИДАЕМАЯ ДАТА" if d == date_str else " ⚠️ НЕОЖИДАННАЯ ДАТА"
            print(f"     {d}: {count} записей{marker}")
        
        # Проверяем распределение по сотрудникам
        print(f"\n2.3. Распределение по сотрудникам (топ-5):")
        emails_in_data = defaultdict(int)
        for entry in work_log_data:
            email = entry.get('email', '').lower()
            if email:
                emails_in_data[email] += 1
        
        for email, count in sorted(emails_in_data.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"     {email}: {count} записей")
        
        # Проверяем наличие статусов
        print(f"\n2.4. Распределение по статусам:")
        statuses_in_data = defaultdict(int)
        for entry in work_log_data:
            status = entry.get('status', '')
            if status:
                statuses_in_data[status] += 1
        
        for status, count in sorted(statuses_in_data.items(), key=lambda x: x[1], reverse=True):
            print(f"     {status}: {count} записей")
        
        # Проверяем наличие LOGIN/LOGOUT
        print(f"\n2.5. Распределение по action_type:")
        action_types_in_data = defaultdict(int)
        for entry in work_log_data:
            action_type = entry.get('action_type', '')
            if action_type:
                action_types_in_data[action_type] += 1
        
        for action_type, count in sorted(action_types_in_data.items(), key=lambda x: x[1], reverse=True):
            print(f"     {action_type}: {count} записей")
        
        # Проверяем расчет времени для первого сотрудника
        if emails_in_data:
            test_email = list(emails_in_data.keys())[0]
            print(f"\n2.6. Проверка расчета времени для сотрудника: {test_email}")
            
            user_data = [e for e in work_log_data if e.get('email', '').lower() == test_email]
            print(f"   Записей для сотрудника: {len(user_data)}")
            
            if user_data:
                # Простой расчет: считаем количество записей со статусами
                status_records = [e for e in user_data if e.get('status')]
                print(f"   Записей со статусами: {len(status_records)}")
                
                if status_records:
                    print(f"   Примеры записей со статусами:")
                    for i, entry in enumerate(status_records[:5], 1):
                        timestamp = entry.get('timestamp', 'N/A')
                        status = entry.get('status', 'N/A')
                        print(f"     {i}. {timestamp[:19]} | {status}")
    
    print("\n" + "=" * 80)
    print("РЕКОМЕНДАЦИИ:")
    print("=" * 80)
    print("1. Если данных за 12.12.2025 не найдено, но они есть в расширенном диапазоне:")
    print("   - Проблема в фильтрации по дате в запросе к базе")
    print("   - Проверьте часовые пояса")
    print("2. Если данные найдены, но расчет времени показывает 0:")
    print("   - Проблема в методе _calculate_time_from_logs")
    print("   - Проверьте формат timestamp в данных")
    print("3. Проверьте логи приложения на наличие ошибок")
    print("=" * 80)
    
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
