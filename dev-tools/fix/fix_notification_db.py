#!/usr/bin/env python3
# coding: utf-8
"""
Исправление таблицы rule_last_sent - добавление колонки last_sent_utc
"""
import sqlite3
from pathlib import Path

db_path = Path("D:/proj vs code/WorkTimeTracker/notification_throttle.db")

if not db_path.exists():
    print(f"БД не найдена: {db_path}")
    exit(1)

print("Исправление notification_throttle.db...")

con = sqlite3.connect(db_path)
cur = con.cursor()

# Проверяем все таблицы
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cur.fetchall()]
print(f"Таблицы в БД: {tables}")

# Проверяем структуру rule_last_sent
if 'rule_last_sent' in tables:
    cur.execute("PRAGMA table_info(rule_last_sent)")
    columns = {row[1]: row[2] for row in cur.fetchall()}
    print(f"Текущие колонки rule_last_sent: {list(columns.keys())}")
    print(f"Типы: {columns}")
    
    if 'last_sent_utc' not in columns:
        print("Добавляем колонку last_sent_utc...")
        try:
            cur.execute("ALTER TABLE rule_last_sent ADD COLUMN last_sent_utc TEXT")
            con.commit()
            print("✓ Колонка добавлена")
        except Exception as e:
            print(f"Ошибка: {e}")
    else:
        print("✓ Колонка уже существует")
        
        # Проверим записи
        cur.execute("SELECT COUNT(*) FROM rule_last_sent")
        count = cur.fetchone()[0]
        print(f"Записей в таблице: {count}")
        
        if count > 0:
            cur.execute("SELECT * FROM rule_last_sent LIMIT 3")
            print("\nПример записей:")
            for row in cur.fetchall():
                print(f"  {row}")
else:
    print("❌ Таблица rule_last_sent НЕ существует!")
    print("Создаём таблицу...")
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS rule_last_sent (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id INTEGER NOT NULL,
            email TEXT,
            context TEXT,
            last_sent_utc TEXT NOT NULL,
            UNIQUE(rule_id, email, context)
        )
    """)
    con.commit()
    print("✓ Таблица создана")

con.close()
print()
print("Готово! Перезапустите user_app")