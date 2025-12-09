"""
Audit Logging System for WorkTimeTracker Admin

Система аудита для отслеживания всех действий администратора.

Features:
- Логирование всех изменений данных
- Сохранение состояния до/после изменений
- IP адрес и hostname администратора
- Поиск по истории изменений
- Фильтрация по дате, администратору, типу действия
- Экспорт audit логов
- Отчеты по действиям администратора

Использование:
    from admin_app.audit_logger import AuditLogger
    
    audit = AuditLogger(db_connection, admin_email="admin@company.com")
    
    # Логирование действия
    audit.log_action(
        action="UPDATE_USER_STATUS",
        entity_type="USER",
        entity_id="user@company.com",
        before_state={'status': 'В работе'},
        after_state={'status': 'Обед'}
    )
    
    # Получить историю
    history = audit.get_entity_history("USER", "user@company.com")
    
    # Поиск действий администратора
    actions = audit.get_admin_actions(
        start_date=datetime(2025, 11, 1),
        end_date=datetime(2025, 11, 30)
    )

Автор: WorkTimeTracker Security Team
Дата: 2025-11-24
"""

import json
import socket
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class AuditEntry:
    """
    Запись в audit log.
    
    Attributes:
        id: Уникальный ID записи
        timestamp: Время действия
        admin_email: Email администратора
        action: Тип действия (CREATE, UPDATE, DELETE, etc.)
        entity_type: Тип сущности (USER, SESSION, CONFIG, etc.)
        entity_id: ID сущности
        before_state: Состояние до изменения
        after_state: Состояние после изменения
        ip_address: IP адрес администратора
        hostname: Hostname машины администратора
        success: Успешно ли выполнено действие
        error_message: Сообщение об ошибке (если не успешно)
    """
    id: Optional[int]
    timestamp: str
    admin_email: str
    action: str
    entity_type: str
    entity_id: Optional[str]
    before_state: Optional[Dict[str, Any]]
    after_state: Optional[Dict[str, Any]]
    ip_address: str
    hostname: str
    success: bool
    error_message: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертировать в словарь"""
        return asdict(self)


# ============================================================================
# AUDIT LOGGER
# ============================================================================

class AuditLogger:
    """
    Система аудита для администратора.
    
    Логирует все действия администратора с полной информацией:
    - Кто выполнил действие
    - Что было изменено
    - Когда
    - Состояние до и после
    - IP адрес и hostname
    - Результат (успех/ошибка)
    
    Использование:
        audit = AuditLogger(db_connection, admin_email="admin@example.com")
        
        # До изменения
        old_status = get_user_status(user_email)
        
        try:
            # Выполнить изменение
            update_user_status(user_email, new_status)
            
            # Залогировать успех
            audit.log_action(
                action="UPDATE_USER_STATUS",
                entity_type="USER",
                entity_id=user_email,
                before_state={'status': old_status},
                after_state={'status': new_status},
                success=True
            )
        except Exception as e:
            # Залогировать ошибку
            audit.log_action(
                action="UPDATE_USER_STATUS",
                entity_type="USER",
                entity_id=user_email,
                before_state={'status': old_status},
                after_state={'status': new_status},
                success=False,
                error_message=str(e)
            )
    """
    
    # Типы действий
    ACTION_CREATE = "CREATE"
    ACTION_UPDATE = "UPDATE"
    ACTION_DELETE = "DELETE"
    ACTION_LOGIN = "LOGIN"
    ACTION_LOGOUT = "LOGOUT"
    ACTION_EXPORT = "EXPORT"
    ACTION_IMPORT = "IMPORT"
    ACTION_CONFIG_CHANGE = "CONFIG_CHANGE"
    
    # Типы сущностей
    ENTITY_USER = "USER"
    ENTITY_SESSION = "SESSION"
    ENTITY_CONFIG = "CONFIG"
    ENTITY_SCHEDULE = "SCHEDULE"
    ENTITY_NOTIFICATION = "NOTIFICATION"
    ENTITY_REPORT = "REPORT"
    
    def __init__(self, db_connection, admin_email: str):
        """
        Инициализация audit logger.
        
        Args:
            db_connection: Соединение с БД
            admin_email: Email текущего администратора
        """
        self.conn = db_connection
        self.admin_email = admin_email
        
        # Создать таблицу audit_log если не существует
        self._ensure_audit_table()
        
        # Кэш для IP и hostname
        self._ip_address: Optional[str] = None
        self._hostname: Optional[str] = None
    
    def _ensure_audit_table(self):
        """Создать таблицу audit_log если не существует"""
        try:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    admin_email TEXT NOT NULL,
                    action TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT,
                    before_state TEXT,
                    after_state TEXT,
                    ip_address TEXT,
                    hostname TEXT,
                    success INTEGER DEFAULT 1,
                    error_message TEXT
                )
            """)
            
            # Индексы для быстрого поиска
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp 
                ON audit_log(timestamp)
            """)
            
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_admin 
                ON audit_log(admin_email, timestamp)
            """)
            
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_entity 
                ON audit_log(entity_type, entity_id, timestamp)
            """)
            
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_action 
                ON audit_log(action, timestamp)
            """)
            
            self.conn.commit()
            logger.debug("Audit log table ensured")
            
        except Exception as e:
            logger.error(f"Failed to create audit_log table: {e}")
            # Не падаем - audit logging не должен ломать основную функциональность
    
    def _get_ip_address(self) -> str:
        """Получить локальный IP адрес"""
        if self._ip_address:
            return self._ip_address
        
        try:
            # Трюк для получения локального IP без внешнего подключения
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            self._ip_address = ip
            return ip
        except Exception:
            self._ip_address = "unknown"
            return "unknown"
    
    def _get_hostname(self) -> str:
        """Получить hostname машины"""
        if self._hostname:
            return self._hostname
        
        try:
            self._hostname = socket.gethostname()
            return self._hostname
        except Exception:
            self._hostname = "unknown"
            return "unknown"
    
    def log_action(
        self,
        action: str,
        entity_type: str,
        entity_id: Optional[str] = None,
        before_state: Optional[Dict[str, Any]] = None,
        after_state: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> Optional[int]:
        """
        Записать действие в audit log.
        
        Args:
            action: Тип действия (CREATE, UPDATE, DELETE, etc.)
            entity_type: Тип сущности (USER, SESSION, CONFIG, etc.)
            entity_id: ID сущности
            before_state: Состояние до изменения (dict)
            after_state: Состояние после изменения (dict)
            success: Успешно ли выполнено действие
            error_message: Сообщение об ошибке (если не успешно)
            
        Returns:
            ID созданной записи или None если не удалось
        """
        try:
            cursor = self.conn.execute("""
                INSERT INTO audit_log (
                    timestamp, admin_email, action, entity_type, entity_id,
                    before_state, after_state, ip_address, hostname,
                    success, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.utcnow().isoformat(),
                self.admin_email,
                action,
                entity_type,
                entity_id,
                json.dumps(before_state, ensure_ascii=False) if before_state else None,
                json.dumps(after_state, ensure_ascii=False) if after_state else None,
                self._get_ip_address(),
                self._get_hostname(),
                1 if success else 0,
                error_message
            ))
            
            self.conn.commit()
            
            audit_id = cursor.lastrowid
            logger.debug(f"Audit log created: {action} on {entity_type}:{entity_id} (id={audit_id})")
            
            return audit_id
            
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
            # Audit logging не должен ломать основную функциональность
            return None
    
    def get_entity_history(
        self,
        entity_type: str,
        entity_id: str,
        limit: int = 100
    ) -> List[AuditEntry]:
        """
        Получить историю изменений сущности.
        
        Args:
            entity_type: Тип сущности
            entity_id: ID сущности
            limit: Максимальное количество записей
            
        Returns:
            Список записей AuditEntry
        """
        try:
            cursor = self.conn.execute("""
                SELECT 
                    id, timestamp, admin_email, action, entity_type, entity_id,
                    before_state, after_state, ip_address, hostname, success, error_message
                FROM audit_log
                WHERE entity_type = ? AND entity_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (entity_type, entity_id, limit))
            
            entries = []
            for row in cursor.fetchall():
                entry = AuditEntry(
                    id=row[0],
                    timestamp=row[1],
                    admin_email=row[2],
                    action=row[3],
                    entity_type=row[4],
                    entity_id=row[5],
                    before_state=json.loads(row[6]) if row[6] else None,
                    after_state=json.loads(row[7]) if row[7] else None,
                    ip_address=row[8],
                    hostname=row[9],
                    success=bool(row[10]),
                    error_message=row[11]
                )
                entries.append(entry)
            
            return entries
            
        except Exception as e:
            logger.error(f"Failed to get entity history: {e}")
            return []
    
    def get_admin_actions(
        self,
        admin_email: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        action_type: Optional[str] = None,
        limit: int = 1000
    ) -> List[AuditEntry]:
        """
        Получить действия администратора с фильтрацией.
        
        Args:
            admin_email: Email администратора (если None - текущий)
            start_date: Начальная дата фильтрации
            end_date: Конечная дата фильтрации
            action_type: Фильтр по типу действия
            limit: Максимальное количество записей
            
        Returns:
            Список записей AuditEntry
        """
        try:
            # Построить запрос
            query = """
                SELECT 
                    id, timestamp, admin_email, action, entity_type, entity_id,
                    before_state, after_state, ip_address, hostname, success, error_message
                FROM audit_log
                WHERE 1=1
            """
            params = []
            
            # Фильтры
            if admin_email:
                query += " AND admin_email = ?"
                params.append(admin_email)
            else:
                query += " AND admin_email = ?"
                params.append(self.admin_email)
            
            if start_date:
                query += " AND timestamp >= ?"
                params.append(start_date.isoformat())
            
            if end_date:
                query += " AND timestamp <= ?"
                params.append(end_date.isoformat())
            
            if action_type:
                query += " AND action = ?"
                params.append(action_type)
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            # Выполнить запрос
            cursor = self.conn.execute(query, params)
            
            entries = []
            for row in cursor.fetchall():
                entry = AuditEntry(
                    id=row[0],
                    timestamp=row[1],
                    admin_email=row[2],
                    action=row[3],
                    entity_type=row[4],
                    entity_id=row[5],
                    before_state=json.loads(row[6]) if row[6] else None,
                    after_state=json.loads(row[7]) if row[7] else None,
                    ip_address=row[8],
                    hostname=row[9],
                    success=bool(row[10]),
                    error_message=row[11]
                )
                entries.append(entry)
            
            return entries
            
        except Exception as e:
            logger.error(f"Failed to get admin actions: {e}")
            return []
    
    def get_recent_actions(self, hours: int = 24, limit: int = 100) -> List[AuditEntry]:
        """
        Получить последние действия за N часов.
        
        Args:
            hours: Количество часов назад
            limit: Максимальное количество записей
            
        Returns:
            Список записей AuditEntry
        """
        start_date = datetime.utcnow() - timedelta(hours=hours)
        return self.get_admin_actions(start_date=start_date, limit=limit)
    
    def get_statistics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Получить статистику по audit логам.
        
        Args:
            start_date: Начальная дата
            end_date: Конечная дата
            
        Returns:
            Словарь со статистикой
        """
        try:
            query = "SELECT COUNT(*), action, entity_type FROM audit_log WHERE 1=1"
            params = []
            
            if start_date:
                query += " AND timestamp >= ?"
                params.append(start_date.isoformat())
            
            if end_date:
                query += " AND timestamp <= ?"
                params.append(end_date.isoformat())
            
            query += " GROUP BY action, entity_type"
            
            cursor = self.conn.execute(query, params)
            
            stats = {
                'total_actions': 0,
                'by_action': {},
                'by_entity_type': {},
                'by_combination': []
            }
            
            for row in cursor.fetchall():
                count, action, entity_type = row
                stats['total_actions'] += count
                
                # По типу действия
                if action not in stats['by_action']:
                    stats['by_action'][action] = 0
                stats['by_action'][action] += count
                
                # По типу сущности
                if entity_type not in stats['by_entity_type']:
                    stats['by_entity_type'][entity_type] = 0
                stats['by_entity_type'][entity_type] += count
                
                # Комбинация
                stats['by_combination'].append({
                    'action': action,
                    'entity_type': entity_type,
                    'count': count
                })
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {
                'total_actions': 0,
                'by_action': {},
                'by_entity_type': {},
                'by_combination': []
            }
    
    def export_to_json(
        self,
        filepath: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> bool:
        """
        Экспортировать audit логи в JSON файл.
        
        Args:
            filepath: Путь к файлу для сохранения
            start_date: Начальная дата
            end_date: Конечная дата
            
        Returns:
            True если успешно, False если ошибка
        """
        try:
            # Получить записи
            entries = self.get_admin_actions(
                start_date=start_date,
                end_date=end_date,
                limit=10000  # Большой лимит для экспорта
            )
            
            # Конвертировать в dict
            data = [entry.to_dict() for entry in entries]
            
            # Сохранить в файл
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Audit log exported to {filepath}: {len(data)} entries")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export audit log: {e}")
            return False
    
    def search(
        self,
        query: str,
        search_in: List[str] = None,
        limit: int = 100
    ) -> List[AuditEntry]:
        """
        Полнотекстовый поиск по audit логам.
        
        Args:
            query: Поисковый запрос
            search_in: Поля для поиска (admin_email, action, entity_id, etc.)
            limit: Максимальное количество результатов
            
        Returns:
            Список найденных записей
        """
        if not search_in:
            search_in = ['admin_email', 'action', 'entity_type', 'entity_id']
        
        try:
            # Построить WHERE clause
            conditions = []
            params = []
            
            for field in search_in:
                conditions.append(f"{field} LIKE ?")
                params.append(f"%{query}%")
            
            where_clause = " OR ".join(conditions)
            
            sql = f"""
                SELECT 
                    id, timestamp, admin_email, action, entity_type, entity_id,
                    before_state, after_state, ip_address, hostname, success, error_message
                FROM audit_log
                WHERE {where_clause}
                ORDER BY timestamp DESC
                LIMIT ?
            """
            params.append(limit)
            
            cursor = self.conn.execute(sql, params)
            
            entries = []
            for row in cursor.fetchall():
                entry = AuditEntry(
                    id=row[0],
                    timestamp=row[1],
                    admin_email=row[2],
                    action=row[3],
                    entity_type=row[4],
                    entity_id=row[5],
                    before_state=json.loads(row[6]) if row[6] else None,
                    after_state=json.loads(row[7]) if row[7] else None,
                    ip_address=row[8],
                    hostname=row[9],
                    success=bool(row[10]),
                    error_message=row[11]
                )
                entries.append(entry)
            
            return entries
            
        except Exception as e:
            logger.error(f"Failed to search audit log: {e}")
            return []


# ============================================================================
# CONTEXT MANAGER
# ============================================================================

class AuditContext:
    """
    Context manager для автоматического audit logging.
    
    Использование:
        with AuditContext(audit, action="UPDATE", entity_type="USER", entity_id="user@email.com") as ctx:
            ctx.before_state = {'status': 'В работе'}
            
            # Выполнить изменения
            update_user_status(user_email, new_status)
            
            ctx.after_state = {'status': 'Обед'}
    """
    
    def __init__(
        self,
        audit_logger: AuditLogger,
        action: str,
        entity_type: str,
        entity_id: Optional[str] = None
    ):
        self.audit = audit_logger
        self.action = action
        self.entity_type = entity_type
        self.entity_id = entity_id
        
        self.before_state: Optional[Dict[str, Any]] = None
        self.after_state: Optional[Dict[str, Any]] = None
        self.success = True
        self.error_message: Optional[str] = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # Произошла ошибка
            self.success = False
            self.error_message = str(exc_val)
        
        # Залогировать действие
        self.audit.log_action(
            action=self.action,
            entity_type=self.entity_type,
            entity_id=self.entity_id,
            before_state=self.before_state,
            after_state=self.after_state,
            success=self.success,
            error_message=self.error_message
        )
        
        # Не подавлять исключение
        return False


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

if __name__ == "__main__":
    """
    Пример использования AuditLogger.
    
    Запуск:
        python admin_app/audit_logger.py
    """
    import sqlite3
    
    # Настройка логирования
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 80)
    print("AuditLogger - Usage Example")
    print("=" * 80)
    print()
    
    # Создать тестовую БД
    conn = sqlite3.connect(":memory:")
    
    # Создать audit logger
    audit = AuditLogger(conn, admin_email="admin@example.com")
    print("✅ AuditLogger initialized")
    print()
    
    # Пример 1: Простое логирование
    print("Example 1: Simple logging")
    audit.log_action(
        action="UPDATE_USER_STATUS",
        entity_type="USER",
        entity_id="user@example.com",
        before_state={'status': 'В работе'},
        after_state={'status': 'Обед'}
    )
    print("✅ Action logged")
    print()
    
    # Пример 2: Логирование с ошибкой
    print("Example 2: Logging with error")
    audit.log_action(
        action="DELETE_USER",
        entity_type="USER",
        entity_id="user@example.com",
        success=False,
        error_message="User not found"
    )
    print("✅ Error logged")
    print()
    
    # Пример 3: Context manager
    print("Example 3: Using context manager")
    with AuditContext(audit, "UPDATE", "USER", "user2@example.com") as ctx:
        ctx.before_state = {'name': 'Old Name'}
        # Выполнить изменения...
        ctx.after_state = {'name': 'New Name'}
    print("✅ Action logged via context manager")
    print()
    
    # Получить историю
    print("Example 4: Getting history")
    history = audit.get_entity_history("USER", "user@example.com")
    print(f"Found {len(history)} entries in history")
    for entry in history:
        print(f"  {entry.timestamp} - {entry.action} by {entry.admin_email}")
    print()
    
    # Статистика
    print("Example 5: Statistics")
    stats = audit.get_statistics()
    print(f"Total actions: {stats['total_actions']}")
    print(f"By action: {stats['by_action']}")
    print()
    
    conn.close()
    print("=" * 80)
