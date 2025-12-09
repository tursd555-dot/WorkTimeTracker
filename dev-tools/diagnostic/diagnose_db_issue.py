#!/usr/bin/env python3
# coding: utf-8
"""
ДЕТАЛЬНАЯ ДИАГНОСТИКА проблемы с БД уведомлений
"""
import sys
import sqlite3
from pathlib import Path
from datetime import datetime

print("=" * 80)
print("ДИАГНОСТИКА БД УВЕДОМЛЕНИЙ")
print("=" * 80)
print()

# 1. Проверка config.py
print("1. ПРОВЕРКА CONFIG.PY:")
print("-" * 80)
try:
    from config import LOCAL_DB_PATH
    print(f"✓ LOCAL_DB_PATH из config: {LOCAL_DB_PATH}")
except ImportError as e:
    print(f"✗ Не удалось импортировать LOCAL_DB_PATH: {e}")
    LOCAL_DB_PATH = "notification_throttle.db"
    print(f"  Используем значение по умолчанию: {LOCAL_DB_PATH}")
print()

# 2. Поиск всех notification_throttle.db
print("2. ПОИСК ВСЕХ БД:")
print("-" * 80)
db_files = list(Path.cwd().rglob("notification_throttle.db"))
if db_files:
    for i, db_file in enumerate(db_files, 1):
        print(f"  [{i}] {db_file}")
        print(f"      Размер: {db_file.stat().st_size} байт")
        print(f"      Изменён: {datetime.fromtimestamp(db_file.stat().st_mtime)}")
else:
    print("  ✗ Не найдено ни одного файла notification_throttle.db")
print()

# 3. Проверка БД из LOCAL_DB_PATH
print("3. ПРОВЕРКА БД ИЗ LOCAL_DB_PATH:")
print("-" * 80)
db_path = Path(LOCAL_DB_PATH)
print(f"Путь: {db_path.absolute()}")
print(f"Существует: {db_path.exists()}")

if db_path.exists():
    print(f"Размер: {db_path.stat().st_size} байт")
    print()
    
    try:
        con = sqlite3.connect(str(db_path))
        cur = con.cursor()
        
        # Список таблиц
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cur.fetchall()]
        print(f"Таблицы: {tables}")
        print()
        
        # Структура rule_last_sent
        if 'rule_last_sent' in tables:
            print("Структура rule_last_sent:")
            cur.execute("PRAGMA table_info(rule_last_sent)")
            columns = cur.fetchall()
            for col in columns:
                print(f"  [{col[0]}] {col[1]} {col[2]} (NOT NULL: {col[3]}, DEFAULT: {col[4]})")
            
            # Проверяем наличие last_sent_utc
            col_names = [col[1] for col in columns]
            if 'last_sent_utc' in col_names:
                print()
                print("✓ Колонка last_sent_utc СУЩЕСТВУЕТ")
            else:
                print()
                print("✗ Колонка last_sent_utc ОТСУТСТВУЕТ!")
                print("  Доступные колонки:", col_names)
        else:
            print("✗ Таблица rule_last_sent НЕ СУЩЕСТВУЕТ!")
        
        con.close()
        
    except Exception as e:
        print(f"✗ Ошибка при работе с БД: {e}")
        import traceback
        traceback.print_exc()
else:
    print("✗ БД не существует по пути из LOCAL_DB_PATH")
print()

# 4. Эмуляция запроса из engine.py
print("4. ЭМУЛЯЦИЯ ЗАПРОСА ИЗ ENGINE.PY:")
print("-" * 80)

if db_path.exists():
    try:
        con = sqlite3.connect(str(db_path))
        cur = con.cursor()
        
        # Точно такой же запрос как в engine.py:163
        test_query = """
        SELECT last_sent_utc 
        FROM rule_last_sent 
        WHERE rule_id=? AND email=? AND context=?
        """
        
        print("Выполняем запрос:")
        print(test_query)
        print("С параметрами: (-1, 'test@example.com', 'test_context')")
        print()
        
        cur.execute(test_query, (-1, 'test@example.com', 'test_context'))
        result = cur.fetchone()
        
        print("✓ ЗАПРОС УСПЕШЕН!")
        print(f"Результат: {result}")
        print()
        print("=" * 80)
        print("ВЫВОД: БД КОРРЕКТНАЯ, запрос работает!")
        print("=" * 80)
        
        con.close()
        
    except sqlite3.OperationalError as e:
        print("✗ ОШИБКА ПРИ ВЫПОЛНЕНИИ ЗАПРОСА:")
        print(f"  {e}")
        print()
        print("=" * 80)
        print("ВЫВОД: В БД ПРОБЛЕМА!")
        print("=" * 80)
        print()
        print("РЕШЕНИЕ:")
        print("  1. Удалите БД: Remove-Item '{db_path}' -Force")
        print("  2. Перезапустите user_app - БД создастся заново")
        
    except Exception as e:
        print(f"✗ Неожиданная ошибка: {e}")
        import traceback
        traceback.print_exc()

# 5. Проверка импорта engine.py
print()
print("5. ПРОВЕРКА ИМПОРТА ENGINE.PY:")
print("-" * 80)

try:
    # Добавляем путь к проекту
    project_root = Path(__file__).parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    
    from notifications import engine
    
    print("✓ Модуль engine импортирован")
    print(f"  Использует БД: {engine.LOCAL_DB_PATH if hasattr(engine, 'LOCAL_DB_PATH') else 'Неизвестно'}")
    
    # Проверяем функцию _open_db
    if hasattr(engine, '_open_db'):
        print()
        print("Тестируем _open_db():")
        try:
            test_con = engine._open_db()
            print("  ✓ Подключение успешно")
            
            # Проверяем структуру
            test_cur = test_con.execute("PRAGMA table_info(rule_last_sent)")
            test_cols = [row[1] for row in test_cur.fetchall()]
            print(f"  Колонки: {test_cols}")
            
            if 'last_sent_utc' in test_cols:
                print("  ✓ Колонка last_sent_utc найдена через _open_db()")
            else:
                print("  ✗ Колонка last_sent_utc ОТСУТСТВУЕТ через _open_db()!")
                print("  ⚠️  ENGINE.PY ИСПОЛЬЗУЕТ ДРУГУЮ БД!")
            
            test_con.close()
            
        except Exception as e:
            print(f"  ✗ Ошибка: {e}")
            import traceback
            traceback.print_exc()
    
except ImportError as e:
    print(f"✗ Не удалось импортировать engine: {e}")
except Exception as e:
    print(f"✗ Ошибка при тестировании engine: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 80)
print("ИТОГОВЫЕ РЕКОМЕНДАЦИИ:")
print("=" * 80)
print()
print("Если engine.py использует ДРУГУЮ БД:")
print("  → Найдите ВСЕ notification_throttle.db и удалите их")
print("  → Перезапустите приложение")
print()
print("Если БД корректная, но ошибка всё равно есть:")
print("  → Проблема в кэшировании подключений")
print("  → Полностью перезапустите Python процесс")
print()
