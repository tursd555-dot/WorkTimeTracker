#!/usr/bin/env python3
# coding: utf-8
"""
Проверка инициализации break_manager в user_app
"""
from pathlib import Path

log_file = Path(f"{Path.home()}/AppData/Roaming/WorkTimeTracker/logs/wtt-user.log")

if not log_file.exists():
    print(f"❌ Лог-файл не найден: {log_file}")
    exit(1)

print("=" * 80)
print("ПРОВЕРКА ИНИЦИАЛИЗАЦИИ BREAK SYSTEM")
print("=" * 80)
print()

with open(log_file, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Ищем последний запуск
init_found = False
success_found = False
error_found = False
last_init_lines = []

for i, line in enumerate(lines):
    if "Break system initialized" in line:
        init_found = True
        success_found = True
        last_init_lines = lines[max(0, i-5):i+1]
        print("✅ УСПЕШНАЯ ИНИЦИАЛИЗАЦИЯ:")
        print("".join(last_init_lines))
        print()
    
    if "Failed to initialize break system" in line:
        error_found = True
        last_init_lines = lines[max(0, i-10):i+5]
        print("❌ ОШИБКА ИНИЦИАЛИЗАЦИИ:")
        print("".join(last_init_lines))
        print()

if not init_found and not error_found:
    print("⚠️  Инициализация break system НЕ вызывалась")
    print()
    print("Проверьте:")
    print("  1. Импорт BreakManager в gui.py")
    print("  2. Метод _init_db() вызывается")
    print("  3. Нет ошибок импорта")

print()
print("=" * 80)
print("ПРОВЕРКА ВЫЗОВОВ on_status_change")
print("=" * 80)
print()

status_changes = []
for line in lines[-200:]:  # Последние 200 строк
    if "on_status_change" in line or "Break integration" in line or "Starting break" in line or "Ending break" in line:
        status_changes.append(line)

if status_changes:
    print(f"Найдено вызовов: {len(status_changes)}")
    print()
    print("Последние вызовы:")
    for line in status_changes[-10:]:
        print(line.strip())
else:
    print("❌ Вызовы on_status_change НЕ найдены")
    print()
    print("Это значит:")
    print("  - Метод set_status() не вызывает on_status_change()")
    print("  - Или threading не работает")
    print("  - Или ошибка в break_integration_worker()")

print()
print("=" * 80)
print("РЕКОМЕНДАЦИИ:")
print("=" * 80)

if error_found:
    print("1. Исправьте ошибку инициализации break system")
    print("2. Перезапустите user_app")
elif not status_changes:
    print("1. Проверьте что метод set_status() вызывает break_integration_worker()")
    print("2. Добавьте отладочный лог в начало break_integration_worker()")
else:
    print("✅ Всё работает! Если Dashboard не обновляется:")
    print("  - Подождите 30 секунд (автообновление)")
    print("  - Проверьте метод _get_active_breaks() в break_manager.py")
    print("  - Запустите: python diagnose_dashboard.py")

print()