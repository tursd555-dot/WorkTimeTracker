"""
Circuit Breaker Pattern для защиты от каскадных сбоев

Защищает систему от перегрузки при недоступности внешних сервисов.

Состояния:
- CLOSED: Все работает нормально
- OPEN: Сервис недоступен, блокируем запросы
- HALF_OPEN: Проверяем восстановление

Использование:
    from shared.resilience.circuit_breaker import CircuitBreaker, circuit_breaker
    
    # Вариант 1: Декоратор
    @circuit_breaker(name="GoogleAPI", failure_threshold=3)
    def call_google_api():
        return api.request()
    
    # Вариант 2: Контекстный менеджер
    breaker = CircuitBreaker("GoogleAPI")
    with breaker:
        result = api.request()
    
    # Вариант 3: Ручная проверка
    if breaker.can_execute():
        try:
            result = api.request()
            breaker.record_success()
        except:
            breaker.record_failure()
            raise

Author: WorkTimeTracker Resilience Team
Date: 2025-12-04
"""

import logging
import threading
import time
from enum import Enum
from datetime import datetime, timedelta
from typing import Optional, Callable, Any
from functools import wraps

# Импорт для работы с московским временем
try:
    from shared.time_utils import format_time_moscow
except ImportError:
    # Фолбэк если модуль недоступен
    def format_time_moscow(dt, format_str='%H:%M:%S'):
        if dt is None:
            dt = datetime.now()
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        return dt.strftime(format_str)

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS
# ============================================================================

class CircuitState(Enum):
    """Состояния Circuit Breaker"""
    CLOSED = "closed"        # Все работает нормально
    OPEN = "open"            # Сервис недоступен, блокируем запросы
    HALF_OPEN = "half_open"  # Проверяем восстановление


# ============================================================================
# EXCEPTIONS
# ============================================================================

class CircuitBreakerError(Exception):
    """Исключение когда circuit открыт"""
    pass


class CircuitOpenError(CircuitBreakerError):
    """Circuit открыт, запросы блокируются"""
    def __init__(self, circuit_name: str, recovery_time: datetime):
        self.circuit_name = circuit_name
        self.recovery_time = recovery_time
        super().__init__(
            f"Circuit breaker [{circuit_name}] is OPEN. "
            f"Will retry at {recovery_time.strftime('%H:%M:%S')}"
        )


# ============================================================================
# CIRCUIT BREAKER
# ============================================================================

