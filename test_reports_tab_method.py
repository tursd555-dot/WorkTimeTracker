#!/usr/bin/env python3
"""
Тестовый скрипт для проверки наличия метода _calculate_time_from_logs в ReportsTab
"""
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from admin_app.reports_tab import ReportsTab
    import inspect
    
    # Проверяем наличие метода
    if hasattr(ReportsTab, '_calculate_time_from_logs'):
        method = getattr(ReportsTab, '_calculate_time_from_logs')
        if callable(method):
            print("✅ Метод _calculate_time_from_logs найден и является вызываемым")
            print(f"   Расположение: {inspect.getfile(method)}")
            print(f"   Строка определения: {inspect.getsourcelines(method)[1]}")
        else:
            print("❌ Метод _calculate_time_from_logs найден, но не является вызываемым")
    else:
        print("❌ Метод _calculate_time_from_logs НЕ найден в классе ReportsTab")
        print("\nДоступные методы класса:")
        methods = [m for m in dir(ReportsTab) if not m.startswith('__')]
        for m in sorted(methods):
            print(f"  - {m}")
    
    # Проверяем все методы, начинающиеся с _calculate
    calculate_methods = [m for m in dir(ReportsTab) if m.startswith('_calculate')]
    print(f"\nМетоды, начинающиеся с '_calculate': {calculate_methods}")
    
except Exception as e:
    print(f"❌ Ошибка при проверке: {e}")
    import traceback
    traceback.print_exc()
