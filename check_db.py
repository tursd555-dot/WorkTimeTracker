#!/usr/bin/env python3
"""
Скрипт для проверки несинхронизированных записей в локальной БД
"""

import sqlite3
import sys
from datetime import datetime, timedelta

DB_PATH = r"D:\proj vs code\WorkTimeTracker\local_backup.db"

def check_unsynced():
    """Проверяет несинхронизированные записи"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        
        # Все несинхронизированные
        cur.execute("SELECT COUNT(*) FROM logs WHERE synced = 0")
        total_unsynced = cur.fetchone()[0]
        
        # Свежие (< 15 минут)
        cutoff_15 = (datetime.now() - timedelta(minutes=15)).isoformat()
        cur.execute(
            "SELECT COUNT(*) FROM logs WHERE synced = 0 AND timestamp >= ?",
            (cutoff_15,)
        )
        fresh_15 = cur.fetchone()[0]
        
        # Свежие (< 5 минут)
        cutoff_5 = (datetime.now() - timedelta(minutes=5)).isoformat()
        cur.execute(
            "SELECT COUNT(*) FROM logs WHERE synced = 0 AND timestamp >= ?",
            (cutoff_5,)
        )
        fresh_5 = cur.fetchone()[0]
        
        # Последние 10 несинхронизированных
        cur.execute(
            """
            SELECT id, email, status, action_type, timestamp, synced 
            FROM logs 
            WHERE synced = 0 
            ORDER BY timestamp DESC 
            LIMIT 10
            """
        )
        last_10 = cur.fetchall()
        
        conn.close()
        
        print("=" * 80)
        print("📊 СТАТИСТИКА НЕСИНХРОНИЗИРОВАННЫХ ЗАПИСЕЙ")
        print("=" * 80)
        print(f"\n📦 Всего несинхронизированных: {total_unsynced}")
        print(f"🚨 Свежих (< 15 минут): {fresh_15}")
        print(f"⚡ Свежих (< 5 минут): {fresh_5}")
        
        if last_10:
            print(f"\n📋 Последние 10 несинхронизированных записей:")
            print("-" * 80)
            for row in last_10:
                id, email, status, action_type, timestamp, synced = row
                # Обработка None значений
                email = email or "N/A"
                status = status or "N/A"
                action_type = action_type or "N/A"
                timestamp = timestamp or "N/A"
                print(f"  ID: {id:4d} | {email:20s} | {status:15s} | {action_type:15s} | {timestamp}")
            print("-" * 80)
        
        return total_unsynced, fresh_15, fresh_5
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 0, 0, 0

if __name__ == "__main__":
    check_unsynced()