class CircuitBreaker:
    """
    Circuit Breaker для защиты от каскадных сбоев
    
    Автоматически обнаруживает недоступность сервиса и переключается
    в режим защиты, предотвращая бесконечные попытки подключения.
    
    Parameters:
        name: Имя circuit breaker (для логирования)
        failure_threshold: После скольких ошибок открыть circuit (default: 5)
        recovery_timeout: Сколько секунд ждать перед попыткой восстановления (default: 60)
        success_threshold: Сколько успехов нужно для закрытия (default: 2)
        expected_exception: Какие исключения считать ошибками (default: Exception)
    
    Example:
        >>> breaker = CircuitBreaker("GoogleAPI", failure_threshold=3, recovery_timeout=30)
        >>> 
        >>> if breaker.can_execute():
        ...     try:
        ...         result = api.call()
        ...         breaker.record_success()
        ...     except Exception:
        ...         breaker.record_failure()
        ...         raise
        ... else:
        ...     # Circuit OPEN, используем fallback
        ...     result = offline_mode()
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        success_threshold: int = 2,
        expected_exception: type = Exception
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self.expected_exception = expected_exception
        
        # Состояние
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.last_state_change: datetime = datetime.now()
        
        # Thread safety
        self.lock = threading.Lock()
        
        # Метрики
        self.metrics = {
            'total_calls': 0,
            'successful_calls': 0,
            'failed_calls': 0,
            'rejected_calls': 0,
            'state_changes': 0,
            'time_in_open': 0.0,  # секунды
            'time_in_half_open': 0.0,
            'time_in_closed': 0.0
        }
        
        logger.info(
            f"Circuit Breaker [{name}] initialized: "
            f"failure_threshold={failure_threshold}, "
            f"recovery_timeout={recovery_timeout}s, "
            f"success_threshold={success_threshold}"
        )
    
    def can_execute(self) -> bool:
        """
        Можно ли выполнить запрос?
        
        Returns:
            True если можно выполнить запрос, False если circuit открыт
        """
        with self.lock:
            self.metrics['total_calls'] += 1
            
            if self.state == CircuitState.CLOSED:
                return True
            
            elif self.state == CircuitState.OPEN:
                # Проверяем, не пора ли попробовать снова
                if self._should_attempt_reset():
                    self._transition_to_half_open()
                    return True
                else:
                    self.metrics['rejected_calls'] += 1
                    logger.debug(
                        f"Circuit Breaker [{self.name}] OPEN, rejecting call. "
                        f"Recovery in {self._time_until_recovery():.0f}s"
                    )
                    return False
            
            elif self.state == CircuitState.HALF_OPEN:
                # В HALF_OPEN пропускаем запросы для проверки
                return True
        
        return False
    
    def record_success(self):
        """Записать успешный вызов"""
        with self.lock:
            self.metrics['successful_calls'] += 1
            
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                logger.debug(
                    f"Circuit Breaker [{self.name}] HALF_OPEN success "
                    f"({self.success_count}/{self.success_threshold})"
                )
                
                if self.success_count >= self.success_threshold:
                    self._transition_to_closed()
            
            # В CLOSED сбрасываем счетчик ошибок при каждом успехе
            if self.state == CircuitState.CLOSED:
                if self.failure_count > 0:
                    logger.debug(
                        f"Circuit Breaker [{self.name}] resetting failure count "
                        f"({self.failure_count} → 0)"
                    )
                self.failure_count = 0
    
    def record_failure(self, exception: Optional[Exception] = None):
        """
        Записать неудачный вызов
        
        Args:
            exception: Исключение, вызвавшее ошибку (опционально)
        """
        with self.lock:
            self.metrics['failed_calls'] += 1
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            
            exc_info = f": {type(exception).__name__}" if exception else ""
            
            if self.state == CircuitState.CLOSED:
                logger.warning(
                    f"Circuit Breaker [{self.name}] CLOSED failure "
                    f"({self.failure_count}/{self.failure_threshold}){exc_info}"
                )
                
                if self.failure_count >= self.failure_threshold:
                    self._transition_to_open()
            
            elif self.state == CircuitState.HALF_OPEN:
                # При ошибке в HALF_OPEN сразу обратно в OPEN
                logger.warning(
                    f"Circuit Breaker [{self.name}] HALF_OPEN failure{exc_info}, "
                    f"returning to OPEN"
                )
                self._transition_to_open()
    
    def reset(self):
        """Принудительно закрыть circuit (для админа)"""
        with self.lock:
            logger.info(f"Circuit Breaker [{self.name}] manually reset")
            self._transition_to_closed()
            self.failure_count = 0
            self.success_count = 0
    
    def get_metrics(self) -> dict:
        """Получить метрики circuit breaker"""
        with self.lock:
            return {
                **self.metrics,
                'state': self.state.value,
                'failure_count': self.failure_count,
                'success_count': self.success_count,
                'time_until_recovery': self._time_until_recovery() if self.state == CircuitState.OPEN else 0,
                'last_failure': self.last_failure_time.isoformat() if self.last_failure_time else None,
                'time_in_current_state': (datetime.now() - self.last_state_change).total_seconds()
            }
    
    # ========================================================================
    # CONTEXT MANAGER SUPPORT
    # ========================================================================
    
    def __enter__(self):
        """Context manager entry"""
        if not self.can_execute():
            recovery_time = datetime.now() + timedelta(seconds=self._time_until_recovery())
            raise CircuitOpenError(self.name, recovery_time)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if exc_type is None:
            # Success
            self.record_success()
        elif isinstance(exc_val, self.expected_exception):
            # Expected failure
            self.record_failure(exc_val)
        # Else: unexpected exception, don't record
        
        return False  # Don't suppress exception
    
    # ========================================================================
    # PRIVATE METHODS
    # ========================================================================
    
    def _should_attempt_reset(self) -> bool:
        """Пора ли попробовать восстановление?"""
        if self.last_failure_time is None:
            return True
        
        elapsed = (datetime.now() - self.last_failure_time).total_seconds()
        return elapsed >= self.recovery_timeout
    
    def _time_until_recovery(self) -> float:
        """Сколько секунд до попытки восстановления"""
        if self.last_failure_time is None:
            return 0
        
        elapsed = (datetime.now() - self.last_failure_time).total_seconds()
        remaining = self.recovery_timeout - elapsed
        return max(0, remaining)
    
    def _transition_to_open(self):
        """Переход в OPEN (авария)"""
        self._update_time_metrics()
        self.state = CircuitState.OPEN
        self.success_count = 0
        self.last_state_change = datetime.now()
        self.metrics['state_changes'] += 1
        
        logger.error(
            f"⚠️  Circuit Breaker [{self.name}] transitioned to OPEN "
            f"after {self.failure_count} failures. "
            f"Will retry in {self.recovery_timeout}s"
        )
        
        # Отправить алерт (если настроено)
        self._send_alert("OPEN")
    
    def _transition_to_half_open(self):
        """Переход в HALF_OPEN (проверка восстановления)"""
        self._update_time_metrics()
        self.state = CircuitState.HALF_OPEN
        self.success_count = 0
        self.failure_count = 0
        self.last_state_change = datetime.now()
        self.metrics['state_changes'] += 1
        
        logger.info(
            f"Circuit Breaker [{self.name}] transitioned to HALF_OPEN, "
            f"attempting recovery"
        )
    
    def _transition_to_closed(self):
        """Переход в CLOSED (восстановление)"""
        self._update_time_metrics()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_state_change = datetime.now()
        self.metrics['state_changes'] += 1
        
        logger.info(
            f"✓ Circuit Breaker [{self.name}] transitioned to CLOSED, "
            f"service recovered"
        )
        
        # Отправить алерт о восстановлении
        self._send_alert("CLOSED")
    
    def _update_time_metrics(self):
        """Обновить метрики времени в состояниях"""
        elapsed = (datetime.now() - self.last_state_change).total_seconds()
        
        if self.state == CircuitState.OPEN:
            self.metrics['time_in_open'] += elapsed
        elif self.state == CircuitState.HALF_OPEN:
            self.metrics['time_in_half_open'] += elapsed
        elif self.state == CircuitState.CLOSED:
            self.metrics['time_in_closed'] += elapsed
    
    def _send_alert(self, new_state: str):
        """Отправить алерт о смене состояния"""
        try:
            from config import TELEGRAM_MONITORING_CHAT_ID
            from telegram_api import send_message
            
            if new_state == "OPEN":
                message = (
                    f"⚠️ CIRCUIT BREAKER ALERT\n\n"
                    f"Service: {self.name}\n"
                    f"State: OPEN (service unavailable)\n"
                    f"Failures: {self.failure_count}\n"
                    f"Recovery timeout: {self.recovery_timeout}s\n"
                    f"Time: {format_time_moscow(datetime.now(), '%H:%M:%S')}"
                )
            elif new_state == "CLOSED":
                message = (
                    f"✅ CIRCUIT BREAKER RECOVERED\n\n"
                    f"Service: {self.name}\n"
                    f"State: CLOSED (service restored)\n"
                    f"Time: {format_time_moscow(datetime.now(), '%H:%M:%S')}"
                )
            else:
                return
            
            send_message(TELEGRAM_MONITORING_CHAT_ID, message)
        
        except Exception as e:
            logger.debug(f"Could not send circuit breaker alert: {e}")


# ============================================================================
# GLOBAL REGISTRY
# ============================================================================

_circuit_breakers: dict[str, CircuitBreaker] = {}
_registry_lock = threading.Lock()


def get_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    success_threshold: int = 2
) -> CircuitBreaker:
    """
    Получить или создать circuit breaker
    
    Использует singleton pattern - один circuit breaker на имя.
    """
    global _circuit_breakers
    
    if name not in _circuit_breakers:
        with _registry_lock:
            if name not in _circuit_breakers:
                _circuit_breakers[name] = CircuitBreaker(
                    name=name,
                    failure_threshold=failure_threshold,
                    recovery_timeout=recovery_timeout,
                    success_threshold=success_threshold
                )
    
    return _circuit_breakers[name]


def get_all_circuit_breakers() -> dict[str, CircuitBreaker]:
    """Получить все зарегистрированные circuit breakers"""
    return _circuit_breakers.copy()


# ============================================================================
# DECORATOR
# ============================================================================

def circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    success_threshold: int = 2,
    fallback: Optional[Callable] = None
):
    """
    Декоратор для защиты функции circuit breaker
    
    Args:
        name: Имя circuit breaker
        failure_threshold: После скольких ошибок открыть
        recovery_timeout: Сколько секунд ждать
        success_threshold: Сколько успехов для закрытия
        fallback: Функция fallback при открытом circuit
    
    Example:
        @circuit_breaker("GoogleAPI", failure_threshold=3, recovery_timeout=30)
        def call_google_api(data):
            return api.append(data)
        
        # С fallback
        def offline_mode(data):
            return queue_for_later(data)
        
        @circuit_breaker("GoogleAPI", fallback=offline_mode)
        def call_google_api(data):
            return api.append(data)
    """
    def decorator(func: Callable) -> Callable:
        breaker = get_circuit_breaker(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            success_threshold=success_threshold
        )
        
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            if not breaker.can_execute():
                # Circuit OPEN
                if fallback:
                    logger.warning(
                        f"Circuit breaker [{name}] OPEN, using fallback"
                    )
                    return fallback(*args, **kwargs)
                else:
                    raise CircuitOpenError(
                        name,
                        datetime.now() + timedelta(seconds=breaker._time_until_recovery())
                    )
            
            try:
                result = func(*args, **kwargs)
                breaker.record_success()
                return result
            
            except Exception as e:
                breaker.record_failure(e)
                raise
        
        return wrapper
    return decorator
