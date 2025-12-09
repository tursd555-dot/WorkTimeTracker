#!/usr/bin/env python3
"""
Тестирование Degradation Manager

Проверяет:
- Оценку режимов
- Переключение режимов
- Автоматическую оценку
- Capabilities
- Метрики
- Integration с Health Checker
"""

import sys
import time
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).parent))

from shared.resilience.degradation_manager import (
    DegradationManager,
    SystemMode,
    ModeCapabilities
)
from shared.health.health_checker import HealthChecker, ComponentHealth, HealthStatus
from datetime import datetime

# Счетчики для тестов
mode_changes = []
notifications = []


def test_basic_functionality():
    """Тест 1: Базовая функциональность"""
    print("="*60)
    print("TEST 1: Базовая функциональность")
    print("="*60)
    
    # Mock health checker
    health_checker = HealthChecker()
    
    manager = DegradationManager(health_checker=health_checker)
    
    print("\n1. Начальный режим...")
    mode = manager.get_current_mode()
    assert mode == SystemMode.FULL
    print(f"   ✓ Начальный режим: {mode.value}")
    
    print("\n2. Capabilities в FULL режиме...")
    cap = manager.get_capabilities()
    assert cap.sync_enabled == True
    assert cap.notifications_enabled == True
    assert cap.full_features == True
    assert cap.read_only == False
    print(f"   ✓ Sync: {cap.sync_enabled}")
    print(f"   ✓ Notifications: {cap.notifications_enabled}")
    print(f"   ✓ Full features: {cap.full_features}")
    print(f"   ✓ Read only: {cap.read_only}")
    
    print("\n3. Принудительная смена режима...")
    manager.force_mode(SystemMode.OFFLINE, "Testing")
    mode = manager.get_current_mode()
    assert mode == SystemMode.OFFLINE
    print(f"   ✓ Режим изменен: {mode.value}")
    
    print("\n4. Capabilities в OFFLINE режиме...")
    cap = manager.get_capabilities()
    assert cap.sync_enabled == False
    assert cap.notifications_enabled == False
    print(f"   ✓ Sync: {cap.sync_enabled}")
    print(f"   ✓ Notifications: {cap.notifications_enabled}")
    
    print("\n✅ TEST 1: PASSED")
    return True


def test_mode_evaluation():
    """Тест 2: Оценка режимов"""
    print("\n" + "="*60)
    print("TEST 2: Оценка режимов")
    print("="*60)
    
    health_checker = HealthChecker()
    manager = DegradationManager(health_checker=health_checker)
    
    # Helper для создания mock статусов
    def set_component_status(name, healthy):
        health_checker.statuses[name] = ComponentHealth(
            component=name,
            status=HealthStatus.HEALTHY if healthy else HealthStatus.UNHEALTHY,
            message="OK" if healthy else "Error",
            last_check=datetime.now(),
            check_duration_ms=0
        )
    
    print("\n1. Все компоненты здоровы → FULL...")
    set_component_status('database', True)
    set_component_status('sheets_api', True)
    set_component_status('telegram_api', True)
    set_component_status('internet', True)
    
    mode = manager.evaluate_mode()
    assert mode == SystemMode.FULL
    print(f"   ✓ Режим: {mode.value}")
    
    print("\n2. Telegram недоступен → DEGRADED...")
    set_component_status('telegram_api', False)
    
    mode = manager.evaluate_mode()
    assert mode == SystemMode.DEGRADED
    print(f"   ✓ Режим: {mode.value}")
    
    print("\n3. Нет интернета → OFFLINE...")
    set_component_status('internet', False)
    set_component_status('sheets_api', False)
    
    mode = manager.evaluate_mode()
    assert mode == SystemMode.OFFLINE
    print(f"   ✓ Режим: {mode.value}")
    
    print("\n4. БД недоступна → EMERGENCY...")
    set_component_status('database', False)
    
    mode = manager.evaluate_mode()
    assert mode == SystemMode.EMERGENCY
    print(f"   ✓ Режим: {mode.value}")
    
    print("\n✅ TEST 2: PASSED")
    return True


