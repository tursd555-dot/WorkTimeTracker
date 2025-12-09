#!/usr/bin/env python3
# coding: utf-8
"""
Проверка таблицы Groups
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api_adapter import get_sheets_api

print("=" * 80)
print("ПРОВЕРКА ТАБЛИЦЫ GROUPS")
print("=" * 80)
print()

sheets = get_sheets_api()

try:
    ws = sheets.get_worksheet("Groups")
    print("✓ Worksheet 'Groups' найден")
    print()
    
    rows = sheets._read_table(ws)
    print(f"Всего записей: {len(rows)}")
    print()
    
    if rows:
        print("ГРУППЫ:")
        for i, row in enumerate(rows, 1):
            # Показываем все поля
            print(f"\n  {i}. {dict(row)}")
            group_name = row.get("GroupName", "") or row.get("Group", "")
            print(f"     Название: '{group_name}'")
        
        print()
        print("=" * 80)
        print(f"✓ Найдено {len(rows)} групп(ы)")
        print("=" * 80)
    else:
        print("❌ Таблица Groups ПУСТАЯ!")
        print()
        print("Нужно создать группы:")
        print("  1. Перейдите в Админка → График → Группы")
        print("  2. Создайте хотя бы одну группу")
        print("  3. Или импортируйте существующие")
        
except Exception as e:
    print(f"❌ ОШИБКА: {e}")
    print()
    import traceback
    traceback.print_exc()

print()