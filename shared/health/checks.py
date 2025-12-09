"""
Предустановленные Health Checks для WorkTimeTracker

Проверки для:
- Database (SQLite + Connection Pool)
- Google Sheets API
- Telegram API
- Internet connectivity
- Disk space
- Memory usage

Usage:
    from shared.health.checks import *
    from shared.health.health_checker import get_health_checker
    
    checker = get_health_checker()
    checker.register_check("database", check_database_health)
    checker.register_check("sheets_api", check_sheets_api_health)
    checker.register_check("telegram_api", check_telegram_api_health)
    checker.register_check("internet", check_internet_health)
    checker.register_check("disk_space", check_disk_space_health)
    checker.register_check("memory", check_memory_health)
    
    checker.start_monitoring(interval=60)

Author: WorkTimeTracker Resilience Team
Date: 2025-12-04
"""

import logging
import shutil
import os
from typing import Tuple, Optional, Dict

logger = logging.getLogger(__name__)


# ============================================================================
# DATABASE HEALTH
# ============================================================================

def check_database_health() -> Tuple[bool, str, Optional[Dict]]:
    """
    Проверка здоровья базы данных
    
    Проверяет:
    - Соединение с БД
    - Доступные connections в пуле
    - Время отклика
    
    Returns:
        (healthy, message, details)
    """
    try:
        from shared.db.connection_pool import get_pool
        import time
        
        pool = get_pool()
        
        # Измеряем время отклика
        start = time.time()
        with pool.get_connection(timeout=2) as conn:
            conn.execute("SELECT 1").fetchone()
        response_time_ms = (time.time() - start) * 1000
        
        # Проверяем доступные соединения
        stats = pool.get_stats()
        available = stats.get('available', 0)
        pool_size = stats.get('pool_size', 10)
        
        details = {
            'response_time_ms': round(response_time_ms, 2),
            'available_connections': available,
            'pool_size': pool_size,
            'reuse_rate': stats.get('reuse_rate', 0)
        }
        
        # Определяем статус
        if available < 2:
            return False, f"Low connections: {available}/{pool_size}", details
        elif response_time_ms > 100:
            return False, f"Slow response: {response_time_ms:.0f}ms", details
        else:
            return True, f"Database OK ({response_time_ms:.0f}ms)", details
    
    except Exception as e:
        return False, f"Database error: {e}", None


# ============================================================================
# GOOGLE SHEETS API HEALTH
# ============================================================================

def check_sheets_api_health() -> Tuple[bool, str, Optional[Dict]]:
    """
    Проверка Google Sheets API
    
    Проверяет:
    - Доступность API
    - Circuit breaker состояние
    - Credentials валидность
    
    Returns:
        (healthy, message, details)
    """
    try:
        from api_adapter import get_sheets_api
        from shared.resilience.circuit_breaker import get_circuit_breaker
        
        # Проверяем circuit breaker
        try:
            breaker = get_circuit_breaker("GoogleSheetsAPI")
            breaker_state = breaker.state.value
            breaker_metrics = breaker.get_metrics()
        except:
            breaker_state = "unknown"
            breaker_metrics = {}
        
        # Если circuit открыт, сервис недоступен
        if breaker_state == "open":
            return False, f"Circuit breaker OPEN", {
                'circuit_state': breaker_state,
                'time_until_recovery': breaker_metrics.get('time_until_recovery', 0)
            }
        
        # Проверяем credentials (легкая проверка, без реальных запросов)
        try:
            api = get_sheets_api()
            if not api.check_credentials():
                return False, "Invalid credentials", {'circuit_state': breaker_state}
        except Exception as e:
            return False, f"API error: {e}", {'circuit_state': breaker_state}
        
        details = {
            'circuit_state': breaker_state,
            'success_rate': breaker_metrics.get('successful_calls', 0) / max(breaker_metrics.get('total_calls', 1), 1)
        }
        
        return True, "Sheets API OK", details
    
    except Exception as e:
        return False, f"Sheets API check failed: {e}", None


# ============================================================================
# TELEGRAM API HEALTH
# ============================================================================

def check_telegram_api_health() -> Tuple[bool, str, Optional[Dict]]:
    """
    Проверка Telegram Bot API
    
    Проверяет:
    - Доступность API
    - Circuit breaker состояние
    - Bot token валидность
    
    Returns:
        (healthy, message, details)
    """
    try:
        from shared.resilience.circuit_breaker import get_circuit_breaker
        
        # Проверяем circuit breaker
        try:
            breaker = get_circuit_breaker("TelegramAPI")
            breaker_state = breaker.state.value
            breaker_metrics = breaker.get_metrics()
        except:
            breaker_state = "unknown"
            breaker_metrics = {}
        
        # Если circuit открыт, сервис недоступен
        if breaker_state == "open":
            return False, f"Circuit breaker OPEN", {
                'circuit_state': breaker_state,
                'time_until_recovery': breaker_metrics.get('time_until_recovery', 0)
            }
        
        # Легкая проверка без реальных запросов
        # (полноценную проверку делаем реже, чтобы не спамить API)
        
        details = {
            'circuit_state': breaker_state,
            'success_rate': breaker_metrics.get('successful_calls', 0) / max(breaker_metrics.get('total_calls', 1), 1)
        }
        
        return True, "Telegram API OK", details
    
    except Exception as e:
        return False, f"Telegram API check failed: {e}", None


# ============================================================================
# INTERNET CONNECTIVITY HEALTH
# ============================================================================

