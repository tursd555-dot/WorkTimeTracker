#!/usr/bin/env python3
"""
Упрощенный тест фильтрации по дате
"""
import sys
import os
from datetime import datetime, timedelta, date, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api_adapter import get_sheets_api
from admin_app.repo import AdminRepo
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

print("=" * 80)
print("ПРОСТОЙ ТЕСТ ФИЛЬТРАЦИИ ПО ДАТЕ")
print("=" * 80)

api = get_sheets_api()
repo = AdminRepo(api)

# Тестируем 12.12.2025
test_date = "2025-12-12"
print(f"\n1. Получение данных за {test_date}...")

data = repo.get_work_log_data(date_from=test_date, date_to=test_date)
print(f"   Найдено записей: {len(data)}")

if data:
    print(f"\n2. Примеры записей (первые 5):")
    for i, entry in enumerate(data[:5], 1):
        ts = entry.get('timestamp', '')
        email = entry.get('email', '')
        status = entry.get('status', '')
        
        # Парсим и показываем UTC и локальное время
        try:
            if 'T' in ts:
                dt_utc = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            else:
                dt_utc = datetime.strptime(ts[:19], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
            
            # Определяем локальный offset
            local_tz = datetime.now().astimezone().tzinfo
            local_dt = dt_utc.astimezone(local_tz)
            offset = local_dt.utcoffset()
            offset_hours = offset.total_seconds() / 3600
            
            print(f"   {i}. UTC: {dt_utc.strftime('%Y-%m-%d %H:%M:%S')} | "
                  f"Локальное (UTC+{offset_hours:.0f}): {local_dt.strftime('%Y-%m-%d %H:%M:%S')} | "
                  f"{email} | {status}")
        except Exception as e:
            print(f"   {i}. {ts} | {email} | {status} (ошибка парсинга: {e})")
else:
    print("\n2. Данных не найдено. Проверяем расширенный диапазон...")
    extended = repo.get_work_log_data(date_from="2025-12-11", date_to="2025-12-13")
    print(f"   За 11-13.12 найдено: {len(extended)} записей")
    
    if extended:
        # Группируем по датам (локальное время)
        dates_count = {}
        for entry in extended:
            ts = entry.get('timestamp', '')
            if ts:
                try:
                    if 'T' in ts:
                        dt_utc = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    else:
                        dt_utc = datetime.strptime(ts[:19], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
                    
                    local_tz = datetime.now().astimezone().tzinfo
                    local_dt = dt_utc.astimezone(local_tz)
                    local_date = local_dt.date().isoformat()
                    dates_count[local_date] = dates_count.get(local_date, 0) + 1
                except:
                    pass
        
        print(f"\n   Распределение по локальным датам:")
        for d, count in sorted(dates_count.items()):
            marker = " <-- ТЕСТОВАЯ ДАТА" if d == test_date else ""
            print(f"     {d}: {count} записей{marker}")

print("\n" + "=" * 80)
