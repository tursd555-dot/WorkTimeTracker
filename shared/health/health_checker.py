"""
Health Check System для WorkTimeTracker

Система проверки здоровья критичных компонентов:
- Database connectivity
- Google Sheets API
- Telegram API
- Internet connectivity
- Disk space
- Memory usage

Автоматический мониторинг с алертами при проблемах.

Usage:
    from shared.health.health_checker import HealthChecker
    from shared.health.checks import *
    
    # Создаем checker
    checker = HealthChecker()
    
    # Регистрируем проверки
    checker.register_check("database", check_database_health)
    checker.register_check("sheets_api", check_sheets_api_health)
    
    # Запускаем мониторинг (каждую минуту)
    checker.start_monitoring(interval=60)
    
    # Проверяем статус
    status = checker.get_overall_status()
    if not status.healthy:
        alert_admin(status.message)

Author: WorkTimeTracker Resilience Team
Date: 2025-12-04
"""

import logging
import threading
import time
from typing import Dict, Callable, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

# Импорт для работы с московским временем
try:
    from shared.time_utils import format_datetime_moscow
except ImportError:
    # Фолбэк если модуль недоступен
    def format_datetime_moscow(dt, format_str='%Y-%m-%d %H:%M:%S'):
        if dt is None:
            dt = datetime.now()
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        return dt.strftime(format_str)

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS
# ============================================================================

