#!/usr/bin/env python3
# coding: utf-8
"""
Исправление таблицы rule_last_sent в local_backup.db
"""
import sqlite3
from pathlib import Path

db_path = Path("D:/proj vs code/WorkTimeTracker/local_backup.db")

print("=" * 80)
print("ИСПРАВЛЕНИЕ ТАБЛИЦЫ rule_last_sent")
print("=" * 80)
print()

if not db_path.exists():
    print(f"✗ БД не найдена: {db_path}")
    exit(1)

print(f"БД: {db_path}")
print()

con = sqlite3.connect(db_path)
cur = con.cursor()

# 1. Проверяем текущую структуру
print("1. ТЕКУЩАЯ СТРУКТУРА:")
print("-" * 80)
cur.execute("PRAGMA table_info(rule_last_sent)")
old_columns = cur.fetchall()
for col in old_columns:
    print(f"  {col[1]} {col[2]}")
print()

# 2. Пересоздаём таблицу с правильной структурой
print("2. ПЕРЕСОЗДАНИЕ ТАБЛИЦЫ:")
print("-" * 80)

try:
    # Удаляем старую таблицу
    print("Удаляем старую таблицу...")
    cur.execute("DROP TABLE IF EXISTS rule_last_sent")
    
    # Создаём новую с правильной структурой
    print("Создаём новую таблицу с правильной структурой...")
    cur.execute("""
        CREATE TABLE rule_last_sent (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id INTEGER NOT NULL,
            email TEXT,
            context TEXT,
            last_sent_utc TEXT NOT NULL,
            UNIQUE(rule_id, email, context)
        )
    """)
    
    con.commit()
    print("✓ Таблица пересоздана")
    print()
    
    # 3. Проверяем новую структуру
    print("3. НОВАЯ СТРУКТУРА:")
    print("-" * 80)
    cur.execute("PRAGMA table_info(rule_last_sent)")
    new_columns = cur.fetchall()
    for col in new_columns:
        print(f"  {col[1]} {col[2]}")
    print()
    
    # 4. Проверяем что запрос работает
    print("4. ПРОВЕРКА ЗАПРОСА:")
    print("-" * 80)
    test_query = """
    SELECT last_sent_utc 
    FROM rule_last_sent 
    WHERE rule_id=? AND email=? AND context=?
    """
    
    cur.execute(test_query, (-1, 'test@example.com', 'test_context'))
    result = cur.fetchone()
    print("✓ Запрос выполнен успешно!")
    print(f"Результат: {result}")
    print()
    
    print("=" * 80)
    print("✓ ИСПРАВЛЕНИЕ ЗАВЕРШЕНО!")
    print("=" * 80)
    print()
    print("Теперь перезапустите user_app - уведомления заработают!")
    
except Exception as e:
    print(f"✗ Ошибка: {e}")
    import traceback
    traceback.print_exc()
    con.rollback()
finally:
    con.close()
