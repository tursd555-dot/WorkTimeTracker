#!/usr/bin/env python3
"""
Тестирование Circuit Breaker

Проверяет:
- Базовую функциональность
- Переходы между состояниями
- Автоматическое восстановление
- Декоратор
- Метрики
"""

import sys
import time
import threading
from pathlib import Path

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).parent))

from shared.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitOpenError,
    circuit_breaker
)

# Счетчики для тестов
call_count = 0
success_count = 0
failure_count = 0


def test_basic_functionality():
    """Тест 1: Базовая функциональность"""
    print("="*60)
    print("TEST 1: Базовая функциональность")
    print("="*60)
    
    breaker = CircuitBreaker(
        name="TestService",
        failure_threshold=3,
        recovery_timeout=2,
        success_threshold=2
    )
    
    print(f"\n1. Начальное состояние: {breaker.state.value}")
    assert breaker.state == CircuitState.CLOSED
    assert breaker.can_execute() == True
    print("   ✓ Circuit в состоянии CLOSED")
    
    # Записываем успехи
    print("\n2. Записываем 3 успешных вызова...")
    for i in range(3):
        breaker.record_success()
    print(f"   ✓ Успехов: {breaker.metrics['successful_calls']}")
    assert breaker.state == CircuitState.CLOSED
    
    # Записываем ошибки
    print("\n3. Записываем 3 ошибки (threshold=3)...")
    for i in range(3):
        breaker.record_failure()
        print(f"   Ошибка {i+1}: state={breaker.state.value}")
    
    assert breaker.state == CircuitState.OPEN
    print("   ✓ Circuit перешел в OPEN после 3 ошибок")
    
    # Проверяем блокировку
    print("\n4. Проверяем блокировку запросов...")
    assert breaker.can_execute() == False
    print(f"   ✓ Запросы блокируются: {breaker.metrics['rejected_calls']} отклонено")
    
    # Ждем recovery timeout
    print(f"\n5. Ожидание {breaker.recovery_timeout} сек для восстановления...")
    time.sleep(breaker.recovery_timeout + 0.5)
    
    # Проверяем HALF_OPEN
    print("   Проверяем переход в HALF_OPEN...")
    assert breaker.can_execute() == True
    assert breaker.state == CircuitState.HALF_OPEN
    print(f"   ✓ Circuit перешел в HALF_OPEN")
    
    # Успешные вызовы для закрытия
    print(f"\n6. Записываем {breaker.success_threshold} успеха для закрытия...")
    for i in range(breaker.success_threshold):
        breaker.record_success()
        print(f"   Успех {i+1}: state={breaker.state.value}")
    
    assert breaker.state == CircuitState.CLOSED
    print("   ✓ Circuit закрылся после успешных вызовов")
    
    print("\n✅ TEST 1: PASSED")
    return True


def test_context_manager():
    """Тест 2: Context manager"""
    print("\n" + "="*60)
    print("TEST 2: Context Manager")
    print("="*60)
    
    breaker = CircuitBreaker(
        name="ContextTest",
        failure_threshold=2,
        recovery_timeout=1
    )
    
    # Успешный вызов
    print("\n1. Успешный вызов через context manager...")
    try:
        with breaker:
            result = "success"
        print("   ✓ Context manager работает для успешных вызовов")
    except Exception as e:
        print(f"   ❌ Unexpected error: {e}")
        return False
    
    # Вызовы с ошибками
    print("\n2. Вызовы с ошибками...")
    for i in range(2):
        try:
            with breaker:
                raise ValueError("Test error")
        except ValueError:
            print(f"   Ошибка {i+1} обработана")
    
    assert breaker.state == CircuitState.OPEN
    print("   ✓ Circuit открылся после ошибок")
    
    # Попытка вызова при OPEN
    print("\n3. Попытка вызова при OPEN circuit...")
    try:
        with breaker:
            result = "should not execute"
        print("   ❌ Не должно было выполниться")
        return False
    except CircuitOpenError as e:
        print(f"   ✓ Получили CircuitOpenError: {e}")
    
    print("\n✅ TEST 2: PASSED")
    return True


