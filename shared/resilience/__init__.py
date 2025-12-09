"""
Модуль отказоустойчивости WorkTimeTracker

Компоненты:
- CircuitBreaker: защита от каскадных сбоев
- DegradationManager: автоматическое переключение режимов работы
- (Future) RateLimiter: ограничение частоты запросов
- (Future) Retry: умные повторные попытки
"""

from .circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerError,
    CircuitOpenError,
    get_circuit_breaker,
    get_all_circuit_breakers,
    circuit_breaker
)

from .degradation_manager import (
    DegradationManager,
    SystemMode,
    ModeTransition,
    ModeCapabilities,
    get_degradation_manager,
    stop_global_degradation_manager
)

__all__ = [
    # Circuit Breaker
    'CircuitBreaker',
    'CircuitState',
    'CircuitBreakerError',
    'CircuitOpenError',
    'get_circuit_breaker',
    'get_all_circuit_breakers',
    'circuit_breaker',
    
    # Degradation Manager
    'DegradationManager',
    'SystemMode',
    'ModeTransition',
    'ModeCapabilities',
    'get_degradation_manager',
    'stop_global_degradation_manager',
]
