#!/usr/bin/env python3
# coding: utf-8
"""
Исправление отступов в строке 359
"""
from pathlib import Path
import shutil
from datetime import datetime

file_path = Path("admin_app/break_analytics_tab.py")

print("Исправление отступов...")

# Backup
backup_path = file_path.with_suffix(f'.py.bak.indent_{datetime.now().strftime("%H%M%S")}')
shutil.copy2(file_path, backup_path)

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Ищем строку 358-359
for i, line in enumerate(lines):
    if i == 357:  # Строка 358 (индекс 357)
        print(f"Строка 358: {repr(line)}")
    if i == 358:  # Строка 359 (индекс 358)
        print(f"Строка 359 ДО: {repr(line)}")
        # Должно быть 8 пробелов (2 уровня отступа)
        if '"""Обновляет Dashboard"""' in line:
            lines[i] = '        """Обновляет Dashboard"""\n'
            print(f"Строка 359 ПОСЛЕ: {repr(lines[i])}")

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print()
print("✓ Исправлено!")
print(f"Backup: {backup_path.name}")
print()
print("Перезапустите админку")