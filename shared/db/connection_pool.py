"""
Thread-safe Connection Pool для SQLite

Оптимизация для 200 пользователей:
- Максимум 10 соединений вместо 200
- Переиспользование соединений
- Автоматический WAL режим
- Thread-safe операции

Author: WorkTimeTracker Performance Team
Date: 2025-12-04
"""

import sqlite3
import threading
import time
import logging
from queue import Queue, Empty, Full
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Generator

logger = logging.getLogger(__name__)


class ConnectionPool:
    """
    Thread-safe пул соединений для SQLite
    
    Преимущества:
    - Переиспользование соединений (меньше overhead)
    - Ограничение max connections (контроль ресурсов)
    - Автоматическая настройка WAL режима
    - Thread-safe (можно использовать из любого потока)
    
    Пример использования:
        pool = ConnectionPool('local_backup.db', pool_size=10)
        
        with pool.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM logs WHERE email = ?", (email,))
            results = cursor.fetchall()
    """
    
    def __init__(
        self,
        db_path: str,
        pool_size: int = 10,
        timeout: float = 5.0,
        check_same_thread: bool = False
    ):
        """
        Инициализация пула соединений
        
        Args:
            db_path: Путь к SQLite БД
            pool_size: Размер пула (для 200 users рекомендуется 10)
            timeout: Таймаут при получении соединения (секунды)
            check_same_thread: Проверка потока (False для multi-threading)
        """
        self.db_path = Path(db_path)
        self.pool_size = pool_size
        self.timeout = timeout
        self.check_same_thread = check_same_thread
        
        # Очередь доступных соединений
        self.pool = Queue(maxsize=pool_size)
        
        # Блокировка для инициализации
        self.init_lock = threading.Lock()
        
        # Счетчики для мониторинга
        self.stats = {
            'created': 0,
            'reused': 0,
            'wait_time_total': 0,
            'wait_count': 0
        }
        self.stats_lock = threading.Lock()
        
        # Инициализация пула
        self._initialize_pool()
        
        logger.info(f"ConnectionPool initialized: {pool_size} connections for {db_path}")
    
    def _initialize_pool(self):
        """Создает начальные соединения в пуле"""
        for i in range(self.pool_size):
            try:
                conn = self._create_connection()
                self.pool.put(conn, block=False)
                with self.stats_lock:
                    self.stats['created'] += 1
            except Exception as e:
                logger.error(f"Failed to create connection #{i}: {e}")
                raise
    
    def _create_connection(self) -> sqlite3.Connection:
        """
        Создает новое соединение с оптимальными настройками
        
        Returns:
            Настроенное SQLite соединение
        """
        if not self.db_path.exists():
            logger.warning(f"Database file does not exist, will be created: {self.db_path}")
        
        conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=self.check_same_thread,
            timeout=self.timeout
        )
        
        # Настройки для производительности и WAL режима
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-64000")       # 64MB cache
        conn.execute("PRAGMA temp_store=MEMORY")       # Temp tables in memory
        conn.execute("PRAGMA busy_timeout=5000")       # 5s wait on lock
        conn.execute("PRAGMA mmap_size=268435456")     # 256MB mmap
        
        # Row factory для dict-like доступа
        conn.row_factory = sqlite3.Row
        
        return conn
    
    @contextmanager
    def get_connection(self, timeout: Optional[float] = None) -> Generator[sqlite3.Connection, None, None]:
        """
        Получить соединение из пула (context manager)
        
        Args:
            timeout: Таймаут ожидания (по умолчанию используется self.timeout)
        
        Yields:
            SQLite соединение
        
        Example:
            with pool.get_connection() as conn:
                cursor = conn.execute("SELECT * FROM logs")
                for row in cursor:
                    print(row['email'])
        """
        timeout = timeout or self.timeout
        conn = None
        start_time = time.time()
        
        try:
            # Пытаемся получить соединение из пула
            try:
                conn = self.pool.get(timeout=timeout)
                wait_time = time.time() - start_time
                
                with self.stats_lock:
                    self.stats['reused'] += 1
                    self.stats['wait_time_total'] += wait_time
                    self.stats['wait_count'] += 1
                
                if wait_time > 1.0:
                    logger.warning(f"Long wait for connection: {wait_time:.2f}s")
                
            except Empty:
                raise TimeoutError(
                    f"Could not get connection from pool within {timeout}s. "
                    f"Pool size: {self.pool_size}, consider increasing."
                )
            
            # Проверяем, что соединение живое
            try:
                conn.execute("SELECT 1")
            except sqlite3.Error:
                logger.warning("Stale connection detected, creating new one")
                conn.close()
                conn = self._create_connection()
                with self.stats_lock:
                    self.stats['created'] += 1
            
            yield conn
            
        except Exception as e:
            logger.error(f"Error in connection context: {e}")
            raise
        
        finally:
            # Возвращаем соединение в пул
            if conn is not None:
                try:
                    # Rollback незакоммиченных транзакций
                    conn.rollback()
                    # Возвращаем в пул
                    self.pool.put(conn, block=False)
                except Full:
                    # Пул полный (не должно происходить), закрываем соединение
                    logger.warning("Pool is full, closing connection")
                    conn.close()
                except Exception as e:
                    logger.error(f"Error returning connection to pool: {e}")
                    try:
                        conn.close()
                    except:
                        pass
    
    def execute_query(self, sql: str, params: tuple = (), fetch: str = 'all') -> list:
        """
        Удобная обертка для выполнения запросов
        
        Args:
            sql: SQL запрос
            params: Параметры запроса
            fetch: 'all', 'one', или 'none'
        
        Returns:
            Результаты запроса
        
        Example:
            results = pool.execute_query(
                "SELECT * FROM logs WHERE email = ?",
                ('user@example.com',)
            )
        """
        with self.get_connection() as conn:
            cursor = conn.execute(sql, params)
            
            if fetch == 'all':
                return cursor.fetchall()
            elif fetch == 'one':
                return cursor.fetchone()
            elif fetch == 'none':
                conn.commit()
                return []
            else:
                raise ValueError(f"Invalid fetch mode: {fetch}")
    
    def execute_many(self, sql: str, params_list: list) -> int:
        """
        Batch операция для множественных INSERT/UPDATE
        
        Args:
            sql: SQL запрос
            params_list: Список кортежей параметров
        
        Returns:
            Количество затронутых строк
        
        Example:
            pool.execute_many(
                "INSERT INTO logs (email, action) VALUES (?, ?)",
                [('user1@ex.com', 'LOGIN'), ('user2@ex.com', 'LOGOUT')]
            )
        """
        with self.get_connection() as conn:
            cursor = conn.executemany(sql, params_list)
            conn.commit()
            return cursor.rowcount
    
    def get_stats(self) -> dict:
        """
        Получить статистику использования пула
        
        Returns:
            Словарь со статистикой
        """
        with self.stats_lock:
            stats = self.stats.copy()
        
        # Вычисляем среднее время ожидания
        if stats['wait_count'] > 0:
            stats['avg_wait_time'] = stats['wait_time_total'] / stats['wait_count']
        else:
            stats['avg_wait_time'] = 0
        
        # Процент переиспользования
        total_requests = stats['created'] + stats['reused']
        if total_requests > 0:
            stats['reuse_rate'] = stats['reused'] / total_requests * 100
        else:
            stats['reuse_rate'] = 0
        
        stats['pool_size'] = self.pool_size
        stats['available'] = self.pool.qsize()
        
        return stats
    
    def close_all(self):
        """
        Закрыть все соединения в пуле
        
        Вызывать при выключении приложения
        """
        logger.info("Closing all connections in pool...")
        closed = 0
        
        while not self.pool.empty():
            try:
                conn = self.pool.get_nowait()
                conn.close()
                closed += 1
            except Empty:
                break
            except Exception as e:
                logger.error(f"Error closing connection: {e}")
        
        logger.info(f"Closed {closed} connections")
    
    def __enter__(self):
        """Context manager support"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup"""
        self.close_all()
    
    def __del__(self):
        """Destructor"""
        try:
            self.close_all()
        except:
            pass


