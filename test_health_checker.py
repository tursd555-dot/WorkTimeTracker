#!/usr/bin/env python3
"""
Тестирование Health Checker System

Проверяет:
- Регистрацию проверок
- Выполнение проверок
- Мониторинг
- Алерты
- Метрики
"""

import sys
import time
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from shared.health.health_checker import HealthChecker, HealthStatus, ComponentHealth
from shared.health.checks import (
    check_database_health,
    check_internet_health,
    check_disk_space_health,
    check_memory_health
)

# Счетчики для тестов
alert_count = 0
last_alert = None


def test_basic_functionality():
    """Тест 1: Базовая функциональность"""
    print("="*60)
    print("TEST 1: Базовая функциональность")
    print("="*60)
    
    checker = HealthChecker(failure_threshold=2)
    
    # Простая проверка
    def simple_check():
        return True, "All good", {"value": 42}
    
    print("\n1. Регистрация проверки...")
    checker.register_check("test_component", simple_check)
    assert "test_component" in checker.checks
    print("   ✓ Проверка зарегистрирована")
    
    print("\n2. Выполнение проверки...")
    result = checker.check_component("test_component")
    assert result is not None
    assert result.healthy
    assert result.status == HealthStatus.HEALTHY
    assert result.message == "All good"
    assert result.details.get("value") == 42
    print(f"   ✓ Проверка выполнена: {result.message}")
    print(f"   ✓ Время выполнения: {result.check_duration_ms:.2f}ms")
    
    print("\n3. Проверка всех компонентов...")
    results = checker.check_all()
    assert len(results) == 1
    assert "test_component" in results
    print(f"   ✓ Проверено компонентов: {len(results)}")
    
    print("\n4. Общий статус системы...")
    overall = checker.get_overall_status()
    assert overall.healthy
    assert overall.status == HealthStatus.HEALTHY
    print(f"   ✓ Статус: {overall.status.value}")
    print(f"   ✓ Сообщение: {overall.message}")
    
    print("\n✅ TEST 1: PASSED")
    return True


def test_unhealthy_component():
    """Тест 2: Нездоровый компонент"""
    print("\n" + "="*60)
    print("TEST 2: Нездоровый компонент")
    print("="*60)
    
    checker = HealthChecker(failure_threshold=2)
    
    # Проверка с ошибкой
    def failing_check():
        return False, "Something went wrong", None
    
    print("\n1. Регистрация failing check...")
    checker.register_check("failing", failing_check)
    
    print("\n2. Первая неудачная проверка...")
    result = checker.check_component("failing")
    assert not result.healthy
    assert result.consecutive_failures == 1
    print(f"   ✗ Статус: {result.status.value}")
    print(f"   ✗ Сообщение: {result.message}")
    print(f"   ✗ Неудач подряд: {result.consecutive_failures}")
    
    print("\n3. Вторая неудачная проверка...")
    result = checker.check_component("failing")
    assert result.consecutive_failures == 2
    print(f"   ✗ Неудач подряд: {result.consecutive_failures}")
    
    print("\n4. Общий статус (должен быть unhealthy)...")
    overall = checker.get_overall_status()
    assert not overall.healthy
    assert overall.status == HealthStatus.UNHEALTHY
    print(f"   ✗ Статус: {overall.status.value}")
    print(f"   ✗ Сообщение: {overall.message}")
    
    print("\n✅ TEST 2: PASSED")
    return True


def test_alerts():
    """Тест 3: Алерты"""
    print("\n" + "="*60)
    print("TEST 3: Алерты")
    print("="*60)
    
    global alert_count, last_alert
    alert_count = 0
    last_alert = None
    
    def alert_callback(message):
        global alert_count, last_alert
        alert_count += 1
        last_alert = message
    
    checker = HealthChecker(
        failure_threshold=3,
        alert_callback=alert_callback
    )
    
    # Failing check
    def failing_check():
        return False, "Service down", None
    
    print("\n1. Регистрация failing check...")
    checker.register_check("service", failing_check)
    
    print("\n2. Первые 2 неудачи (без алерта)...")
    for i in range(2):
        checker.check_component("service")
        print(f"   Неудача {i+1}: alerts={alert_count}")
    
    assert alert_count == 0
    print("   ✓ Алерты не отправлены (порог не достигнут)")
    
    print("\n3. Третья неудача (алерт)...")
    checker.check_component("service")
    print(f"   Неудача 3: alerts={alert_count}")
    
    assert alert_count == 1
    assert last_alert is not None
    assert "service" in last_alert
    print("   ✓ Алерт отправлен!")
    print(f"   ✓ Текст алерта:\n{last_alert[:100]}...")
    
    print("\n4. Четвертая неудача (повторный алерт)...")
    checker.check_component("service")
    assert alert_count == 2
    print(f"   ✓ Повторный алерт отправлен (total={alert_count})")
    
    print("\n✅ TEST 3: PASSED")
    return True


