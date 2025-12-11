#!/usr/bin/env python3
"""
Проверка наличия метода _calculate_time_from_logs в файле reports_tab.py
"""
import re
import sys

def check_method_in_file(filepath):
    """Проверяет наличие метода в файле"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Проверяем наличие определения метода
        method_def_pattern = r'def _calculate_time_from_logs\s*\(self'
        if re.search(method_def_pattern, content):
            print("✅ Метод _calculate_time_from_logs определен в файле")
            
            # Находим строку с определением
            lines = content.split('\n')
            for i, line in enumerate(lines, 1):
                if re.search(method_def_pattern, line):
                    print(f"   Найден на строке {i}: {line.strip()}")
                    break
            
            # Проверяем, что метод вызывается
            call_pattern = r'self\._calculate_time_from_logs\s*\('
            calls = re.findall(call_pattern, content)
            print(f"   Найдено вызовов метода: {len(calls)}")
            if calls:
                print("   ✅ Метод вызывается в коде")
            else:
                print("   ⚠️ Метод определен, но не вызывается")
            
            # Проверяем импорт Any
            if 'from typing import' in content and 'Any' in content:
                import_line = [l for l in lines if 'from typing import' in l and 'Any' in l]
                if import_line:
                    print(f"   ✅ Импорт Any найден: {import_line[0].strip()}")
                else:
                    print("   ⚠️ Any используется, но не импортирован")
            
            return True
        else:
            print("❌ Метод _calculate_time_from_logs НЕ найден в файле")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка при чтении файла: {e}")
        return False

if __name__ == '__main__':
    filepath = 'admin_app/reports_tab.py'
    print(f"Проверка файла: {filepath}\n")
    check_method_in_file(filepath)
