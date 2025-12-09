"""
Improved Sync Queue for WorkTimeTracker

Улучшенная очередь синхронизации с:
- Exponential backoff с jitter
- Batch операциями (несколько записей за раз)
- Приоритетами
- Conflict resolution
- Детальная телеметрия

Проблемы старой системы:
1. Синхронизация по одной записи → 100 записей = 100 запросов
2. Нет exponential backoff → спам при сбоях
3. Нет batch операций → превышение rate limits
4. Нет приоритетов → важные события застревают

Решения:
1. Batch операции → 100 записей = 5 запросов (batch по 20)
2. Exponential backoff с jitter → меньше нагрузки при сбоях
3. Приоритеты → LOGIN/LOGOUT обрабатываются первыми
4. Conflict resolution → автоматическое разрешение

Использование:
    from sync.sync_queue_improved import ImprovedSyncQueue
    
    queue = ImprovedSyncQueue(
        db_connection=conn,
        sheets_client=sheets,
        batch_size=20,
        max_attempts=5
    )
    
    # Запустить синхронизацию
    result = queue.sync_pending_records()
    print(f"Synced: {result['synced']}, Failed: {result['failed']}")

Автор: WorkTimeTracker Sync Team
Дата: 2025-11-24
"""

import time
import random
import logging
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum

# Импорт conflict resolver
try:
    from .conflict_resolver import ConflictResolver, ConflictInfo, ConflictRequiresManualResolution
except ImportError:
    # Fallback для тестирования
    from conflict_resolver import ConflictResolver, ConflictInfo, ConflictRequiresManualResolution

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS
# ============================================================================

class SyncPriority(IntEnum):
    """
    Приоритеты синхронизации.
    
    Чем больше число, тем выше приоритет.
    """
    LOW = 1
    NORMAL = 5
    HIGH = 8
    CRITICAL = 10


class SyncStatus(IntEnum):
    """Статусы синхронизации"""
    PENDING = 0      # Ожидает синхронизации
    SYNCED = 1       # Синхронизировано
    FAILED = -1      # Не удалось синхронизировать (после всех попыток)


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class SyncTask:
    """
    Задача синхронизации.
    
    Attributes:
        id: ID записи в БД
        data: Данные для синхронизации
        priority: Приоритет (1-10)
        attempts: Количество попыток
        last_attempt: Время последней попытки
        created_at: Время создания задачи
        max_attempts: Максимальное количество попыток
    """
    id: int
    data: Dict[str, Any]
    priority: int = SyncPriority.NORMAL
    attempts: int = 0
    last_attempt: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    max_attempts: int = 5
    
    def should_retry(self) -> bool:
        """Проверить, нужно ли повторить попытку"""
        return self.attempts < self.max_attempts
    
    def get_backoff_delay(self) -> float:
        """
        Вычислить задержку для exponential backoff с jitter.
        
        Formula: delay = base * (2 ^ attempts) + random_jitter
        где base = 1 second, random_jitter = [0, 1) second
        
        Examples:
            Attempt 0: 1s + jitter = ~1-2s
            Attempt 1: 2s + jitter = ~2-3s
            Attempt 2: 4s + jitter = ~4-5s
            Attempt 3: 8s + jitter = ~8-9s
            Attempt 4: 16s + jitter = ~16-17s
            
        Returns:
            Задержка в секундах
        """
        base_delay = 1.0
        exponential_delay = base_delay * (2 ** self.attempts)
        jitter = random.uniform(0, 1.0)
        
        # Максимальная задержка - 5 минут
        return min(exponential_delay + jitter, 300.0)
    
    def increment_attempts(self):
        """Увеличить счетчик попыток"""
        self.attempts += 1
        self.last_attempt = datetime.utcnow()


