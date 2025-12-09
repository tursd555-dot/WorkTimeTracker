"""
Кэширование данных для Admin App
Уменьшает количество запросов к Google Sheets API
"""
import logging
import time
from typing import Dict, Any, Optional, Callable
from functools import wraps
from threading import Lock

logger = logging.getLogger(__name__)


class DataCache:
    """
    Кэш данных с TTL (Time To Live)
    
    Использование:
    cache = DataCache(ttl=300)  # 5 минут
    
    @cache.cached('users')
    def get_users():
        return api.get_users()
    """
    
    def __init__(self, ttl: int = 300):
        """
        Args:
            ttl: Время жизни кэша в секундах (по умолчанию 5 минут)
        """
        self.ttl = ttl
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()
    
    def get(self, key: str) -> Optional[Any]:
        """Получить значение из кэша"""
        with self._lock:
            if key not in self._cache:
                return None
            
            entry = self._cache[key]
            
            # Проверяем TTL
            if time.time() - entry['timestamp'] > self.ttl:
                logger.debug(f"Cache expired for key: {key}")
                del self._cache[key]
                return None
            
            logger.debug(f"Cache hit for key: {key}")
            return entry['value']
    
    def set(self, key: str, value: Any):
        """Сохранить значение в кэш"""
        with self._lock:
            self._cache[key] = {
                'value': value,
                'timestamp': time.time()
            }
            logger.debug(f"Cache set for key: {key}")
    
    def invalidate(self, key: str):
        """Инвалидировать кэш для ключа"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"Cache invalidated for key: {key}")
    
    def clear(self):
        """Очистить весь кэш"""
        with self._lock:
            self._cache.clear()
            logger.debug("Cache cleared")
    
    def cached(self, key: str):
        """
        Декоратор для кэширования результата функции
        
        @cache.cached('users')
        def get_users():
            return api.get_users()
        """
        def decorator(func: Callable):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Проверяем кэш
                cached_value = self.get(key)
                if cached_value is not None:
                    return cached_value
                
                # Вызываем функцию
                logger.debug(f"Cache miss for key: {key}, calling function")
                result = func(*args, **kwargs)
                
                # Сохраняем в кэш
                self.set(key, result)
                
                return result
            
            # Добавляем методы для управления кэшем
            wrapper.invalidate_cache = lambda: self.invalidate(key)
            wrapper.clear_cache = lambda: self.clear()
            
            return wrapper
        return decorator
    
    def stats(self) -> Dict[str, Any]:
        """Статистика кэша"""
        with self._lock:
            return {
                'entries': len(self._cache),
                'keys': list(self._cache.keys()),
                'ttl': self.ttl
            }


# Глобальный кэш для Admin App
# TTL = 5 минут (данные редко меняются)
admin_cache = DataCache(ttl=300)


# Примеры использования:
"""
from admin_app.data_cache import admin_cache

# Вариант 1: Декоратор
@admin_cache.cached('users')
def load_users():
    return api.get_users()

# Вариант 2: Вручную
def load_groups():
    cached = admin_cache.get('groups')
    if cached:
        return cached
    
    groups = api.get_groups()
    admin_cache.set('groups', groups)
    return groups

# Инвалидация кэша при изменении
def save_user(user):
    api.save_user(user)
    admin_cache.invalidate('users')  # Сбросить кэш

# Статистика
print(admin_cache.stats())
# {'entries': 2, 'keys': ['users', 'groups'], 'ttl': 300}
"""


class RateLimiter:
    """
    Ограничитель частоты запросов
    
    Использование:
    limiter = RateLimiter(max_calls=10, period=60)  # 10 запросов в минуту
    
    @limiter.limit
    def api_call():
        return api.get_data()
    """
    
    def __init__(self, max_calls: int = 50, period: int = 60):
        """
        Args:
            max_calls: Максимум вызовов
            period: Период в секундах
        """
        self.max_calls = max_calls
        self.period = period
        self._calls = []
        self._lock = Lock()
    
    def _cleanup_old_calls(self):
        """Удаляет старые вызовы"""
        now = time.time()
        cutoff = now - self.period
        self._calls = [t for t in self._calls if t > cutoff]
    
    def can_call(self) -> bool:
        """Проверяет можно ли сделать вызов"""
        with self._lock:
            self._cleanup_old_calls()
            return len(self._calls) < self.max_calls
    
    def wait_if_needed(self):
        """Ждет если нужно"""
        with self._lock:
            self._cleanup_old_calls()
            
            if len(self._calls) >= self.max_calls:
                # Ждем до истечения самого старого вызова
                oldest = min(self._calls)
                wait_time = oldest + self.period - time.time()
                
                if wait_time > 0:
                    logger.warning(f"Rate limit reached, waiting {wait_time:.1f}s")
                    time.sleep(wait_time)
                    self._cleanup_old_calls()
    
    def record_call(self):
        """Записывает вызов"""
        with self._lock:
            self._calls.append(time.time())
    
    def limit(self, func: Callable):
        """
        Декоратор для ограничения частоты вызовов
        
        @limiter.limit
        def api_call():
            return api.get_data()
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            self.wait_if_needed()
            result = func(*args, **kwargs)
            self.record_call()
            return result
        return wrapper


# Глобальный rate limiter
# 50 запросов в минуту (безопасно для Google API)
api_limiter = RateLimiter(max_calls=50, period=60)


if __name__ == "__main__":
    print("Data Cache & Rate Limiter")
    print()
    print("Cache example:")
    print("  @admin_cache.cached('users')")
    print("  def get_users(): ...")
    print()
    print("Rate limiter example:")
    print("  @api_limiter.limit")
    print("  def api_call(): ...")