def test_mode_transitions():
    """Тест 3: История переходов"""
    print("\n" + "="*60)
    print("TEST 3: История переходов")
    print("="*60)
    
    health_checker = HealthChecker()
    manager = DegradationManager(health_checker=health_checker)
    
    print("\n1. Начальная история...")
    history = manager.get_mode_history()
    initial_count = len(history)
    print(f"   Переходов: {initial_count}")
    
    print("\n2. Переключаем режимы...")
    manager.force_mode(SystemMode.DEGRADED, "Test 1")
    manager.force_mode(SystemMode.OFFLINE, "Test 2")
    manager.force_mode(SystemMode.EMERGENCY, "Test 3")
    
    print("\n3. Проверяем историю...")
    history = manager.get_mode_history()
    print(f"   Всего переходов: {len(history)}")
    
    assert len(history) == initial_count + 3
    
    # Проверяем последний переход
    last = history[-1]
    assert last.from_mode == SystemMode.OFFLINE
    assert last.to_mode == SystemMode.EMERGENCY
    assert last.reason == "Test 3"
    print(f"\n   Последний переход:")
    print(f"   От: {last.from_mode.value}")
    print(f"   К: {last.to_mode.value}")
    print(f"   Причина: {last.reason}")
    print(f"   Время: {last.timestamp.strftime('%H:%M:%S')}")
    
    print("\n✅ TEST 3: PASSED")
    return True


def test_callbacks():
    """Тест 4: Callbacks"""
    print("\n" + "="*60)
    print("TEST 4: Callbacks")
    print("="*60)
    
    global mode_changes, notifications
    mode_changes = []
    notifications = []
    
    def mode_callback(old_mode, new_mode, reason):
        mode_changes.append((old_mode, new_mode, reason))
    
    def notification_callback(message):
        notifications.append(message)
    
    health_checker = HealthChecker()
    manager = DegradationManager(
        health_checker=health_checker,
        mode_change_callback=mode_callback,
        notification_callback=notification_callback
    )
    
    print("\n1. Переключаем режимы...")
    manager.force_mode(SystemMode.DEGRADED, "Test callback 1")
    manager.force_mode(SystemMode.OFFLINE, "Test callback 2")
    
    print("\n2. Проверяем mode callbacks...")
    print(f"   Вызовов: {len(mode_changes)}")
    assert len(mode_changes) == 2
    
    last_change = mode_changes[-1]
    print(f"   Последний: {last_change[0].value} → {last_change[1].value}")
    assert last_change[0] == SystemMode.DEGRADED
    assert last_change[1] == SystemMode.OFFLINE
    print("   ✓ Mode callbacks работают")
    
    print("\n3. Проверяем notification callbacks...")
    print(f"   Уведомлений: {len(notifications)}")
    assert len(notifications) == 2
    
    last_notif = notifications[-1]
    print(f"   Последнее: {last_notif[:50]}...")
    assert "OFFLINE" in last_notif.upper()
    print("   ✓ Notification callbacks работают")
    
    print("\n✅ TEST 4: PASSED")
    return True


def test_auto_evaluation():
    """Тест 5: Автоматическая оценка"""
    print("\n" + "="*60)
    print("TEST 5: Автоматическая оценка")
    print("="*60)
    
    health_checker = HealthChecker()
    manager = DegradationManager(health_checker=health_checker)
    
    # Helper для изменения статуса
    def set_db_status(healthy):
        health_checker.statuses['database'] = ComponentHealth(
            component='database',
            status=HealthStatus.HEALTHY if healthy else HealthStatus.UNHEALTHY,
            message="OK" if healthy else "Error",
            last_check=datetime.now(),
            check_duration_ms=0
        )
    
    print("\n1. Запуск автоматической оценки (интервал 1 сек)...")
    set_db_status(True)  # Начинаем с healthy
    manager.start_auto_evaluation(interval=1)
    
    print("   Ожидание 2 секунд...")
    time.sleep(2)
    
    print("\n2. Меняем статус БД на unhealthy...")
    set_db_status(False)
    
    print("   Ожидание 2 секунд для переоценки...")
    time.sleep(2)
    
    print("\n3. Проверяем режим...")
    mode = manager.get_current_mode()
    print(f"   Текущий режим: {mode.value}")
    
    # Режим должен был измениться на EMERGENCY (БД недоступна)
    assert mode == SystemMode.EMERGENCY
    print("   ✓ Режим автоматически изменился на EMERGENCY")
    
    print("\n4. Остановка автоматической оценки...")
    manager.stop_auto_evaluation()
    print("   ✓ Оценка остановлена")
    
    print("\n✅ TEST 5: PASSED")
    return True


