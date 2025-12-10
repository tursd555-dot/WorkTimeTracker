#!/usr/bin/env python3
"""Проверка локальной SQLite БД"""
import sqlite3
from datetime import datetime, date

DB_PATH = "local_backup.db"

print("="*80)
print("ЛОКАЛЬНАЯ БД - ПРОВЕРКА")
print("="*80)

try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Проверяем структуру БД
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print(f"\nТаблицы в БД: {[t[0] for t in tables]}")

    # Проверяем есть ли таблица break_log
    if ('break_log',) in tables or ('breaks',) in tables:
        # Пробуем обе возможные названия
        for table_name in ['break_log', 'breaks']:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                print(f"\n📊 Таблица '{table_name}': {count} записей")

                # Показываем последние 5 записей
                cursor.execute(f"""
                    SELECT * FROM {table_name}
                    ORDER BY rowid DESC
                    LIMIT 5
                """)
                rows = cursor.fetchall()

                if rows:
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    columns = [col[1] for col in cursor.fetchall()]
                    print(f"\nКолонки: {columns}")
                    print("\nПоследние 5 записей:")
                    for i, row in enumerate(rows, 1):
                        print(f"\n{i}. {dict(zip(columns, row))}")
                else:
                    print(f"  Нет записей в {table_name}")

            except sqlite3.OperationalError:
                continue
    else:
        print("\n❌ Таблица break_log/breaks не найдена!")

    # Проверяем logs таблицу
    if ('logs',) in tables:
        today = date.today().isoformat()
        cursor.execute("""
            SELECT COUNT(*) FROM logs
            WHERE date(timestamp) = ?
        """, (today,))
        count = cursor.fetchone()[0]
        print(f"\n📊 Таблица 'logs': {count} записей за сегодня")

        # Последние 5 записей
        cursor.execute("""
            SELECT timestamp, email, status, action_type, synced_to_sheets
            FROM logs
            ORDER BY id DESC
            LIMIT 5
        """)
        rows = cursor.fetchall()
        if rows:
            print("\nПоследние 5 действий:")
            for i, row in enumerate(rows, 1):
                ts, email, status, action, synced = row
                sync_status = "✅ Синхр." if synced else "⏳ Не синхр."
                print(f"  {i}. {ts} | {email} | {status} | {action} | {sync_status}")

    conn.close()

except FileNotFoundError:
    print(f"\n❌ Файл {DB_PATH} не найден!")
except Exception as e:
    print(f"\n❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()

print("="*80)