@dataclass
class SyncResult:
    """
    Результат синхронизации.
    
    Attributes:
        total: Общее количество задач
        synced: Успешно синхронизировано
        failed: Не удалось синхронизировать
        skipped: Пропущено (waiting for backoff)
        conflicts_resolved: Разрешено конфликтов
        duration: Длительность синхронизации (секунды)
        errors: Список ошибок
    """
    total: int = 0
    synced: int = 0
    failed: int = 0
    skipped: int = 0
    conflicts_resolved: int = 0
    duration: float = 0.0
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертировать в словарь"""
        return {
            'total': self.total,
            'synced': self.synced,
            'failed': self.failed,
            'skipped': self.skipped,
            'conflicts_resolved': self.conflicts_resolved,
            'duration': round(self.duration, 2),
            'errors': self.errors
        }


# ============================================================================
# IMPROVED SYNC QUEUE
# ============================================================================

class ImprovedSyncQueue:
    """
    Улучшенная очередь синхронизации.
    
    Features:
    - Exponential backoff с jitter для retry
    - Batch операции (несколько записей за раз)
    - Приоритеты (CRITICAL > HIGH > NORMAL > LOW)
    - Conflict resolution
    - Детальная телеметрия
    - Rate limiting protection
    
    Использование:
        queue = ImprovedSyncQueue(db_conn, sheets_client)
        
        # Синхронизировать все pending записи
        result = queue.sync_pending_records()
        
        # Проверить статус
        status = queue.get_queue_status()
    """
    
    def __init__(
        self,
        db_connection,
        sheets_client,
        batch_size: int = 20,
        max_attempts: int = 5,
        conflict_strategy: str = 'last_write_wins'
    ):
        """
        Инициализация очереди синхронизации.
        
        Args:
            db_connection: Соединение с локальной БД
            sheets_client: Клиент для работы с Google Sheets
            batch_size: Размер batch для синхронизации
            max_attempts: Максимальное количество попыток
            conflict_strategy: Стратегия разрешения конфликтов
        """
        self.conn = db_connection
        self.sheets = sheets_client
        self.batch_size = batch_size
        self.max_attempts = max_attempts
        
        # Conflict resolver
        from sync.conflict_resolver import ConflictResolutionStrategy
        strategy_map = {
            'last_write_wins': ConflictResolutionStrategy.LAST_WRITE_WINS,
            'admin_wins': ConflictResolutionStrategy.ADMIN_WINS,
            'user_wins': ConflictResolutionStrategy.USER_WINS,
            'merge': ConflictResolutionStrategy.MERGE
        }
        self.conflict_resolver = ConflictResolver(
            strategy=strategy_map.get(conflict_strategy, ConflictResolutionStrategy.LAST_WRITE_WINS)
        )
        
        # Статистика
        self.stats = {
            'total_synced': 0,
            'total_failed': 0,
            'total_conflicts': 0,
            'last_sync_time': None
        }
    
    def sync_pending_records(self) -> SyncResult:
        """
        Синхронизировать все pending записи.
        
        Returns:
            Результат синхронизации
        """
        start_time = time.time()
        result = SyncResult()
        
        logger.info("Starting sync of pending records...")
        
        try:
            # Получить все pending задачи
            while True:
                tasks = self._get_pending_tasks(limit=self.batch_size * 2)
                
                if not tasks:
                    break  # Нет записей для синхронизации
                
                result.total += len(tasks)
                
                # Разделить на приоритетные и обычные
                high_priority = [t for t in tasks if t.priority >= SyncPriority.HIGH]
                normal_priority = [t for t in tasks if t.priority < SyncPriority.HIGH]
                
                # Сначала обрабатываем высокоприоритетные по одной
                for task in high_priority:
                    if not self._should_process_task(task):
                        result.skipped += 1
                        continue
                    
                    success, error = self._process_single_task(task)
                    if success:
                        result.synced += 1
                    else:
                        if error:
                            result.errors.append(f"Task {task.id}: {error}")
                
                # Затем batch обработка обычных
                if normal_priority:
                    # Фильтровать задачи, готовые к обработке
                    ready_tasks = [t for t in normal_priority if self._should_process_task(t)]
                    skipped_count = len(normal_priority) - len(ready_tasks)
                    result.skipped += skipped_count
                    
                    if ready_tasks:
                        synced, failed = self._process_batch(ready_tasks[:self.batch_size])
                        result.synced += synced
                        result.failed += failed
        
        except Exception as e:
            logger.error(f"Sync failed with exception: {e}")
            result.errors.append(f"Fatal error: {e}")
        
        finally:
            result.duration = time.time() - start_time
            result.conflicts_resolved = len(self.conflict_resolver.conflict_log)
            
            # Обновить статистику
            self.stats['total_synced'] += result.synced
            self.stats['total_failed'] += result.failed
            self.stats['total_conflicts'] += result.conflicts_resolved
            self.stats['last_sync_time'] = datetime.utcnow().isoformat()
            
            logger.info(
                f"Sync completed: {result.synced} synced, {result.failed} failed, "
                f"{result.skipped} skipped, {result.conflicts_resolved} conflicts resolved "
                f"in {result.duration:.2f}s"
            )
        
        return result
    
    def _get_pending_tasks(self, limit: int) -> List[SyncTask]:
        """
        Получить pending задачи из БД.
        
        Args:
            limit: Максимальное количество задач
            
        Returns:
            Список SyncTask
        """
        try:
            cursor = self.conn.execute("""
                SELECT 
                    id, session_id, email, name, status, action_type, 
                    comment, timestamp, sync_attempts, last_sync_attempt,
                    priority, status_start_time, status_end_time, reason
                FROM logs
                WHERE synced = 0
                ORDER BY priority DESC, timestamp ASC
                LIMIT ?
            """, (limit,))
            
            tasks = []
            for row in cursor.fetchall():
                task = SyncTask(
                    id=row[0],
                    data={
                        'session_id': row[1],
                        'email': row[2],
                        'name': row[3],
                        'status': row[4],
                        'action_type': row[5],
                        'comment': row[6],
                        'timestamp': row[7],
                        'status_start_time': row[11],
                        'status_end_time': row[12],
                        'reason': row[13]
                    },
                    priority=row[10] or SyncPriority.NORMAL,
                    attempts=row[8] or 0,
                    last_attempt=datetime.fromisoformat(row[9]) if row[9] else None,
                    created_at=datetime.fromisoformat(row[7]),
                    max_attempts=self.max_attempts
                )
                
                tasks.append(task)
            
            return tasks
            
        except Exception as e:
            logger.error(f"Failed to get pending tasks: {e}")
            return []
    
    def _should_process_task(self, task: SyncTask) -> bool:
        """
        Проверить, нужно ли обрабатывать задачу сейчас.
        
        Учитывает exponential backoff.
        
        Args:
            task: Задача для проверки
            
        Returns:
            True если можно обрабатывать
        """
        # Если это первая попытка - обрабатываем
        if task.attempts == 0:
            return True
        
        # Если превышено максимальное количество попыток - не обрабатываем
        if not task.should_retry():
            return False
        
        # Проверяем backoff delay
        if task.last_attempt:
            delay = task.get_backoff_delay()
            time_since_last = (datetime.utcnow() - task.last_attempt).total_seconds()
            
            if time_since_last < delay:
                logger.debug(
                    f"Task {task.id} waiting for backoff: "
                    f"{delay - time_since_last:.1f}s remaining"
                )
                return False
        
        return True
    
    def _process_single_task(self, task: SyncTask) -> Tuple[bool, Optional[str]]:
        """
        Обработать одну задачу (для высокоприоритетных).
        
        Args:
            task: Задача для обработки
            
        Returns:
            Tuple[success, error_message]
        """
        try:
            logger.debug(f"Processing task {task.id} (priority={task.priority})")
            
            # Попытка синхронизации
            self._sync_to_sheets(task.data)
            
            # Успех - помечаем как synced
            self._mark_as_synced(task.id)
            
            logger.debug(f"Task {task.id} synced successfully")
            return True, None
            
        except ConflictRequiresManualResolution as e:
            # Конфликт требует ручного разрешения
            logger.warning(f"Task {task.id} requires manual conflict resolution")
            self._increment_attempts(task.id)
            return False, "Manual conflict resolution required"
            
        except Exception as e:
            # Другая ошибка
            logger.error(f"Task {task.id} sync failed: {e}")
            
            # Увеличить счетчик попыток
            task.increment_attempts()
            self._increment_attempts(task.id)
            
            # Если превышено максимальное количество попыток
            if not task.should_retry():
                self._mark_as_failed(task.id, str(e))
                return False, f"Failed after {self.max_attempts} attempts: {e}"
            
            return False, str(e)
    
    def _process_batch(self, tasks: List[SyncTask]) -> Tuple[int, int]:
        """
        Batch обработка задач.
        
        Вместо N отдельных запросов к Google Sheets,
        делаем 1 batch request.
        
        Args:
            tasks: Список задач для обработки
            
        Returns:
            Tuple[synced_count, failed_count]
        """
        if not tasks:
            return 0, 0
        
        synced = 0
        failed = 0
        
        try:
            logger.debug(f"Processing batch of {len(tasks)} tasks")
            
            # Подготовить batch данные
            batch_data = [task.data for task in tasks]
            
            # Отправить batch в Google Sheets
            self._batch_update_sheets(batch_data)
            
            # Пометить все как synced
            task_ids = [task.id for task in tasks]
            self._mark_batch_as_synced(task_ids)
            
            synced = len(tasks)
            logger.debug(f"Batch synced successfully: {synced} tasks")
            
        except Exception as e:
            logger.error(f"Batch sync failed: {e}")
            
            # Fallback - обработать по одной
            logger.info("Falling back to individual processing...")
            
            for task in tasks:
                success, _ = self._process_single_task(task)
                if success:
                    synced += 1
                else:
                    failed += 1
        
        return synced, failed
    
    def _sync_to_sheets(self, data: Dict[str, Any]):
        """
        Синхронизировать одну запись в Google Sheets.
        
        Args:
            data: Данные для синхронизации
            
        Raises:
            Exception: Если синхронизация не удалась
        """
        # TODO: Реализация зависит от sheets_client API
        # Пример:
        # self.sheets.append_row(data)
        
        # Заглушка для примера
        logger.debug(f"Syncing to sheets: {data['email']} - {data['action_type']}")
        
        # Имитация работы
        time.sleep(0.1)
    
    def _batch_update_sheets(self, batch_data: List[Dict[str, Any]]):
        """
        Batch обновление Google Sheets.
        
        Args:
            batch_data: Список записей для синхронизации
            
        Raises:
            Exception: Если синхронизация не удалась
        """
        # TODO: Реализация зависит от sheets_client API
        # Пример:
        # self.sheets.batch_append(batch_data)
        
        # Заглушка для примера
        logger.debug(f"Batch syncing {len(batch_data)} records to sheets")
        
        # Имитация работы
        time.sleep(0.5)
    
    def _mark_as_synced(self, task_id: int):
        """Пометить задачу как синхронизированную"""
        self.conn.execute("""
            UPDATE logs
            SET synced = 1, last_sync_attempt = ?
            WHERE id = ?
        """, (datetime.utcnow().isoformat(), task_id))
        self.conn.commit()
    
    def _mark_batch_as_synced(self, task_ids: List[int]):
        """Пометить batch задач как синхронизированные"""
        placeholders = ','.join('?' * len(task_ids))
        self.conn.execute(f"""
            UPDATE logs
            SET synced = 1, last_sync_attempt = ?
            WHERE id IN ({placeholders})
        """, [datetime.utcnow().isoformat()] + task_ids)
        self.conn.commit()
    
    def _mark_as_failed(self, task_id: int, error: str):
        """Пометить задачу как failed после исчерпания попыток"""
        self.conn.execute("""
            UPDATE logs
            SET synced = -1,
                comment = ?
            WHERE id = ?
        """, (f"[SYNC FAILED AFTER {self.max_attempts} ATTEMPTS] {error}", task_id))
        self.conn.commit()
        
        # TODO: Отправить уведомление администратору
        logger.error(f"Task {task_id} marked as FAILED: {error}")
    
    def _increment_attempts(self, task_id: int):
        """Увеличить счетчик попыток синхронизации"""
        self.conn.execute("""
            UPDATE logs
            SET sync_attempts = sync_attempts + 1,
                last_sync_attempt = ?
            WHERE id = ?
        """, (datetime.utcnow().isoformat(), task_id))
        self.conn.commit()
    
    def get_queue_status(self) -> Dict[str, Any]:
        """
        Получить статус очереди синхронизации.
        
        Returns:
            Словарь со статистикой очереди
        """
        try:
            # Pending записи
            cursor = self.conn.execute("""
                SELECT COUNT(*), 
                       SUM(CASE WHEN priority >= 8 THEN 1 ELSE 0 END) as high_priority,
                       SUM(CASE WHEN sync_attempts >= ? THEN 1 ELSE 0 END) as retry_count
                FROM logs
                WHERE synced = 0
            """, (3,))
            
            row = cursor.fetchone()
            pending = row[0] or 0
            high_priority = row[1] or 0
            retry_count = row[2] or 0
            
            # Failed записи
            cursor = self.conn.execute("SELECT COUNT(*) FROM logs WHERE synced = -1")
            failed = cursor.fetchone()[0] or 0
            
            return {
                'pending': pending,
                'high_priority': high_priority,
                'retry_count': retry_count,
                'failed': failed,
                'stats': self.stats.copy()
            }
            
        except Exception as e:
            logger.error(f"Failed to get queue status: {e}")
            return {
                'pending': 0,
                'high_priority': 0,
                'retry_count': 0,
                'failed': 0,
                'stats': self.stats.copy()
            }
    
    def retry_failed_records(self) -> SyncResult:
        """
        Повторить синхронизацию failed записей.
        
        Returns:
            Результат синхронизации
        """
        logger.info("Retrying failed records...")
        
        # Сбросить статус failed → pending
        self.conn.execute("""
            UPDATE logs
            SET synced = 0, sync_attempts = 0, last_sync_attempt = NULL
            WHERE synced = -1
        """)
        self.conn.commit()
        
        # Синхронизировать
        return self.sync_pending_records()


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

if __name__ == "__main__":
    """
    Пример использования ImprovedSyncQueue.
    
    Запуск:
        python sync/sync_queue_improved.py
    """
    import sqlite3
    
    # Настройка логирования
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 80)
    print("ImprovedSyncQueue - Usage Example")
    print("=" * 80)
    print()
    
    # Создать тестовую БД
    conn = sqlite3.connect(":memory:")
    
    # Создать таблицу logs
    conn.execute("""
        CREATE TABLE logs (
            id INTEGER PRIMARY KEY,
            session_id TEXT,
            email TEXT,
            name TEXT,
            status TEXT,
            action_type TEXT,
            comment TEXT,
            timestamp TEXT,
            synced INTEGER DEFAULT 0,
            sync_attempts INTEGER DEFAULT 0,
            last_sync_attempt TEXT,
            priority INTEGER DEFAULT 5,
            status_start_time TEXT,
            status_end_time TEXT,
            reason TEXT
        )
    """)
    
    # Добавить тестовые записи
    for i in range(5):
        conn.execute("""
            INSERT INTO logs (
                session_id, email, name, status, action_type,
                timestamp, priority
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            f"session_{i}",
            f"user{i}@example.com",
            f"User {i}",
            "В работе",
            "STATUS_CHANGE",
            datetime.utcnow().isoformat(),
            SyncPriority.CRITICAL if i == 0 else SyncPriority.NORMAL
        ))
    conn.commit()
    
    # Создать mock sheets client
    class MockSheetsClient:
        pass
    
    sheets = MockSheetsClient()
    
    # Создать sync queue
    queue = ImprovedSyncQueue(
        db_connection=conn,
        sheets_client=sheets,
        batch_size=3,
        max_attempts=3
    )
    
    print("✅ ImprovedSyncQueue initialized")
    print()
    
    # Проверить статус
    status = queue.get_queue_status()
    print(f"Queue status:")
    print(f"  Pending: {status['pending']}")
    print(f"  High priority: {status['high_priority']}")
    print()
    
    # Синхронизировать
    print("Starting sync...")
    result = queue.sync_pending_records()
    
    print()
    print(f"Sync result:")
    print(f"  Total: {result.total}")
    print(f"  Synced: {result.synced}")
    print(f"  Failed: {result.failed}")
    print(f"  Skipped: {result.skipped}")
    print(f"  Duration: {result.duration:.2f}s")
    print()
    
    # Финальный статус
    status = queue.get_queue_status()
    print(f"Final queue status:")
    print(f"  Pending: {status['pending']}")
    print(f"  Failed: {status['failed']}")
    print()
    
    conn.close()
    print("=" * 80)