def test_metrics():
    """Тест 6: Метрики"""
    print("\n" + "="*60)
    print("TEST 6: Метрики")
    print("="*60)
    
    health_checker = HealthChecker()
    manager = DegradationManager(health_checker=health_checker)
    
    print("\n1. Начальные метрики...")
    metrics = manager.get_metrics()
    
    print("   Метрики:")
    for key, value in metrics.items():
        if isinstance(value, float):
            print(f"      {key}: {value:.2f}")
        else:
            print(f"      {key}: {value}")
    
    assert metrics['mode_changes'] == 0
    assert metrics['current_mode'] == 'full'
    print("   ✓ Начальные метрики корректны")
    
    print("\n2. Делаем несколько переключений...")
    manager.force_mode(SystemMode.DEGRADED, "Test")
    time.sleep(0.5)
    manager.force_mode(SystemMode.OFFLINE, "Test")
    time.sleep(0.5)
    manager.force_mode(SystemMode.FULL, "Test")
    
    print("\n3. Проверяем обновленные метрики...")
    metrics = manager.get_metrics()
    
    print("   Обновленные метрики:")
    print(f"      mode_changes: {metrics['mode_changes']}")
    print(f"      current_mode: {metrics['current_mode']}")
    print(f"      time_in_degraded: {metrics['time_in_degraded']:.2f}s")
    print(f"      time_in_offline: {metrics['time_in_offline']:.2f}s")
    
    assert metrics['mode_changes'] == 3
    assert metrics['current_mode'] == 'full'
    assert metrics['time_in_degraded'] > 0
    assert metrics['time_in_offline'] > 0
    print("   ✓ Метрики обновляются корректно")
    
    print("\n✅ TEST 6: PASSED")
    return True


def test_all_capabilities():
    """Тест 7: Все capabilities"""
    print("\n" + "="*60)
    print("TEST 7: Все Capabilities")
    print("="*60)
    
    health_checker = HealthChecker()
    manager = DegradationManager(health_checker=health_checker)
    
    modes_to_test = [
        (SystemMode.FULL, True, True, True, False),
        (SystemMode.DEGRADED, True, False, True, False),
        (SystemMode.OFFLINE, False, False, True, False),
        (SystemMode.EMERGENCY, False, False, False, True),
    ]
    
    for mode, sync, notif, features, readonly in modes_to_test:
        print(f"\n{mode.value.upper()}:")
        manager.force_mode(mode, "Testing capabilities")
        cap = manager.get_capabilities()
        
        print(f"   Sync: {cap.sync_enabled} (expected: {sync})")
        print(f"   Notifications: {cap.notifications_enabled} (expected: {notif})")
        print(f"   Full features: {cap.full_features} (expected: {features})")
        print(f"   Read only: {cap.read_only} (expected: {readonly})")
        print(f"   Description: {cap.description}")
        
        assert cap.sync_enabled == sync
        assert cap.notifications_enabled == notif
        assert cap.full_features == features
        assert cap.read_only == readonly
        print("   ✓ Capabilities корректны")
    
    print("\n✅ TEST 7: PASSED")
    return True


def main():
    """Запуск всех тестов"""
    print("╔" + "="*58 + "╗")
    print("║" + " Degradation Manager Tests ".center(58) + "║")
    print("╚" + "="*58 + "╝")
    
    tests = [
        ("Базовая функциональность", test_basic_functionality),
        ("Оценка режимов", test_mode_evaluation),
        ("История переходов", test_mode_transitions),
        ("Callbacks", test_callbacks),
        ("Автоматическая оценка", test_auto_evaluation),
        ("Метрики", test_metrics),
        ("Все Capabilities", test_all_capabilities),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ {test_name}: FAILED with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Итоги
    print("\n" + "="*60)
    print("ИТОГИ ТЕСТИРОВАНИЯ")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"  {test_name:30} {status}")
    
    print("\n" + "="*60)
    print(f"Пройдено: {passed}/{total}")
    print("="*60)
    
    if passed == total:
        print("\n🎉 ВСЕ ТЕСТЫ УСПЕШНО ПРОЙДЕНЫ!")
        print("\nDegradation Manager готов к использованию:")
        print("  ✓ Автоматическая оценка режимов")
        print("  ✓ 4 режима работы (FULL/DEGRADED/OFFLINE/EMERGENCY)")
        print("  ✓ Callbacks для интеграции")
        print("  ✓ История переходов")
        print("  ✓ Детальные метрики")
        return 0
    else:
        print(f"\n⚠️  {total - passed} тест(ов) НЕ прошли")
        return 1


if __name__ == '__main__':
    sys.exit(main())