# ============================================================================
# Singleton instance (глобальный пул)
# ============================================================================

_global_pool: Optional[ConnectionPool] = None
_global_pool_lock = threading.Lock()


def get_pool(db_path: str = 'local_backup.db', pool_size: int = 10) -> ConnectionPool:
    """
    Получить глобальный пул соединений (singleton)
    
    Args:
        db_path: Путь к БД
        pool_size: Размер пула (только при первом вызове)
    
    Returns:
        Глобальный ConnectionPool
    
    Example:
        # В любом месте приложения
        from shared.db.connection_pool import get_pool
        
        pool = get_pool()
        with pool.get_connection() as conn:
            conn.execute("INSERT INTO logs ...")
    """
    global _global_pool
    
    if _global_pool is None:
        with _global_pool_lock:
            if _global_pool is None:
                _global_pool = ConnectionPool(db_path, pool_size)
                logger.info(f"Created global connection pool: {pool_size} connections")
    
    return _global_pool


def close_global_pool():
    """
    Закрыть глобальный пул соединений
    
    Вызывать при выключении приложения
    """
    global _global_pool
    
    if _global_pool is not None:
        _global_pool.close_all()
        _global_pool = None


# ============================================================================
# Удобные функции для быстрого использования
# ============================================================================

def query(sql: str, params: tuple = (), db_path: str = 'local_backup.db') -> list:
    """
    Быстрое выполнение SELECT запроса
    
    Example:
        from shared.db.connection_pool import query
        results = query("SELECT * FROM logs WHERE email = ?", ('user@ex.com',))
    """
    pool = get_pool(db_path)
    return pool.execute_query(sql, params, fetch='all')


def query_one(sql: str, params: tuple = (), db_path: str = 'local_backup.db') -> Optional[sqlite3.Row]:
    """
    Быстрое выполнение SELECT для одной строки
    
    Example:
        from shared.db.connection_pool import query_one
        user = query_one("SELECT * FROM users WHERE email = ?", ('user@ex.com',))
    """
    pool = get_pool(db_path)
    return pool.execute_query(sql, params, fetch='one')


def execute(sql: str, params: tuple = (), db_path: str = 'local_backup.db'):
    """
    Быстрое выполнение INSERT/UPDATE/DELETE
    
    Example:
        from shared.db.connection_pool import execute
        execute("INSERT INTO logs (email, action) VALUES (?, ?)", ('user@ex.com', 'LOGIN'))
    """
    pool = get_pool(db_path)
    return pool.execute_query(sql, params, fetch='none')