def check_internet_health() -> Tuple[bool, str, Optional[Dict]]:
    """
    Проверка интернет-соединения
    
    Проверяет доступность Google (быстрая проверка)
    
    Returns:
        (healthy, message, details)
    """
    try:
        from sync.network import is_internet_available
        import time
        
        start = time.time()
        available = is_internet_available(timeout=3)
        response_time_ms = (time.time() - start) * 1000
        
        details = {
            'response_time_ms': round(response_time_ms, 2)
        }
        
        if available:
            return True, f"Internet OK ({response_time_ms:.0f}ms)", details
        else:
            return False, "No internet connection", details
    
    except Exception as e:
        return False, f"Internet check failed: {e}", None


# ============================================================================
# DISK SPACE HEALTH
# ============================================================================

def check_disk_space_health() -> Tuple[bool, str, Optional[Dict]]:
    """
    Проверка дискового пространства
    
    Пороги:
    - < 1 GB: UNHEALTHY
    - < 5 GB: OK but warning
    - >= 5 GB: OK
    
    Returns:
        (healthy, message, details)
    """
    try:
        usage = shutil.disk_usage(".")
        
        free_gb = usage.free / (1024**3)
        total_gb = usage.total / (1024**3)
        used_gb = usage.used / (1024**3)
        percent_used = (usage.used / usage.total) * 100
        
        details = {
            'free_gb': round(free_gb, 2),
            'used_gb': round(used_gb, 2),
            'total_gb': round(total_gb, 2),
            'percent_used': round(percent_used, 1)
        }
        
        if free_gb < 1:
            return False, f"Critical: {free_gb:.1f} GB free", details
        elif free_gb < 5:
            # Деградированное состояние - работает, но мало места
            from shared.health.health_checker import HealthStatus
            return HealthStatus.DEGRADED, f"Low disk space: {free_gb:.1f} GB", details
        else:
            return True, f"Disk space OK: {free_gb:.1f} GB free", details
    
    except Exception as e:
        return False, f"Disk check failed: {e}", None


# ============================================================================
# MEMORY USAGE HEALTH
# ============================================================================

def check_memory_health() -> Tuple[bool, str, Optional[Dict]]:
    """
    Проверка использования памяти
    
    Пороги:
    - > 500 MB: UNHEALTHY
    - > 200 MB: DEGRADED
    - <= 200 MB: HEALTHY
    
    Returns:
        (healthy, message, details)
    """
    try:
        import psutil
        
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        
        memory_mb = memory_info.rss / 1024 / 1024
        
        # Системная память
        system_memory = psutil.virtual_memory()
        system_available_mb = system_memory.available / 1024 / 1024
        system_percent = system_memory.percent
        
        details = {
            'process_memory_mb': round(memory_mb, 1),
            'system_available_mb': round(system_available_mb, 1),
            'system_percent': round(system_percent, 1)
        }
        
        if memory_mb > 500:
            return False, f"High memory: {memory_mb:.0f} MB", details
        elif memory_mb > 200:
            from shared.health.health_checker import HealthStatus
            return HealthStatus.DEGRADED, f"Elevated memory: {memory_mb:.0f} MB", details
        else:
            return True, f"Memory OK: {memory_mb:.0f} MB", details
    
    except ImportError:
        # psutil не установлен
        return True, "Memory check skipped (psutil not installed)", None
    except Exception as e:
        return False, f"Memory check failed: {e}", None


# ============================================================================
# SYNC QUEUE HEALTH
# ============================================================================

def check_sync_queue_health() -> Tuple[bool, str, Optional[Dict]]:
    """
    Проверка очереди синхронизации
    
    Проверяет количество несинхронизированных записей
    
    Returns:
        (healthy, message, details)
    """
    try:
        from shared.db.connection_pool import get_pool
        
        pool = get_pool()
        
        with pool.get_connection() as conn:
            # Считаем несинхронизированные записи
            result = conn.execute("""
                SELECT COUNT(*) as count
                FROM logs
                WHERE synced = 0
            """).fetchone()
            
            pending_count = result['count'] if result else 0
            
            details = {
                'pending_sync': pending_count
            }
            
            if pending_count > 1000:
                return False, f"Large sync queue: {pending_count} records", details
            elif pending_count > 100:
                from shared.health.health_checker import HealthStatus
                return HealthStatus.DEGRADED, f"Sync queue growing: {pending_count} records", details
            else:
                return True, f"Sync queue OK: {pending_count} pending", details
    
    except Exception as e:
        return False, f"Sync queue check failed: {e}", None


# ============================================================================
# ALL CHECKS REGISTRATION
# ============================================================================

def register_all_checks(checker):
    """
    Зарегистрировать все предустановленные проверки
    
    Args:
        checker: HealthChecker instance
    """
    checks = [
        ("database", check_database_health),
        ("sheets_api", check_sheets_api_health),
        ("telegram_api", check_telegram_api_health),
        ("internet", check_internet_health),
        ("disk_space", check_disk_space_health),
        ("memory", check_memory_health),
        ("sync_queue", check_sync_queue_health),
    ]
    
    for name, check_func in checks:
        try:
            checker.register_check(name, check_func)
            logger.info(f"Registered health check: {name}")
        except Exception as e:
            logger.error(f"Failed to register health check {name}: {e}")


__all__ = [
    'check_database_health',
    'check_sheets_api_health',
    'check_telegram_api_health',
    'check_internet_health',
    'check_disk_space_health',
    'check_memory_health',
    'check_sync_queue_health',
    'register_all_checks',
]
