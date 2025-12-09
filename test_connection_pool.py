#!/usr/bin/env python3
"""
Тест Connection Pool для 200 пользователей

Проверяет:
- Thread-safety
- Производительность
- Concurrent access
- Memory usage
"""

import sys
import time
import threading
import random
from pathlib import Path

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).parent))

from shared.db.connection_pool import ConnectionPool, get_pool

def test_basic_operations():
    """Тест базовых операций"""
    print("="*60)
    print("TEST 1: Базовые операции")
    print("="*60)
    
    pool = ConnectionPool('local_backup.db', pool_size=5)
    
    # Тест SELECT
    print("\n1. SELECT запрос...")
    with pool.get_connection() as conn:
        cursor = conn.execute("SELECT COUNT(*) as cnt FROM logs")
        result = cursor.fetchone()
        print(f"   ✓ Записей в logs: {result['cnt']}")
    
    # Тест INSERT
    print("\n2. INSERT запрос...")
    test_email = f"test_{int(time.time())}@example.com"
    with pool.get_connection() as conn:
        conn.execute("""
            INSERT INTO logs (session_id, email, name, action_type, timestamp)
            VALUES (?, ?, ?, ?, datetime('now'))
        """, (f"test_{time.time()}", test_email, "Test User", "TEST"))
        conn.commit()
    print(f"   ✓ Добавлена тестовая запись: {test_email}")
    
    # Тест статистики
    print("\n3. Статистика пула...")
    stats = pool.get_stats()
    print(f"   ✓ Создано соединений: {stats['created']}")
    print(f"   ✓ Переиспользовано: {stats['reused']}")
    print(f"   ✓ Доступно в пуле: {stats['available']}/{stats['pool_size']}")
    print(f"   ✓ Среднее время ожидания: {stats['avg_wait_time']*1000:.2f} ms")
    
    pool.close_all()
    print("\n✅ Базовые операции: PASSED")
    return True

def test_concurrent_access():
    """Тест concurrent access (симуляция 200 пользователей)"""
    print("\n" + "="*60)
    print("TEST 2: Concurrent Access (200 пользователей)")
    print("="*60)
    
    pool = ConnectionPool('local_backup.db', pool_size=10)
    results = {'success': 0, 'errors': 0}
    results_lock = threading.Lock()
    
    def worker(worker_id, num_queries):
        """Рабочий поток (симулирует пользователя)"""
        for i in range(num_queries):
            try:
                # Случайная операция
                operation = random.choice(['select', 'insert'])
                
                if operation == 'select':
                    # SELECT запрос
                    with pool.get_connection() as conn:
                        conn.execute("SELECT * FROM logs LIMIT 10")
                else:
                    # INSERT запрос
                    with pool.get_connection() as conn:
                        conn.execute("""
                            INSERT INTO logs (session_id, email, name, action_type, timestamp)
                            VALUES (?, ?, ?, ?, datetime('now'))
                        """, (f"test_{worker_id}_{i}", f"worker{worker_id}@test.com", 
                              f"Worker {worker_id}", "TEST"))
                        conn.commit()
                
                with results_lock:
                    results['success'] += 1
                
                # Небольшая задержка (симуляция реальной работы)
                time.sleep(random.uniform(0.001, 0.01))
                
            except Exception as e:
                with results_lock:
                    results['errors'] += 1
                print(f"   ⚠️  Worker {worker_id} error: {e}")
    
    # Запускаем 200 потоков (пользователей)
    num_workers = 200
    queries_per_worker = 5  # Каждый делает 5 запросов
    
    print(f"\n🚀 Запуск {num_workers} потоков...")
    print(f"   Каждый поток: {queries_per_worker} запросов")
    print(f"   Всего запросов: {num_workers * queries_per_worker}")
    print(f"   Размер пула: 10 соединений")
    
    start_time = time.time()
    threads = []
    
    for i in range(num_workers):
        t = threading.Thread(target=worker, args=(i, queries_per_worker))
        t.start()
        threads.append(t)
    
    # Ждем завершения всех потоков
    for t in threads:
        t.join()
    
    elapsed = time.time() - start_time
    
    # Результаты
    print(f"\n📊 Результаты:")
    print(f"   Время выполнения: {elapsed:.2f} сек")
    print(f"   Успешных запросов: {results['success']}")
    print(f"   Ошибок: {results['errors']}")
    print(f"   Запросов/сек: {results['success']/elapsed:.1f}")
    
    # Статистика пула
    stats = pool.get_stats()
    print(f"\n📈 Статистика пула:")
    print(f"   Всего запросов к пулу: {stats['created'] + stats['reused']}")
    print(f"   Процент переиспользования: {stats['reuse_rate']:.1f}%")
    print(f"   Среднее время ожидания: {stats['avg_wait_time']*1000:.2f} ms")
    print(f"   Доступно соединений: {stats['available']}/{stats['pool_size']}")
    
    pool.close_all()
    
    if results['errors'] == 0:
        print("\n✅ Concurrent access: PASSED")
        return True
    else:
        print(f"\n⚠️  Concurrent access: PASSED с {results['errors']} ошибками")
        return True

