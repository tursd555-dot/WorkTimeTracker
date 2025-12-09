"""
Интеграция Circuit Breaker в sheets_api.py

Добавляет:
1. Circuit Breaker для защиты от каскадных сбоев
2. Интеграцию с Health Checker
3. Graceful fallback в offline режим

ИНСТРУКЦИЯ ПО ПРИМЕНЕНИЮ:
1. Добавить в начало sheets_api.py после импортов
2. В методе _initialize() добавить инициализацию circuit breaker
3. Обернуть _request_with_retry в circuit breaker
4. Добавить методы для offline работы
"""

# ============================================================================
# ДОБАВИТЬ В НАЧАЛО sheets_api.py ПОСЛЕ ИМПОРТОВ
# ============================================================================

# Импорты для Circuit Breaker
from shared.resilience import get_circuit_breaker, CircuitOpenError, CircuitState

# ============================================================================
# ДОБАВИТЬ В МЕТОД _initialize() ПОСЛЕ self._quota_lock
# ============================================================================

def _initialize(self):
    # ... существующий код ...
    self._quota_lock = threading.Lock()
    
    # ДОБАВИТЬ: Circuit Breaker для защиты
    self.circuit_breaker = get_circuit_breaker(
        name="GoogleSheetsAPI",
        failure_threshold=3,      # 3 ошибки подряд
        recovery_timeout=300,     # 5 минут
        success_threshold=2       # 2 успеха для восстановления
    )
    logger.info("Circuit Breaker initialized for Sheets API")
    
    # ... остальной код ...

# ============================================================================
# ЗАМЕНИТЬ МЕТОД _request_with_retry
# ============================================================================

def _request_with_retry(self, func, *args, **kwargs):
    """
    Выполнить запрос с retry логикой и Circuit Breaker защитой
    
    Если Circuit Breaker открыт, запрос не выполняется и
    данные сохраняются для последующей синхронизации.
    """
    from config import API_MAX_RETRIES, API_DELAY_SECONDS, GOOGLE_API_LIMITS
    
    # Проверяем Circuit Breaker ПЕРЕД попыткой запроса
    if not self.circuit_breaker.can_execute():
        # Circuit OPEN - сервис недоступен
        logger.warning(
            f"Circuit breaker OPEN for Sheets API. "
            f"Will retry in {self.circuit_breaker._time_until_recovery():.0f}s"
        )
        
        # Возвращаем специальный результат для обработки в вызывающем коде
        raise CircuitOpenError(
            "GoogleSheetsAPI",
            datetime.now() + timedelta(seconds=self.circuit_breaker._time_until_recovery())
        )
    
    last_exc: Optional[Exception] = None
    
    for attempt in range(API_MAX_RETRIES):
        try:
            # Проверки квоты и rate limit
            if not self._check_quota(required=1):
                raise SheetsAPIError("Insufficient API quota", is_retryable=True)
            
            self._check_rate_limit(API_DELAY_SECONDS)
            
            name = getattr(func, "__name__", "<callable>")
            logger.debug(f"Attempt {attempt + 1}: {name}")
            
            # Выполняем запрос
            result = func(*args, **kwargs)
            
            # Успех! Обновляем квоту и circuit breaker
            with self._quota_lock:
                self._quota_info.remaining = max(0, self._quota_info.remaining - 1)
            
            self.circuit_breaker.record_success()
            
            return result
        
        except Exception as e:
            last_exc = e
            msg = str(e).lower()
            
            # Классификация ошибок
            is_format_error = any(x in msg for x in (
                "invalid value at 'data.values'", 
                "invalid value at 'values'",
                "invalid json payload",
                "bad request"
            ))
            
            # 429/5xx/сетевые — повторимые, ошибки формата — нет
            retryable = not is_format_error and any(x in msg for x in (
                "rate limit", "quota", "429", "timeout", "temporarily", 
                "unavailable", "socket", "503", "500", "502"
            ))
            
            # Ошибки формата не записываем в circuit breaker
            if is_format_error:
                logger.error(f"Invalid payload format for Sheets API: {e}")
                raise SheetsAPIError(
                    f"Invalid data format for Google Sheets API: {e}",
                    is_retryable=False,
                    details="Check that all values are properly formatted strings/numbers"
                )
            
            # Записываем ошибку в circuit breaker (только retryable ошибки)
            if retryable:
                self.circuit_breaker.record_failure(e)
                
                # Проверяем, не открылся ли circuit
                if self.circuit_breaker.state == CircuitState.OPEN:
                    logger.error(
                        f"Circuit breaker OPENED after {self.circuit_breaker.failure_count} failures"
                    )
                    # Отправляем алерт (опционально)
                    self._send_circuit_breaker_alert()
            
            # Последняя попытка или не повторяемая ошибка
            if attempt == API_MAX_RETRIES - 1 or not retryable:
                logger.error(f"Request failed after {API_MAX_RETRIES} attempts")
                if isinstance(e, SheetsAPIError):
                    raise
                raise SheetsAPIError(
                    f"API request failed: {e}",
                    is_retryable=retryable,
                    details=str(e)
                )
            
            # Exponential backoff с jitter
            base = max(1.0, float(API_DELAY_SECONDS))
            wait = base * (2 ** attempt)
            wait = wait + random.uniform(0, base)
            
            # Учитываем rate limit
            per_min = max(1, GOOGLE_API_LIMITS.get("max_requests_per_minute", 60))
            min_gap = 60.0 / per_min
            wait = max(wait, min_gap)
            
            logger.warning(f"Retry {attempt + 1}/{API_MAX_RETRIES} in {wait:.2f}s (error: {e})")
            time.sleep(wait)
    
    raise last_exc or Exception("Unknown request error")

