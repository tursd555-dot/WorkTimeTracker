#!/usr/bin/env python3
"""Завершает старые тестовые перерывы"""
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

from supabase import create_client

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
client = create_client(url, key)

print("="*80)
print("ЗАВЕРШЕНИЕ СТАРЫХ ТЕСТОВЫХ ПЕРЕРЫВОВ")
print("="*80)

# Находим все активные перерывы с TEST_SESSION
response = client.table('break_log')\
    .select('*')\
    .is_('end_time', 'null')\
    .like('session_id', '%TEST_%')\
    .execute()

print(f"\nНайдено тестовых активных перерывов: {len(response.data)}")

if not response.data:
    print("✅ Тестовых перерывов нет, все чисто!")
else:
    now = datetime.now(timezone.utc).isoformat()

    for row in response.data:
        break_id = row['id']
        email = row.get('email', 'N/A')
        break_type = row.get('break_type', 'N/A')
        start_time = row.get('start_time', 'N/A')

        # Вычисляем длительность
        try:
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end_dt = datetime.now(timezone.utc)
            duration = int((end_dt - start_dt).total_seconds() / 60)
        except:
            duration = 0

        print(f"\n🔴 Завершаем: {email} | {break_type} | {start_time[:19]}")
        print(f"   Длительность: {duration} мин")

        # Завершаем перерыв
        update_data = {
            'end_time': now,
            'duration_minutes': duration,
            'status': 'Completed'
        }

        client.table('break_log')\
            .update(update_data)\
            .eq('id', break_id)\
            .execute()

        print(f"   ✅ Завершен")

print("\n" + "="*80)
print("ПРОВЕРКА: Активные перерывы после очистки")
print("="*80)

# Проверяем что осталось
response_check = client.table('break_log')\
    .select('*')\
    .is_('end_time', 'null')\
    .execute()

print(f"\nАктивных перерывов осталось: {len(response_check.data)}")

if response_check.data:
    for row in response_check.data:
        email = row.get('email', 'N/A')
        break_type = row.get('break_type', 'N/A')
        start_time = row.get('start_time', 'N/A')
        session = row.get('session_id', 'N/A')
        print(f"  - {email} | {break_type} | {start_time[:19]} | Session: {session}")
else:
    print("✅ Все перерывы завершены!")

print("="*80)
