"""
Модуль Health Checks для WorkTimeTracker

Компоненты:
- HealthChecker: система мониторинга здоровья
- Предустановленные checks: database, sheets_api, telegram_api, и т.д.
"""

from .health_checker import (
    HealthChecker,
    HealthStatus,
    ComponentHealth,
    get_health_checker,
    stop_global_health_checker
)

from .checks import (
    check_database_health,
    check_sheets_api_health,
    check_telegram_api_health,
    check_internet_health,
    check_disk_space_health,
    check_memory_health,
    check_sync_queue_health,
    register_all_checks
)

__all__ = [
    # Health Checker
    'HealthChecker',
    'HealthStatus',
    'ComponentHealth',
    'get_health_checker',
    'stop_global_health_checker',
    
    # Checks
    'check_database_health',
    'check_sheets_api_health',
    'check_telegram_api_health',
    'check_internet_health',
    'check_disk_space_health',
    'check_memory_health',
    'check_sync_queue_health',
    'register_all_checks',
]