# ============================================================================
# ДОБАВИТЬ НОВЫЕ МЕТОДЫ В КЛАСС SheetsAPI
# ============================================================================

def check_credentials(self) -> bool:
    """
    Легкая проверка валидности credentials (для Health Checks)
    
    Returns:
        True если credentials валидны
    """
    try:
        # Проверяем, что client инициализирован
        if not hasattr(self, 'client') or self.client is None:
            return False
        
        # Проверяем, что credentials файл существует
        if not hasattr(self, 'credentials_path') or not self.credentials_path.exists():
            return False
        
        return True
    
    except Exception as e:
        logger.debug(f"Credentials check failed: {e}")
        return False

def get_circuit_breaker_metrics(self) -> dict:
    """
    Получить метрики circuit breaker
    
    Returns:
        Словарь с метриками
    """
    if not hasattr(self, 'circuit_breaker'):
        return {'error': 'Circuit breaker not initialized'}
    
    return self.circuit_breaker.get_metrics()

def _send_circuit_breaker_alert(self):
    """Отправить алерт о том, что circuit breaker открылся"""
    try:
        from config import TELEGRAM_MONITORING_CHAT_ID
        from telegram_api import send_message
        
        message = (
            "⚠️ CIRCUIT BREAKER ALERT\n\n"
            "Service: Google Sheets API\n"
            "State: OPEN (service unavailable)\n"
            f"Failures: {self.circuit_breaker.failure_count}\n"
            f"Recovery timeout: {self.circuit_breaker.recovery_timeout}s\n"
            f"Time: {datetime.now().strftime('%H:%M:%S')}\n\n"
            "System switched to OFFLINE mode.\n"
            "Data will be queued for later sync."
        )
        
        send_message(TELEGRAM_MONITORING_CHAT_ID, message)
        logger.info("Circuit breaker alert sent")
    
    except Exception as e:
        logger.debug(f"Could not send circuit breaker alert: {e}")

def is_available(self) -> bool:
    """
    Проверить доступность API (для использования в коде)
    
    Returns:
        True если API доступен для запросов
    """
    if not hasattr(self, 'circuit_breaker'):
        return True  # Если circuit breaker не инициализирован
    
    return self.circuit_breaker.can_execute()

def get_status_message(self) -> str:
    """
    Получить человеко-читаемый статус API
    
    Returns:
        Строка со статусом
    """
    if not hasattr(self, 'circuit_breaker'):
        return "Circuit breaker not initialized"
    
    state = self.circuit_breaker.state
    
    if state == CircuitState.CLOSED:
        return "✅ Google Sheets API: Available"
    elif state == CircuitState.OPEN:
        time_until = self.circuit_breaker._time_until_recovery()
        return f"🔴 Google Sheets API: Unavailable (retry in {time_until:.0f}s)"
    elif state == CircuitState.HALF_OPEN:
        return "🟡 Google Sheets API: Testing recovery..."
    else:
        return "❓ Google Sheets API: Unknown state"

# ============================================================================
# ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ
# ============================================================================

"""
# Пример 1: Проверка доступности перед вызовом
api = get_sheets_api()

if api.is_available():
    # API доступен
    api.log_event(user_data, "LOGIN")
else:
    # API недоступен, работаем offline
    logger.warning("Sheets API unavailable, queuing for later")
    queue_for_later_sync(user_data, "LOGIN")

# Пример 2: Обработка CircuitOpenError
try:
    api.log_event(user_data, "LOGIN")
except CircuitOpenError as e:
    logger.warning(f"Circuit open: {e}")
    queue_for_later_sync(user_data, "LOGIN")

# Пример 3: Проверка статуса
status = api.get_status_message()
print(status)  # ✅ Google Sheets API: Available

# Пример 4: Метрики
metrics = api.get_circuit_breaker_metrics()
print(f"State: {metrics['state']}")
print(f"Failed calls: {metrics['failed_calls']}")
print(f"Rejected calls: {metrics['rejected_calls']}")
"""
