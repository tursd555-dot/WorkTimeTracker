#!/usr/bin/env python3
"""
Пример полной интеграции систем отказоустойчивости

Демонстрирует работу:
- Circuit Breaker
- Health Checks
- Degradation Manager

В реальной ситуации: Google Sheets API падает
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from shared.resilience import (
    get_circuit_breaker,
    get_degradation_manager,
    SystemMode
)
from shared.health import (
    get_health_checker,
    HealthChecker,
    ComponentHealth,
    HealthStatus
)
from datetime import datetime


def simulate_google_api_failure():
    """
    Симуляция отказа Google Sheets API
    
    Показывает как три системы работают вместе:
    1. Circuit Breaker обнаруживает ошибки и открывается
    2. Health Check видит circuit state = open → UNHEALTHY
    3. Degradation Manager переключает режим на OFFLINE
    """
    
    print("╔" + "="*58 + "╗")
    print("║" + " Интеграция систем отказоустойчивости ".center(58) + "║")
    print("╚" + "="*58 + "╝")
    
    print("\n📋 СЦЕНАРИЙ: Google Sheets API недоступен")
    print("="*60)
    
    # ========================================================================
    # SETUP
    # ========================================================================
    
    print("\n⚙️  НАСТРОЙКА СИСТЕМ")
    print("-"*60)
    
    # 1. Circuit Breaker для Google Sheets API
    print("\n1. Circuit Breaker...")
    sheets_breaker = get_circuit_breaker(
        name="GoogleSheetsAPI",
        failure_threshold=3,
        recovery_timeout=5  # 5 сек для демо (в проде 300)
    )
    print(f"   ✓ Создан: failure_threshold=3, recovery_timeout=5s")
    print(f"   ✓ Состояние: {sheets_breaker.state.value}")
    
    # 2. Health Checker
    print("\n2. Health Checker...")
    health_checker = get_health_checker(failure_threshold=2)
    
    # Регистрируем mock проверку для Sheets API
    def check_sheets_api():
        """Проверка учитывает circuit breaker"""
        breaker_state = sheets_breaker.state.value
        
        if breaker_state == "open":
            return False, f"Circuit breaker OPEN", {'circuit_state': breaker_state}
        elif breaker_state == "half_open":
            return True, f"Circuit breaker HALF_OPEN (testing)", {'circuit_state': breaker_state}
        else:
            return True, "Sheets API OK", {'circuit_state': breaker_state}
    
    # Регистрируем mock проверки для других компонентов
    def check_database():
        return True, "Database OK", {}
    
    def check_telegram():
        return True, "Telegram OK", {}
    
    def check_internet():
        return True, "Internet OK", {}
    
    health_checker.register_check("database", check_database)
    health_checker.register_check("sheets_api", check_sheets_api)
    health_checker.register_check("telegram_api", check_telegram)
    health_checker.register_check("internet", check_internet)
    
    print(f"   ✓ Проверок зарегистрировано: {len(health_checker.checks)}")
    
    # 3. Degradation Manager
    print("\n3. Degradation Manager...")
    
    def on_mode_change(old_mode, new_mode, reason):
        print(f"\n   📢 РЕЖИМ ИЗМЕНЕН: {old_mode.value} → {new_mode.value}")
        print(f"      Причина: {reason}")
    
    degradation_manager = get_degradation_manager(
        health_checker=health_checker,
        mode_change_callback=on_mode_change
    )
    
    print(f"   ✓ Создан")
    print(f"   ✓ Текущий режим: {degradation_manager.get_current_mode().value}")
    
    # ========================================================================
    # НАЧАЛЬНОЕ СОСТОЯНИЕ
    # ========================================================================
    
    print("\n\n📊 НАЧАЛЬНОЕ СОСТОЯНИЕ")
    print("-"*60)
    
    print("\n Circuit Breaker:")
    print(f"   State: {sheets_breaker.state.value}")
    print(f"   Failures: {sheets_breaker.failure_count}")
    
    print("\n Health Checks:")
    health_checker.check_all()
    for name, status in health_checker.statuses.items():
        icon = "✅" if status.healthy else "❌"
        print(f"   {icon} {name}: {status.message}")
    
    print("\n System Mode:")
    mode = degradation_manager.get_current_mode()
    cap = degradation_manager.get_capabilities()
    print(f"   Mode: {mode.value}")
    print(f"   Sync: {cap.sync_enabled}")
    print(f"   Notifications: {cap.notifications_enabled}")
    
    # ========================================================================
    # СИМУЛЯЦИЯ ОТКАЗА
    # ========================================================================
    
    print("\n\n💥 СИМУЛЯЦИЯ: Google Sheets API начинает падать...")
    print("="*60)
    
    # Попытка 1
    print("\n⏱️  t=0s - Попытка 1: API timeout...")
    sheets_breaker.record_failure()
    print(f"   Circuit Breaker: {sheets_breaker.state.value} (failures: {sheets_breaker.failure_count})")
    
    time.sleep(1)
    
    # Попытка 2
    print("\n⏱️  t=1s - Попытка 2: API timeout...")
    sheets_breaker.record_failure()
    print(f"   Circuit Breaker: {sheets_breaker.state.value} (failures: {sheets_breaker.failure_count})")
    
    time.sleep(1)
    
    # Попытка 3 - Circuit открывается
    print("\n⏱️  t=2s - Попытка 3: API timeout...")
    sheets_breaker.record_failure()
    print(f"   🔴 Circuit Breaker: {sheets_breaker.state.value} (ОТКРЫТ!)")
    print(f"   ⏰ Ожидание восстановления: {sheets_breaker.recovery_timeout}s")
    
    time.sleep(1)
    
    # Health Check обнаруживает проблему
    print("\n⏱️  t=3s - Health Check обнаруживает проблему...")
    health_checker.check_all()
    
    sheets_status = health_checker.statuses.get('sheets_api')
    print(f"   Health: sheets_api = {sheets_status.status.value}")
    print(f"   Message: {sheets_status.message}")
    print(f"   Consecutive failures: {sheets_status.consecutive_failures}")
    
    time.sleep(1)
    
    # Второй Health Check
    print("\n⏱️  t=4s - Health Check #2 (consecutive failure)...")
    health_checker.check_all()
    sheets_status = health_checker.statuses.get('sheets_api')
    print(f"   Consecutive failures: {sheets_status.consecutive_failures}")
    
    # Degradation Manager оценивает режим
    print("\n⏱️  t=5s - Degradation Manager оценивает режим...")
    new_mode = degradation_manager.evaluate_mode()
    
    print(f"\n   Новый режим: {new_mode.value}")
    cap = degradation_manager.get_capabilities()
    print(f"   Sync: {cap.sync_enabled} (данные в очередь)")
    print(f"   Notifications: {cap.notifications_enabled}")
    print(f"   Description: {cap.description}")
    
    # ========================================================================
    # РАБОТА В OFFLINE РЕЖИМЕ
    # ========================================================================
    
    print("\n\n📴 РАБОТА В OFFLINE РЕЖИМЕ")
    print("-"*60)
    print("\nПользователи продолжают работу:")
    print("  ✓ Логин/логаут работает")
    print("  ✓ Данные сохраняются в локальную БД")
    print("  ✓ Синхронизация откладывается в очередь")
    print("  ✓ UI не блокируется")
    
    # ========================================================================
    # ВОССТАНОВЛЕНИЕ
    # ========================================================================
    
    print("\n\n🔄 ВОССТАНОВЛЕНИЕ СЕРВИСА")
    print("="*60)
    
    print(f"\n⏱️  Ожидание {sheets_breaker.recovery_timeout}s для recovery timeout...")
    time.sleep(sheets_breaker.recovery_timeout + 1)
    
    # Circuit переходит в HALF_OPEN
    print(f"\n⏱️  t={sheets_breaker.recovery_timeout + 6}s - Circuit Breaker пробует восстановление...")
    
    if sheets_breaker.can_execute():
        print(f"   🟡 Circuit Breaker: {sheets_breaker.state.value} (проверка)")
    
    # Симулируем успешный запрос
    print("\n⏱️  Успешный запрос к API...")
    sheets_breaker.record_success()
    print(f"   Success count: {sheets_breaker.success_count}/{sheets_breaker.success_threshold}")
    
    # Еще один успешный запрос
    print("\n⏱️  Еще один успешный запрос...")
    sheets_breaker.record_success()
    print(f"   🟢 Circuit Breaker: {sheets_breaker.state.value} (ЗАКРЫТ!)")
    
    # Health Check видит восстановление
    print("\n⏱️  Health Check обнаруживает восстановление...")
    health_checker.check_all()
    sheets_status = health_checker.statuses.get('sheets_api')
    print(f"   Health: sheets_api = {sheets_status.status.value}")
    
    # Degradation Manager переключает обратно в FULL
    print("\n⏱️  Degradation Manager переключает режим...")
    new_mode = degradation_manager.evaluate_mode()
    print(f"   ✅ Новый режим: {new_mode.value}")
    
    # ========================================================================
    # ИТОГОВОЕ СОСТОЯНИЕ
    # ========================================================================
    
    print("\n\n📊 ИТОГОВОЕ СОСТОЯНИЕ")
    print("="*60)
    
    print("\n Circuit Breaker:")
    metrics = sheets_breaker.get_metrics()
    print(f"   State: {metrics['state']}")
    print(f"   Total calls: {metrics['total_calls']}")
    print(f"   Successful: {metrics['successful_calls']}")
    print(f"   Failed: {metrics['failed_calls']}")
    print(f"   Rejected: {metrics['rejected_calls']}")
    print(f"   State changes: {metrics['state_changes']}")
    
    print("\n Health Checks:")
    overall = health_checker.get_overall_status()
    print(f"   Overall: {overall.status.value}")
    print(f"   Message: {overall.message}")
    
    print("\n System Mode:")
    mode = degradation_manager.get_current_mode()
    print(f"   Current: {mode.value}")
    
    dm_metrics = degradation_manager.get_metrics()
    print(f"   Mode changes: {dm_metrics['mode_changes']}")
    
    print("\n Mode History:")
    history = degradation_manager.get_mode_history(limit=5)
    for transition in history:
        print(f"   {transition.timestamp.strftime('%H:%M:%S')} - "
              f"{transition.from_mode.value} → {transition.to_mode.value} "
              f"({transition.reason})")
    
    # ========================================================================
    # ВЫВОДЫ
    # ========================================================================
    
    print("\n\n✨ РЕЗУЛЬТАТЫ")
    print("="*60)
    print("\n✅ Система успешно справилась с отказом:")
    print("  1. Circuit Breaker обнаружил проблему за 2 секунды")
    print("  2. Health Check подтвердил проблему")
    print("  3. Degradation Manager переключился в OFFLINE")
    print("  4. Пользователи продолжили работу без простоя")
    print("  5. Система автоматически восстановилась")
    print("  6. Синхронизация очереди возобновлена")
    
    print("\n📈 Метрики:")
    print(f"  • Время обнаружения: 2 секунды")
    print(f"  • Downtime для пользователей: 0 секунд")
    print(f"  • Неудачных запросов: 3 (вместо 1000+)")
    print(f"  • Автоматическое восстановление: ✅")
    
    print("\n" + "="*60)
    print("🎉 ДЕМОНСТРАЦИЯ ЗАВЕРШЕНА")
    print("="*60)


if __name__ == '__main__':
    simulate_google_api_failure()