class HealthStatus(Enum):
    """Статусы здоровья компонента"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"  # Работает, но с проблемами
    UNHEALTHY = "unhealthy"


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class ComponentHealth:
    """Результат проверки здоровья компонента"""
    component: str
    status: HealthStatus
    message: str
    last_check: datetime
    check_duration_ms: float
    consecutive_failures: int = 0
    details: Dict = field(default_factory=dict)
    
    @property
    def healthy(self) -> bool:
        """Компонент здоров?"""
        return self.status == HealthStatus.HEALTHY


# ============================================================================
# HEALTH CHECKER
# ============================================================================

class HealthChecker:
    """
    Система проверки здоровья критичных компонентов
    
    Автоматически мониторит состояние компонентов и отправляет
    алерты при обнаружении проблем.
    
    Parameters:
        failure_threshold: После скольких неудач подряд отправить алерт (default: 3)
        alert_callback: Функция для отправки алертов (default: None)
    
    Example:
        >>> checker = HealthChecker(failure_threshold=3)
        >>> checker.register_check("database", check_db_health)
        >>> checker.start_monitoring(interval=60)
        >>> 
        >>> # Позже проверим статус
        >>> status = checker.get_overall_status()
        >>> if not status.healthy:
        ...     print(f"System unhealthy: {status.message}")
    """
    
    def __init__(
        self,
        failure_threshold: int = 3,
        alert_callback: Optional[Callable] = None
    ):
        self.failure_threshold = failure_threshold
        self.alert_callback = alert_callback
        
        # Зарегистрированные проверки
        self.checks: Dict[str, Callable] = {}
        
        # Текущие статусы
        self.statuses: Dict[str, ComponentHealth] = {}
        
        # Мониторинг
        self.monitoring_thread: Optional[threading.Thread] = None
        self.running = False
        
        # Thread safety
        self.lock = threading.Lock()
        
        # Метрики
        self.metrics = {
            'total_checks': 0,
            'healthy_checks': 0,
            'unhealthy_checks': 0,
            'alerts_sent': 0,
            'last_check_time': None
        }
        
        logger.info(
            f"HealthChecker initialized: failure_threshold={failure_threshold}"
        )
    
    def register_check(self, name: str, check_func: Callable[[], Tuple[bool, str, Optional[Dict]]]):
        """
        Зарегистрировать health check
        
        Args:
            name: Имя компонента
            check_func: Функция проверки, должна возвращать:
                - bool: True = healthy, False = unhealthy
                - str: сообщение о статусе
                - dict (optional): дополнительные детали
        
        Example:
            def check_database():
                try:
                    conn.execute("SELECT 1")
                    return True, "Database OK", {"connections": 10}
                except:
                    return False, "Database error", None
            
            checker.register_check("database", check_database)
        """
        with self.lock:
            self.checks[name] = check_func
            logger.info(f"Registered health check: {name}")
    
    def unregister_check(self, name: str):
        """Удалить health check"""
        with self.lock:
            if name in self.checks:
                del self.checks[name]
                if name in self.statuses:
                    del self.statuses[name]
                logger.info(f"Unregistered health check: {name}")
    
    def check_all(self) -> Dict[str, ComponentHealth]:
        """
        Проверить все компоненты
        
        Returns:
            Словарь {component_name: ComponentHealth}
        """
        results = {}
        
        for name, check_func in self.checks.items():
            result = self._check_component(name, check_func)
            results[name] = result
        
        with self.lock:
            self.statuses = results
            self.metrics['last_check_time'] = datetime.now()
            self.metrics['total_checks'] += len(results)
            self.metrics['healthy_checks'] += sum(1 for r in results.values() if r.healthy)
            self.metrics['unhealthy_checks'] += sum(1 for r in results.values() if not r.healthy)
        
        return results
    
    def check_component(self, name: str) -> Optional[ComponentHealth]:
        """
        Проверить конкретный компонент
        
        Args:
            name: Имя компонента
        
        Returns:
            ComponentHealth или None если компонент не зарегистрирован
        """
        check_func = self.checks.get(name)
        if not check_func:
            logger.warning(f"Health check not found: {name}")
            return None
        
        result = self._check_component(name, check_func)
        
        # Обновляем статус
        with self.lock:
            self.statuses[name] = result
        
        return result
    
    def get_status(self, name: str) -> Optional[ComponentHealth]:
        """Получить последний статус компонента"""
        return self.statuses.get(name)
    
    def get_overall_status(self) -> ComponentHealth:
        """
        Получить общий статус системы
        
        Returns:
            ComponentHealth с агрегированным статусом
        """
        if not self.statuses:
            return ComponentHealth(
                component="system",
                status=HealthStatus.UNHEALTHY,
                message="No health checks registered",
                last_check=datetime.now(),
                check_duration_ms=0
            )
        
        # Подсчитываем статусы
        healthy = [s for s in self.statuses.values() if s.status == HealthStatus.HEALTHY]
        degraded = [s for s in self.statuses.values() if s.status == HealthStatus.DEGRADED]
        unhealthy = [s for s in self.statuses.values() if s.status == HealthStatus.UNHEALTHY]
        
        # Определяем общий статус
        if unhealthy:
            status = HealthStatus.UNHEALTHY
            message = f"Unhealthy: {', '.join(s.component for s in unhealthy)}"
        elif degraded:
            status = HealthStatus.DEGRADED
            message = f"Degraded: {', '.join(s.component for s in degraded)}"
        else:
            status = HealthStatus.HEALTHY
            message = "All systems operational"
        
        return ComponentHealth(
            component="system",
            status=status,
            message=message,
            last_check=datetime.now(),
            check_duration_ms=0,
            details={
                'healthy': len(healthy),
                'degraded': len(degraded),
                'unhealthy': len(unhealthy),
                'total': len(self.statuses)
            }
        )
    
    def start_monitoring(self, interval: int = 60):
        """
        Запустить периодический мониторинг
        
        Args:
            interval: Интервал проверки в секундах (default: 60)
        """
        if self.running:
            logger.warning("Health monitoring already running")
            return
        
        self.running = True
        
        def monitor_loop():
            logger.info(f"Health monitoring started (interval={interval}s)")
            
            while self.running:
                try:
                    # Проверяем все компоненты
                    self.check_all()
                    
                    # Спим до следующей проверки
                    time.sleep(interval)
                
                except Exception as e:
                    logger.error(f"Health monitoring error: {e}", exc_info=True)
                    time.sleep(interval)  # Продолжаем даже при ошибке
        
        self.monitoring_thread = threading.Thread(
            target=monitor_loop,
            name="HealthMonitor",
            daemon=True
        )
        self.monitoring_thread.start()
    
    def stop_monitoring(self):
        """Остановить мониторинг"""
        if not self.running:
            return
        
        logger.info("Stopping health monitoring...")
        self.running = False
        
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        
        logger.info("Health monitoring stopped")
    
    def get_metrics(self) -> Dict:
        """Получить метрики health checker"""
        with self.lock:
            return {
                **self.metrics,
                'registered_checks': len(self.checks),
                'monitoring_active': self.running
            }
    
    # ========================================================================
    # PRIVATE METHODS
    # ========================================================================
    
    def _check_component(self, name: str, check_func: Callable) -> ComponentHealth:
        """Выполнить проверку компонента"""
        start = time.time()
        
        try:
            # Вызываем проверку
            result = check_func()
            
            # Парсим результат (поддерживаем 2 и 3 элемента)
            if len(result) == 2:
                healthy, message = result
                details = None
            elif len(result) == 3:
                healthy, message, details = result
            else:
                raise ValueError(f"Invalid check result format: {result}")
            
            duration_ms = (time.time() - start) * 1000
            
            # Определяем статус
            if isinstance(healthy, bool):
                status = HealthStatus.HEALTHY if healthy else HealthStatus.UNHEALTHY
            else:
                # Поддержка явного указания статуса
                status = healthy
            
            # Получаем предыдущий статус
            prev = self.statuses.get(name)
            
            if status != HealthStatus.HEALTHY:
                # Увеличиваем счетчик неудач
                consecutive_failures = (prev.consecutive_failures + 1) if prev else 1
                
                # Отправляем алерт если превышен порог
                if consecutive_failures >= self.failure_threshold:
                    self._send_alert(name, message, consecutive_failures)
            else:
                # При успехе сбрасываем счетчик
                consecutive_failures = 0
            
            health = ComponentHealth(
                component=name,
                status=status,
                message=message,
                last_check=datetime.now(),
                check_duration_ms=duration_ms,
                consecutive_failures=consecutive_failures,
                details=details or {}
            )
            
            # Логируем
            if status == HealthStatus.HEALTHY:
                logger.debug(f"Health check [{name}]: OK ({duration_ms:.0f}ms)")
            elif status == HealthStatus.DEGRADED:
                logger.warning(f"Health check [{name}]: DEGRADED - {message}")
            else:
                logger.error(f"Health check [{name}]: UNHEALTHY - {message}")
            
            return health
        
        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            logger.error(f"Health check [{name}] failed: {e}", exc_info=True)
            
            prev = self.statuses.get(name)
            consecutive_failures = (prev.consecutive_failures + 1) if prev else 1
            
            # Отправляем алерт если превышен порог
            if consecutive_failures >= self.failure_threshold:
                self._send_alert(name, f"Check failed: {e}", consecutive_failures)
            
            return ComponentHealth(
                component=name,
                status=HealthStatus.UNHEALTHY,
                message=f"Check failed: {e}",
                last_check=datetime.now(),
                check_duration_ms=duration_ms,
                consecutive_failures=consecutive_failures
            )
    
    def _send_alert(self, component: str, message: str, failures: int):
        """Отправить алерт о проблеме"""
        alert_msg = (
            f"⚠️ HEALTH ALERT ⚠️\n\n"
            f"Component: {component}\n"
            f"Status: UNHEALTHY\n"
            f"Message: {message}\n"
            f"Consecutive failures: {failures}\n"
            f"Time: {format_datetime_moscow(datetime.now(), '%Y-%m-%d %H:%M:%S')}"
        )
        
        # Используем callback если есть
        if self.alert_callback:
            try:
                self.alert_callback(alert_msg)
                with self.lock:
                    self.metrics['alerts_sent'] += 1
                logger.info(f"Alert sent for {component}")
            except Exception as e:
                logger.error(f"Failed to send alert: {e}")
        else:
            # Пытаемся отправить через Telegram
            try:
                from config import TELEGRAM_MONITORING_CHAT_ID
                from telegram_api import send_message
                send_message(TELEGRAM_MONITORING_CHAT_ID, alert_msg)
                with self.lock:
                    self.metrics['alerts_sent'] += 1
                logger.info(f"Alert sent for {component}")
            except Exception as e:
                logger.debug(f"Could not send alert via Telegram: {e}")


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

_global_health_checker: Optional[HealthChecker] = None
_checker_lock = threading.Lock()


def get_health_checker(
    failure_threshold: int = 3,
    alert_callback: Optional[Callable] = None
) -> HealthChecker:
    """
    Получить глобальный health checker (singleton)
    
    Args:
        failure_threshold: После скольких неудач отправить алерт
        alert_callback: Функция для алертов
    
    Returns:
        Глобальный экземпляр HealthChecker
    """
    global _global_health_checker
    
    if _global_health_checker is None:
        with _checker_lock:
            if _global_health_checker is None:
                _global_health_checker = HealthChecker(
                    failure_threshold=failure_threshold,
                    alert_callback=alert_callback
                )
    
    return _global_health_checker


def stop_global_health_checker():
    """Остановить глобальный health checker"""
    global _global_health_checker
    
    if _global_health_checker:
        _global_health_checker.stop_monitoring()
        _global_health_checker = None