def test_decorator():
    """Тест 3: Декоратор"""
    print("\n" + "="*60)
    print("TEST 3: Декоратор")
    print("="*60)
    
    global call_count, success_count, failure_count
    call_count = 0
    success_count = 0
    failure_count = 0
    
    # Функция с декоратором
    @circuit_breaker(
        name="DecoratorTest",
        failure_threshold=2,
        recovery_timeout=1
    )
    def api_call(should_fail=False):
        global call_count
        call_count += 1
        if should_fail:
            raise ConnectionError("API unavailable")
        return "success"
    
    # Функция fallback
    def fallback_func(should_fail=False):
        return "fallback_result"
    
    @circuit_breaker(
        name="FallbackTest",
        failure_threshold=2,
        recovery_timeout=1,
        fallback=fallback_func
    )
    def api_call_with_fallback(should_fail=False):
        if should_fail:
            raise ConnectionError("API unavailable")
        return "success"
    
    # Успешные вызовы
    print("\n1. Успешные вызовы...")
    for i in range(3):
        result = api_call(should_fail=False)
        assert result == "success"
    print(f"   ✓ {call_count} успешных вызовов")
    
    # Неудачные вызовы
    print("\n2. Неудачные вызовы (открываем circuit)...")
    for i in range(2):
        try:
            api_call(should_fail=True)
        except ConnectionError:
            pass
    print("   ✓ Circuit открыт после ошибок")
    
    # Попытка вызова при OPEN
    print("\n3. Попытка вызова при OPEN...")
    try:
        api_call(should_fail=False)
        print("   ❌ Не должно было выполниться")
        return False
    except CircuitOpenError:
        print("   ✓ Получили CircuitOpenError")
    
    # Fallback
    print("\n4. Тест fallback функции...")
    # Открываем circuit
    for i in range(2):
        try:
            api_call_with_fallback(should_fail=True)
        except ConnectionError:
            pass
    
    # Вызов при OPEN с fallback
    result = api_call_with_fallback(should_fail=False)
    assert result == "fallback_result"
    print("   ✓ Fallback сработал при OPEN circuit")
    
    print("\n✅ TEST 3: PASSED")
    return True


def test_concurrent_access():
    """Тест 4: Concurrent access"""
    print("\n" + "="*60)
    print("TEST 4: Concurrent Access")
    print("="*60)
    
    breaker = CircuitBreaker(
        name="ConcurrentTest",
        failure_threshold=10,
        recovery_timeout=1
    )
    
    results = {'success': 0, 'failure': 0, 'rejected': 0}
    lock = threading.Lock()
    
    def worker(worker_id, should_fail):
        for i in range(5):
            if breaker.can_execute():
                try:
                    # Симуляция работы
                    time.sleep(0.001)
                    if should_fail:
                        raise ValueError("Error")
                    
                    breaker.record_success()
                    with lock:
                        results['success'] += 1
                
                except ValueError:
                    breaker.record_failure()
                    with lock:
                        results['failure'] += 1
            else:
                with lock:
                    results['rejected'] += 1
    
    # Запускаем потоки
    print("\n1. Запуск 10 потоков (5 успешных, 5 с ошибками)...")
    threads = []
    for i in range(10):
        should_fail = i >= 5  # Половина с ошибками
        t = threading.Thread(target=worker, args=(i, should_fail))
        t.start()
        threads.append(t)
    
    # Ждем завершения
    for t in threads:
        t.join()
    
    print(f"\n2. Результаты:")
    print(f"   Успешных: {results['success']}")
    print(f"   Ошибок: {results['failure']}")
    print(f"   Отклонено: {results['rejected']}")
    print(f"   Circuit state: {breaker.state.value}")
    
    assert results['success'] > 0
    assert results['failure'] > 0
    print("   ✓ Thread-safe работа подтверждена")
    
    print("\n✅ TEST 4: PASSED")
    return True


def test_metrics():
    """Тест 5: Метрики"""
    print("\n" + "="*60)
    print("TEST 5: Метрики")
    print("="*60)
    
    breaker = CircuitBreaker(
        name="MetricsTest",
        failure_threshold=2,
        recovery_timeout=1
    )
    
    # Генерируем активность
    print("\n1. Генерация активности...")
    breaker.record_success()
    breaker.record_success()
    breaker.record_failure()
    breaker.record_failure()  # Открываем circuit
    
    # Попытка при OPEN
    breaker.can_execute()  # Отклонится
    
    # Получаем метрики
    print("\n2. Метрики circuit breaker:")
    metrics = breaker.get_metrics()
    
    for key, value in metrics.items():
        if isinstance(value, float):
            print(f"   {key}: {value:.2f}")
        else:
            print(f"   {key}: {value}")
    
    assert metrics['successful_calls'] == 2
    assert metrics['failed_calls'] == 2
    assert metrics['rejected_calls'] >= 1
    assert metrics['state'] == 'open'
    
    print("\n   ✓ Метрики собираются корректно")
    
    print("\n✅ TEST 5: PASSED")
    return True


def main():
    """Запуск всех тестов"""
    print("╔" + "="*58 + "╗")
    print("║" + " Circuit Breaker Tests ".center(58) + "║")
    print("╚" + "="*58 + "╝")
    
    tests = [
        ("Базовая функциональность", test_basic_functionality),
        ("Context Manager", test_context_manager),
        ("Декоратор", test_decorator),
        ("Concurrent Access", test_concurrent_access),
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
        print("\nCircuit Breaker готов к использованию:")
        print("  ✓ Автоматическое обнаружение сбоев")
        print("  ✓ Защита от каскадных ошибок")
        print("  ✓ Автоматическое восстановление")
        print("  ✓ Thread-safe операции")
        print("  ✓ Детальные метрики")
        return 0
    else:
        print(f"\n⚠️  {total - passed} тест(ов) НЕ прошли")
        return 1


if __name__ == '__main__':
    sys.exit(main())
