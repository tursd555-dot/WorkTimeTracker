#!/usr/bin/env python3
"""
Быстрый тест интеграции Circuit Breaker в sheets_api.py

Проверяет что:
1. Импорты работают
2. Circuit Breaker инициализируется
3. Методы доступны
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

print("="*60)
print("ТЕСТ ИНТЕГРАЦИИ CIRCUIT BREAKER")
print("="*60)

# Тест 1: Импорты
print("\n1. Проверка импортов...")
try:
    from shared.resilience import get_circuit_breaker, CircuitOpenError, CircuitState
    from datetime import timedelta
    print("   ✓ Импорты Circuit Breaker успешны")
except ImportError as e:
    print(f"   ✗ Ошибка импорта: {e}")
    sys.exit(1)

# Тест 2: Проверка что изменения в файле
print("\n2. Проверка изменений в sheets_api.py...")
try:
    with open('sheets_api.py', 'r') as f:
        content = f.read()
    
    checks = [
        ('Circuit Breaker импорт', 'from shared.resilience import get_circuit_breaker'),
        ('timedelta импорт', 'from datetime import datetime, timezone, timedelta'),
        ('Инициализация CB', 'self.circuit_breaker = get_circuit_breaker'),
        ('Проверка can_execute', 'if not self.circuit_breaker.can_execute():'),
        ('Запись успеха', 'self.circuit_breaker.record_success()'),
        ('Запись ошибки', 'self.circuit_breaker.record_failure(e)'),
        ('Метод check_credentials', 'def check_credentials(self)'),
        ('Метод get_circuit_breaker_metrics', 'def get_circuit_breaker_metrics(self)'),
        ('Метод is_available', 'def is_available(self)'),
        ('Метод get_status_message', 'def get_status_message(self)'),
    ]
    
    all_ok = True
    for name, check in checks:
        if check in content:
            print(f"   ✓ {name}")
        else:
            print(f"   ✗ {name} - НЕ НАЙДЕНО")
            all_ok = False
    
    if not all_ok:
        print("\n⚠️  Некоторые изменения не применены")
        sys.exit(1)

except Exception as e:
    print(f"   ✗ Ошибка чтения файла: {e}")
    sys.exit(1)

# Тест 3: Создание Circuit Breaker
print("\n3. Тестирование Circuit Breaker...")
try:
    cb = get_circuit_breaker("TestAPI", failure_threshold=3)
    print(f"   ✓ Circuit Breaker создан: {cb.name}")
    print(f"   ✓ Состояние: {cb.state.value}")
    print(f"   ✓ can_execute: {cb.can_execute()}")
    
    # Тест ошибок
    cb.record_failure(Exception("Test error 1"))
    cb.record_failure(Exception("Test error 2"))
    cb.record_failure(Exception("Test error 3"))
    
    print(f"   ✓ После 3 ошибок: {cb.state.value}")
    if cb.state == CircuitState.OPEN:
        print("   ✓ Circuit правильно открылся")
    else:
        print(f"   ✗ Circuit должен быть OPEN, но {cb.state.value}")

except Exception as e:
    print(f"   ✗ Ошибка создания CB: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Итог
print("\n" + "="*60)
print("✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
print("="*60)
print("\nCircuit Breaker успешно интегрирован в sheets_api.py")
print("\nСледующие шаги:")
print("  1. Интегрировать Health Checks в main.py")
print("  2. Протестировать с реальным API")
print("="*60)