def test_monitoring():
    """Тест 4: Периодический мониторинг"""
    print("\n" + "="*60)
    print("TEST 4: Периодический мониторинг")
    print("="*60)
    
    checker = HealthChecker()
    
    check_count = 0
    
    def counting_check():
        nonlocal check_count
        check_count += 1
        return True, f"Check #{check_count}", None
    
    print("\n1. Регистрация проверки...")
    checker.register_check("counting", counting_check)
    
    print("\n2. Запуск мониторинга (интервал 1 сек)...")
    checker.start_monitoring(interval=1)
    
    print("   Ожидание 3.5 секунды...")
    time.sleep(3.5)
    
    print(f"\n3. Проверка выполнений...")
    print(f"   Выполнено проверок: {check_count}")
    
    # Должно быть ~3 проверки (с небольшой погрешностью)
    assert check_count >= 2, f"Expected >= 2 checks, got {check_count}"
    assert check_count <= 5, f"Expected <= 5 checks, got {check_count}"
    print(f"   ✓ Мониторинг работает (~{check_count} проверок за 3.5 сек)")
    
    print("\n4. Остановка мониторинга...")
    checker.stop_monitoring()
    
    old_count = check_count
    time.sleep(2)
    
    assert check_count == old_count
    print(f"   ✓ Мониторинг остановлен (проверок не увеличилось)")
    
    print("\n✅ TEST 4: PASSED")
    return True


def test_real_checks():
    """Тест 5: Реальные проверки"""
    print("\n" + "="*60)
    print("TEST 5: Реальные проверки")
    print("="*60)
    
    print("\n1. Проверка интернета...")
    healthy, message, details = check_internet_health()
    print(f"   Результат: {healthy}")
    print(f"   Сообщение: {message}")
    if details:
        print(f"   Детали: {details}")
    
    print("\n2. Проверка дискового пространства...")
    healthy, message, details = check_disk_space_health()
    print(f"   Результат: {healthy}")
    print(f"   Сообщение: {message}")
    if details:
        for key, value in details.items():
            print(f"      {key}: {value}")
    
    print("\n3. Проверка памяти...")
    healthy, message, details = check_memory_health()
    print(f"   Результат: {healthy}")
    print(f"   Сообщение: {message}")
    if details:
        for key, value in details.items():
            print(f"      {key}: {value}")
    
    print("\n4. Проверка БД (если доступна)...")
    try:
        healthy, message, details = check_database_health()
        print(f"   Результат: {healthy}")
        print(f"   Сообщение: {message}")
        if details:
            for key, value in details.items():
                print(f"      {key}: {value}")
    except Exception as e:
        print(f"   ⚠️  БД недоступна: {e}")
    
    print("\n   ✓ Все реальные проверки выполнены")
    
    print("\n✅ TEST 5: PASSED")
    return True


def test_metrics():
    """Тест 6: Метрики"""
    print("\n" + "="*60)
    print("TEST 6: Метрики")
    print("="*60)
    
    checker = HealthChecker()
    
    def healthy_check():
        return True, "OK", None
    
    def unhealthy_check():
        return False, "Error", None
    
    print("\n1. Регистрация проверок...")
    checker.register_check("healthy", healthy_check)
    checker.register_check("unhealthy", unhealthy_check)
    
    print("\n2. Выполнение проверок...")
    checker.check_all()
    checker.check_all()
    checker.check_all()
    
    print("\n3. Получение метрик...")
    metrics = checker.get_metrics()
    
    print("\n   Метрики:")
    for key, value in metrics.items():
        print(f"      {key}: {value}")
    
    assert metrics['total_checks'] == 6  # 3 × 2 компонента
    assert metrics['healthy_checks'] == 3
    assert metrics['unhealthy_checks'] == 3
    print("\n   ✓ Метрики собираются корректно")
    
    print("\n✅ TEST 6: PASSED")
    return True


def main():
    """Запуск всех тестов"""
    print("╔" + "="*58 + "╗")
    print("║" + " Health Checker Tests ".center(58) + "║")
    print("╚" + "="*58 + "╝")
    
    tests = [
        ("Базовая функциональность", test_basic_functionality),
        ("Нездоровый компонент", test_unhealthy_component),
        ("Алерты", test_alerts),
        ("Мониторинг", test_monitoring),
        ("Реальные проверки", test_real_checks),
        ("Метрики", test_metrics),
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
        print("\nHealth Checker готов к использованию:")
        print("  ✓ Автоматический мониторинг компонентов")
        print("  ✓ Алерты при проблемах")
        print("  ✓ Детальные метрики")
        print("  ✓ Предустановленные проверки")
        print("  ✓ Периодический мониторинг")
        return 0
    else:
        print(f"\n⚠️  {total - passed} тест(ов) НЕ прошли")
        return 1


if __name__ == '__main__':
    sys.exit(main())