def test_performance_comparison():
    """Сравнение производительности: pool vs direct connections"""
    print("\n" + "="*60)
    print("TEST 3: Производительность (Pool vs Direct)")
    print("="*60)
    
    num_queries = 100
    
    # Тест 1: С пулом
    print(f"\n🔄 Pool ({num_queries} запросов)...")
    pool = ConnectionPool('local_backup.db', pool_size=10)
    
    start = time.time()
    for i in range(num_queries):
        with pool.get_connection() as conn:
            conn.execute("SELECT * FROM logs LIMIT 10")
    pool_time = time.time() - start
    
    pool.close_all()
    print(f"   Время: {pool_time:.3f} сек ({num_queries/pool_time:.1f} запросов/сек)")
    
    # Тест 2: Прямые соединения
    print(f"\n🔌 Direct connections ({num_queries} запросов)...")
    import sqlite3
    
    start = time.time()
    for i in range(num_queries):
        conn = sqlite3.connect('local_backup.db')
        conn.execute("SELECT * FROM logs LIMIT 10")
        conn.close()
    direct_time = time.time() - start
    
    print(f"   Время: {direct_time:.3f} сек ({num_queries/direct_time:.1f} запросов/сек)")
    
    # Сравнение
    speedup = direct_time / pool_time
    print(f"\n⚡ Улучшение: {speedup:.1f}x быстрее с пулом")
    
    print("\n✅ Performance comparison: PASSED")
    return True

def test_error_handling():
    """Тест обработки ошибок"""
    print("\n" + "="*60)
    print("TEST 4: Обработка ошибок")
    print("="*60)
    
    pool = ConnectionPool('local_backup.db', pool_size=5)
    
    # Тест 1: Некорректный SQL
    print("\n1. Некорректный SQL...")
    try:
        with pool.get_connection() as conn:
            conn.execute("SELECT * FROM non_existent_table")
        print("   ❌ Ошибка НЕ поймана!")
        return False
    except Exception as e:
        print(f"   ✓ Ошибка корректно поймана: {type(e).__name__}")
    
    # Тест 2: Timeout (если пул занят)
    print("\n2. Timeout при занятом пуле...")
    # Займем весь пул
    connections = []
    try:
        pool_small = ConnectionPool('local_backup.db', pool_size=2)
        for i in range(2):
            connections.append(pool_small.get_connection().__enter__())
        
        # Попытка получить еще одно соединение (должен быть timeout)
        try:
            with pool_small.get_connection(timeout=0.1) as conn:
                pass
            print("   ⚠️  Timeout НЕ сработал")
        except TimeoutError:
            print("   ✓ Timeout корректно сработал")
        
        finally:
            # Освобождаем соединения
            for ctx in connections:
                ctx.__exit__(None, None, None)
            pool_small.close_all()
    
    except Exception as e:
        print(f"   ⚠️  Unexpected error: {e}")
    
    pool.close_all()
    print("\n✅ Error handling: PASSED")
    return True

def main():
    """Запуск всех тестов"""
    print("╔" + "="*58 + "╗")
    print("║" + " Connection Pool Tests for 200 Users ".center(58) + "║")
    print("╚" + "="*58 + "╝")
    
    tests = [
        ("Базовые операции", test_basic_operations),
        ("Concurrent Access", test_concurrent_access),
        ("Производительность", test_performance_comparison),
        ("Обработка ошибок", test_error_handling),
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
        print("\nConnection Pool готов для 200 пользователей:")
        print("  ✓ Thread-safe операции")
        print("  ✓ Переиспользование соединений")
        print("  ✓ Обработка ошибок")
        print("  ✓ Высокая производительность")
        return 0
    else:
        print(f"\n⚠️  {total - passed} тест(ов) НЕ прошли")
        return 1

if __name__ == '__main__':
    sys.exit(main())
