#!/usr/bin/env python3
"""Проверка активных перерывов в БД"""
import os
from datetime import datetime, date
from dotenv import load_dotenv

load_dotenv()

from supabase import create_client

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
client = create_client(url, key)

print("="*80)
print("АКТИВНЫЕ ПЕРЕРЫВЫ В БД")
print("="*80)

today = date.today().isoformat()

# Читаем break_log
response = client.table('break_log')\
    .select('*')\
    .gte('start_time', f'{today}T00:00:00')\
    .is_('end_time', 'null')\
    .order('start_time', desc=True)\
    .execute()

print(f"\nНайдено активных перерывов: {len(response.data)}")
print()

for i, row in enumerate(response.data, 1):
    email = row.get('email', 'N/A')
    name = row.get('name', 'N/A')
    break_type = row.get('break_type', 'N/A')
    start_time = row.get('start_time', 'N/A')
    session_id = row.get('session_id', 'N/A')

    # Длительность
    if start_time != 'N/A':
        try:
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            now = datetime.now(start_dt.tzinfo)
            duration = int((now - start_dt).total_seconds() / 60)
        except:
            duration = '?'
    else:
        duration = '?'

    print(f"{i}. Email: {email}")
    print(f"   Имя: {name}")
    print(f"   Тип: {break_type}")
    print(f"   Начало: {start_time}")
    print(f"   Длительность: {duration} мин")
    print(f"   Session: {session_id}")
    print()

print("="*80)
print("ВСЕ ПЕРЕРЫВЫ ЗА СЕГОДНЯ (включая завершенные)")
print("="*80)

response_all = client.table('break_log')\
    .select('*')\
    .gte('start_time', f'{today}T00:00:00')\
    .order('start_time', desc=True)\
    .execute()

print(f"\nВсего перерывов за сегодня: {len(response_all.data)}")
print()

for i, row in enumerate(response_all.data[:10], 1):  # Только первые 10
    email = row.get('email', 'N/A')
    break_type = row.get('break_type', 'N/A')
    start_time = row.get('start_time', 'N/A')
    end_time = row.get('end_time', 'N/A')
    status = "✅ Завершен" if end_time else "🔴 Активен"

    print(f"{i}. {email} | {break_type} | {start_time[:19]} | {status}")

print("="*80)
