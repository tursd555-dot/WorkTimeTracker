#!/usr/bin/env python3
"""
Полный тест интеграции систем отказоустойчивости

Проверяет:
1. Circuit Breaker в sheets_api.py
2. Health Checks и Degradation Manager в main.py
3. Правильность всех изменений
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

print("="*70)
print(" ПОЛНЫЙ ТЕСТ ИНТЕГРАЦИИ СИСТЕМ ОТКАЗОУСТОЙЧИВОСТИ ".center(70, "="))
print("="*70)

# ===== ТЕСТ 1: SHEETS_API.PY =====
print("\n📋 ТЕСТ 1: Circuit Breaker в sheets_api.py")
print("-"*70)

try:
    with open('sheets_api.py', 'r') as f:
        sheets_content = f.read()
    
    sheets_checks = [
        ('Circuit Breaker импорт', 'from shared.resilience import get_circuit_breaker'),
        ('timedelta импорт', 'timedelta'),
        ('Инициализация CB', 'self.circuit_breaker = get_circuit_breaker'),
        ('Проверка can_execute', 'if not self.circuit_breaker.can_execute():'),
        ('Запись успеха', 'self.circuit_breaker.record_success()'),
        ('Запись ошибки', 'self.circuit_breaker.record_failure(e)'),
        ('Метод check_credentials', 'def check_credentials(self)'),
        ('Метод get_circuit_breaker_metrics', 'def get_circuit_breaker_metrics(self)'),
        ('Метод is_available', 'def is_available(self)'),
    ]
    
    sheets_ok = 0
    for name, check in sheets_checks:
        if check in sheets_content:
            print(f"  ✓ {name}")
            sheets_ok += 1
        else:
            print(f"  ✗ {name} - НЕ НАЙДЕНО")
    
    print(f"\nРезультат: {sheets_ok}/{len(sheets_checks)} проверок пройдено")
    
    if sheets_ok < len(sheets_checks):
        print("⚠️  Некоторые изменения в sheets_api.py не применены")

except Exception as e:
    print(f"  ✗ Ошибка чтения sheets_api.py: {e}")
    sheets_ok = 0

# ===== ТЕСТ 2: MAIN.PY =====
print("\n📋 ТЕСТ 2: Health Checks и Degradation Manager в main.py")
print("-"*70)

try:
    with open('user_app/main.py', 'r') as f:
        main_content = f.read()
    
    main_checks = [
        ('Health Checker импорт', 'from shared.health import'),
        ('get_health_checker импорт', 'get_health_checker'),
        ('register_all_checks импорт', 'register_all_checks'),
        ('Degradation Manager импорт', 'from shared.resilience import'),
        ('get_degradation_manager импорт', 'get_degradation_manager'),
        ('SystemMode импорт', 'SystemMode'),
        ('Поле health_checker', 'self.health_checker: HealthChecker = None'),
        ('Поле degradation_manager', 'self.degradation_manager: DegradationManager = None'),
        ('Поле current_system_mode', 'self.current_system_mode = SystemMode.FULL'),
        ('Инициализация Health Checker', 'self.health_checker = get_health_checker'),
        ('register_all_checks вызов', 'register_all_checks(self.health_checker)'),
        ('start_monitoring вызов', 'self.health_checker.start_monitoring'),
        ('Инициализация Degradation Manager', 'self.degradation_manager = get_degradation_manager'),
        ('start_auto_evaluation вызов', 'self.degradation_manager.start_auto_evaluation'),
        ('Метод _on_system_mode_change', 'def _on_system_mode_change(self'),
        ('Метод _on_system_notification', 'def _on_system_notification(self'),
        ('Метод _cleanup', 'def _cleanup(self)'),
        ('Регистрация cleanup', 'atexit.register(self._cleanup)'),
    ]
    
    main_ok = 0
    for name, check in main_checks:
        if check in main_content:
            print(f"  ✓ {name}")
            main_ok += 1
        else:
            print(f"  ✗ {name} - НЕ НАЙДЕНО")
    
    print(f"\nРезультат: {main_ok}/{len(main_checks)} проверок пройдено")
    
    if main_ok < len(main_checks):
        print("⚠️  Некоторые изменения в main.py не применены")

except Exception as e:
    print(f"  ✗ Ошибка чтения main.py: {e}")
    main_ok = 0

# ===== ТЕСТ 3: ПРОВЕРКА ИМПОРТОВ =====
print("\n📋 ТЕСТ 3: Проверка импортов")
print("-"*70)

imports_ok = 0
imports_total = 3

try:
    from shared.resilience import get_circuit_breaker, CircuitOpenError, CircuitState
    print("  ✓ shared.resilience импорты")
    imports_ok += 1
except ImportError as e:
    print(f"  ✗ shared.resilience импорты: {e}")

try:
    from shared.health import get_health_checker, register_all_checks, HealthChecker
    print("  ✓ shared.health импорты")
    imports_ok += 1
except ImportError as e:
    print(f"  ✗ shared.health импорты: {e}")

try:
    from shared.resilience import get_degradation_manager, SystemMode, DegradationManager
    print("  ✓ shared.resilience degradation импорты")
    imports_ok += 1
except ImportError as e:
    print(f"  ✗ shared.resilience degradation импорты: {e}")

print(f"\nРезультат: {imports_ok}/{imports_total} импортов успешны")

# ===== ТЕСТ 4: СОЗДАНИЕ ОБЪЕКТОВ =====
print("\n📋 ТЕСТ 4: Создание объектов")
print("-"*70)

objects_ok = 0
objects_total = 3

try:
    from shared.resilience import get_circuit_breaker
    cb = get_circuit_breaker("TestAPI", failure_threshold=3)
    print(f"  ✓ Circuit Breaker создан: {cb.name}, state={cb.state.value}")
    objects_ok += 1
except Exception as e:
    print(f"  ✗ Circuit Breaker: {e}")

try:
    from shared.health import get_health_checker
    hc = get_health_checker(failure_threshold=3)
    print(f"  ✓ Health Checker создан")
    objects_ok += 1
except Exception as e:
    print(f"  ✗ Health Checker: {e}")

try:
    from shared.resilience import get_degradation_manager
    from shared.health import get_health_checker
    hc = get_health_checker()
    dm = get_degradation_manager(health_checker=hc)
    print(f"  ✓ Degradation Manager создан: mode={dm.get_current_mode().value}")
    objects_ok += 1
except Exception as e:
    print(f"  ✗ Degradation Manager: {e}")

print(f"\nРезультат: {objects_ok}/{objects_total} объектов создано")

# ===== ИТОГИ =====
print("\n" + "="*70)
print(" ИТОГИ ИНТЕГРАЦИИ ".center(70, "="))
print("="*70)

total_checks = len(sheets_checks) + len(main_checks) + imports_total + objects_total
total_passed = sheets_ok + main_ok + imports_ok + objects_ok

print(f"\nПроверок пройдено: {total_passed}/{total_checks}")
print(f"  - sheets_api.py: {sheets_ok}/{len(sheets_checks)}")
print(f"  - main.py: {main_ok}/{len(main_checks)}")
print(f"  - Импорты: {imports_ok}/{imports_total}")
print(f"  - Объекты: {objects_ok}/{objects_total}")

if total_passed == total_checks:
    print("\n" + "🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! ".center(70, "="))
    print("="*70)
    print("\n✅ Интеграция успешно завершена!")
    print("\nСистемы готовы к работе:")
    print("  ✓ Circuit Breaker в sheets_api.py")
    print("  ✓ Health Checks в main.py")
    print("  ✓ Degradation Manager в main.py")
    print("\nСледующие шаги:")
    print("  1. Запустить приложение: python user_app/main.py")
    print("  2. Проверить логи на наличие сообщений о запуске систем")
    print("  3. Мониторить метрики в production")
    exit_code = 0
else:
    print("\n" + "⚠️  НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОЙДЕНЫ ".center(70, "="))
    print("="*70)
    print("\nПроверьте вывод выше для деталей.")
    print("Возможно, нужно повторить некоторые шаги интеграции.")
    exit_code = 1

print("="*70)
sys.exit(exit_code)
