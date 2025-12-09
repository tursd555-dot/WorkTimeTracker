"""
Database Migration System for WorkTimeTracker

Система управления миграциями БД с поддержкой:
- Версионирования схемы
- Rollback (откат изменений)
- Проверка целостности (checksums)
- Транзакционные миграции (все или ничего)
- Автоматическое применение при старте

Проблемы старой системы:
1. Нет версионирования схемы БД
2. Невозможно откатить изменения
3. Сложно обновлять схему у пользователей
4. Нет проверки целостности миграций

Решения:
1. Каждая миграция имеет версию и checksum
2. Поддержка up/down SQL для rollback
3. Автоматическое применение миграций
4. Валидация через checksums

Использование:
    from db_migrations_improved import MigrationManager
    
    manager = MigrationManager(db_connection)
    
    # Применить все миграции
    manager.migrate()
    
    # Откатить до версии 2
    manager.rollback(target_version=2)
    
    # Проверить целостность
    manager.verify_integrity()

Автор: WorkTimeTracker DB Team
Дата: 2025-11-24
"""

import hashlib
import logging
from typing import List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class Migration:
    """
    Одна миграция БД.
    
    Attributes:
        version: Номер версии (1, 2, 3, ...)
        description: Описание миграции
        up_sql: SQL для применения (upgrade)
        down_sql: SQL для отката (downgrade)
        checksum: Контрольная сумма для верификации
    """
    version: int
    description: str
    up_sql: str
    down_sql: str
    checksum: str
    
    @classmethod
    def create(cls, version: int, description: str, up_sql: str, down_sql: str):
        """
        Создать миграцию с автоматическим checksum.
        
        Args:
            version: Номер версии
            description: Описание
            up_sql: SQL для upgrade
            down_sql: SQL для downgrade
            
        Returns:
            Migration объект
        """
        # Вычислить checksum (SHA-256 от version + up_sql)
        content = f"{version}{up_sql}".encode('utf-8')
        checksum = hashlib.sha256(content).hexdigest()
        
        return cls(version, description, up_sql, down_sql, checksum)


# ============================================================================
# MIGRATION MANAGER
# ============================================================================

class MigrationManager:
    """
    Управление миграциями БД.
    
    Features:
    - Версионирование схемы
    - Rollback поддержка
    - Проверка целостности через checksums
    - Транзакционные миграции (все или ничего)
    - История миграций
    
    Использование:
        manager = MigrationManager(db_connection)
        
        # Применить все pending миграции
        manager.migrate()
        
        # Откатить до версии 2
        manager.rollback(target_version=2)
        
        # Проверить целостность
        if manager.verify_integrity():
            print("All migrations are valid")
    """
    
    # ========================================================================
    # ОПРЕДЕЛЕНИЕ МИГРАЦИЙ
    # ========================================================================
    
    MIGRATIONS: List[Migration] = [
        Migration.create(
            version=1,
            description="Initial schema with logs and sessions",
            up_sql="""
                -- Таблица для логов действий пользователей
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    email TEXT NOT NULL,
                    name TEXT NOT NULL,
                    status TEXT,
                    action_type TEXT NOT NULL,
                    comment TEXT,
                    timestamp TEXT NOT NULL,
                    synced INTEGER DEFAULT 0,
                    sync_attempts INTEGER DEFAULT 0,
                    last_sync_attempt TEXT,
                    priority INTEGER DEFAULT 1,
                    status_start_time TEXT,
                    status_end_time TEXT,
                    reason TEXT,
                    user_group TEXT
                );
                
                -- Таблица для сессий
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL,
                    session_id TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    login_time TEXT NOT NULL,
                    logout_time TEXT
                );
                
                -- Основные индексы
                CREATE INDEX IF NOT EXISTS idx_logs_email ON logs(email);
                CREATE INDEX IF NOT EXISTS idx_logs_session ON logs(session_id);
                CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp);
                CREATE INDEX IF NOT EXISTS idx_logs_synced ON logs(synced);
                CREATE INDEX IF NOT EXISTS idx_logs_action_type ON logs(action_type);
                
                -- Триггеры
                CREATE TRIGGER IF NOT EXISTS check_comment_length
                BEFORE INSERT ON logs
                FOR EACH ROW
                WHEN length(NEW.comment) > 500
                BEGIN
                    SELECT RAISE(ABORT, 'Comment too long');
                END;
                
                CREATE TRIGGER IF NOT EXISTS prevent_duplicate_logout
                BEFORE INSERT ON logs
                FOR EACH ROW
                WHEN LOWER(NEW.action_type) = 'logout' AND EXISTS (
                    SELECT 1 FROM logs
                    WHERE session_id = NEW.session_id
                    AND LOWER(action_type) = 'logout'
                )
                BEGIN
                    SELECT RAISE(ABORT, 'Duplicate LOGOUT action');
                END;
            """,
            down_sql="""
                DROP TRIGGER IF EXISTS prevent_duplicate_logout;
                DROP TRIGGER IF EXISTS check_comment_length;
                DROP INDEX IF EXISTS idx_logs_action_type;
                DROP INDEX IF EXISTS idx_logs_synced;
                DROP INDEX IF EXISTS idx_logs_timestamp;
                DROP INDEX IF EXISTS idx_logs_session;
                DROP INDEX IF EXISTS idx_logs_email;
                DROP TABLE IF EXISTS sessions;
                DROP TABLE IF EXISTS logs;
            """
        ),
        
        Migration.create(
            version=2,
            description="Add audit logging table",
            up_sql="""
                -- Таблица для audit логов (действия администратора)
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
                );
                
                -- Индексы для быстрого поиска
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp 
                ON audit_log(timestamp);
                
                CREATE INDEX IF NOT EXISTS idx_audit_admin 
                ON audit_log(admin_email, timestamp);
                
                CREATE INDEX IF NOT EXISTS idx_audit_entity 
                ON audit_log(entity_type, entity_id, timestamp);
                
                CREATE INDEX IF NOT EXISTS idx_audit_action 
                ON audit_log(action, timestamp);
            """,
            down_sql="""
                DROP INDEX IF EXISTS idx_audit_action;
                DROP INDEX IF EXISTS idx_audit_entity;
                DROP INDEX IF EXISTS idx_audit_admin;
                DROP INDEX IF EXISTS idx_audit_timestamp;
                DROP TABLE IF EXISTS audit_log;
            """
        ),
        
        Migration.create(
            version=3,
            description="Optimize indexes for sync performance",
            up_sql="""
                -- Удалить избыточный индекс (дублируется в составном)
                DROP INDEX IF EXISTS idx_logs_synced;
                
                -- Оптимизированный partial index для pending записей
                CREATE INDEX IF NOT EXISTS idx_logs_sync_query 
                ON logs(synced, priority, timestamp)
                WHERE synced = 0;
                
                -- Индекс для поиска активных сессий
                CREATE INDEX IF NOT EXISTS idx_logs_active_sessions 
                ON logs(email, session_id, action_type)
                WHERE action_type IN ('LOGIN', 'LOGOUT');
                
                -- Составной индекс для email + session + end time
                CREATE INDEX IF NOT EXISTS idx_logs_email_session_end 
                ON logs(email, session_id, status_end_time);
                
                -- Составной индекс для очереди синхронизации
                CREATE INDEX IF NOT EXISTS idx_logs_synced_priority_id 
                ON logs(synced, priority, id);
                
                -- Обновить статистику для оптимизатора
                ANALYZE logs;
            """,
            down_sql="""
                DROP INDEX IF EXISTS idx_logs_synced_priority_id;
                DROP INDEX IF EXISTS idx_logs_email_session_end;
                DROP INDEX IF EXISTS idx_logs_active_sessions;
                DROP INDEX IF EXISTS idx_logs_sync_query;
                
                -- Восстановить старый индекс
                CREATE INDEX IF NOT EXISTS idx_logs_synced ON logs(synced);
            """
        ),
        
        Migration.create(
            version=4,
            description="Add rule_last_sent table for notifications",
            up_sql="""
                -- Таблица для отслеживания последних отправленных уведомлений
                CREATE TABLE IF NOT EXISTS rule_last_sent (
                    rule_id TEXT PRIMARY KEY,
                    user_email TEXT NOT NULL,
                    last_sent_timestamp TEXT NOT NULL
                );
                
                CREATE INDEX IF NOT EXISTS idx_rule_last_sent_user 
                ON rule_last_sent(user_email);
                
                -- Таблица для приложений логов (если нужна)
                CREATE TABLE IF NOT EXISTS app_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL
                );
                
                CREATE INDEX IF NOT EXISTS idx_app_logs_ts 
                ON app_logs(ts);
            """,
            down_sql="""
                DROP INDEX IF EXISTS idx_app_logs_ts;
                DROP TABLE IF EXISTS app_logs;
                DROP INDEX IF EXISTS idx_rule_last_sent_user;
                DROP TABLE IF EXISTS rule_last_sent;
            """
        ),
    ]
    
    # ========================================================================
    # INITIALIZATION
    # ========================================================================
    
    def __init__(self, db_connection):
        """
        Инициализация migration manager.
        
        Args:
            db_connection: Соединение с БД
        """
        self.conn = db_connection
        self._ensure_migrations_table()
    
    def _ensure_migrations_table(self):
        """Создать таблицу для отслеживания миграций"""
        try:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    description TEXT NOT NULL,
                    applied_at TEXT NOT NULL,
                    checksum TEXT NOT NULL
                )
            """)
            self.conn.commit()
            logger.debug("Schema migrations table ensured")
        except Exception as e:
            logger.error(f"Failed to create migrations table: {e}")
            raise
    
    # ========================================================================
    # MIGRATION OPERATIONS
    # ========================================================================
    
    def get_current_version(self) -> int:
        """
        Получить текущую версию схемы БД.
        
        Returns:
            Номер версии (0 если нет миграций)
        """
        try:
            cursor = self.conn.execute("""
                SELECT COALESCE(MAX(version), 0)
                FROM schema_migrations
            """)
            return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Failed to get current version: {e}")
            return 0
    
    def migrate(self, target_version: Optional[int] = None):
        """
        Применить миграции до указанной версии.
        
        Если target_version не указан, применить все pending миграции.
        
        Args:
            target_version: Целевая версия (None = последняя)
        """
        current = self.get_current_version()
        target = target_version or max(m.version for m in self.MIGRATIONS)
        
        if current >= target:
            logger.info(f"Already at version {current}, nothing to migrate")
            return
        
        # Найти миграции для применения
        migrations_to_apply = [
            m for m in self.MIGRATIONS
            if current < m.version <= target
        ]
        
        if not migrations_to_apply:
            logger.info("No migrations to apply")
            return
        
        # Применить миграции по порядку
        for migration in sorted(migrations_to_apply, key=lambda m: m.version):
            self._apply_migration(migration)
        
        logger.info(f"✅ Migrated from version {current} to {target}")
    
    def _apply_migration(self, migration: Migration):
        """
        Применить одну миграцию транзакционно.
        
        Args:
            migration: Миграция для применения
        """
        logger.info(f"Applying migration {migration.version}: {migration.description}")
        
        try:
            # Начать транзакцию
            self.conn.execute("BEGIN")
            
            # Выполнить SQL миграции
            self.conn.executescript(migration.up_sql)
            
            # Записать в таблицу миграций
            self.conn.execute("""
                INSERT INTO schema_migrations (version, description, applied_at, checksum)
                VALUES (?, ?, ?, ?)
            """, (
                migration.version,
                migration.description,
                datetime.utcnow().isoformat(),
                migration.checksum
            ))
            
            # Закоммитить транзакцию
            self.conn.commit()
            
            logger.info(f"✅ Migration {migration.version} applied successfully")
            
        except Exception as e:
            # Откатить при ошибке
            self.conn.rollback()
            logger.error(f"❌ Migration {migration.version} failed: {e}")
            raise Exception(f"Migration {migration.version} failed: {e}")
    
    def rollback(self, target_version: int):
        """
        Откатить миграции до указанной версии.
        
        Args:
            target_version: Версия, до которой откатить
        """
        current = self.get_current_version()
        
        if current <= target_version:
            logger.info(f"Already at version {current}, nothing to rollback")
            return
        
        # Найти миграции для отката
        migrations_to_rollback = [
            m for m in self.MIGRATIONS
            if target_version < m.version <= current
        ]
        
        if not migrations_to_rollback:
            logger.info("No migrations to rollback")
            return
        
        # Откатить миграции в обратном порядке
        for migration in sorted(migrations_to_rollback, key=lambda m: m.version, reverse=True):
            self._rollback_migration(migration)
        
        logger.info(f"✅ Rolled back from version {current} to {target_version}")
    
    def _rollback_migration(self, migration: Migration):
        """
        Откатить одну миграцию.
        
        Args:
            migration: Миграция для отката
        """
        logger.info(f"Rolling back migration {migration.version}: {migration.description}")
        
        try:
            # Начать транзакцию
            self.conn.execute("BEGIN")
            
            # Выполнить down SQL
            self.conn.executescript(migration.down_sql)
            
            # Удалить запись из таблицы миграций
            self.conn.execute("""
                DELETE FROM schema_migrations
                WHERE version = ?
            """, (migration.version,))
            
            # Закоммитить
            self.conn.commit()
            
            logger.info(f"✅ Migration {migration.version} rolled back successfully")
            
        except Exception as e:
            # Откатить при ошибке
            self.conn.rollback()
            logger.error(f"❌ Rollback of migration {migration.version} failed: {e}")
            raise Exception(f"Rollback of migration {migration.version} failed: {e}")
    
    # ========================================================================
    # VERIFICATION
    # ========================================================================
    
    def verify_integrity(self) -> bool:
        """
        Проверить целостность миграций через checksums.
        
        Returns:
            True если все миграции валидны
        """
        logger.info("Verifying migrations integrity...")
        
        try:
            # Получить примененные миграции
            cursor = self.conn.execute("""
                SELECT version, checksum
                FROM schema_migrations
                ORDER BY version
            """)
            
            applied_migrations = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Проверить каждую миграцию
            all_valid = True
            
            for migration in self.MIGRATIONS:
                if migration.version in applied_migrations:
                    stored_checksum = applied_migrations[migration.version]
                    
                    if stored_checksum != migration.checksum:
                        logger.error(
                            f"❌ Checksum mismatch for migration {migration.version}! "
                            f"Expected: {migration.checksum}, Got: {stored_checksum}"
                        )
                        all_valid = False
            
            if all_valid:
                logger.info("✅ All migrations integrity verified")
            else:
                logger.error("❌ Migrations integrity check failed!")
            
            return all_valid
            
        except Exception as e:
            logger.error(f"Failed to verify integrity: {e}")
            return False
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def get_migration_history(self) -> List[Dict]:
        """
        Получить историю примененных миграций.
        
        Returns:
            Список миграций с информацией
        """
        try:
            cursor = self.conn.execute("""
                SELECT version, description, applied_at, checksum
                FROM schema_migrations
                ORDER BY version
            """)
            
            history = []
            for row in cursor.fetchall():
                history.append({
                    'version': row[0],
                    'description': row[1],
                    'applied_at': row[2],
                    'checksum': row[3]
                })
            
            return history
            
        except Exception as e:
            logger.error(f"Failed to get migration history: {e}")
            return []
    
    def get_pending_migrations(self) -> List[Migration]:
        """
        Получить список pending миграций.
        
        Returns:
            Список миграций, которые еще не применены
        """
        current = self.get_current_version()
        
        return [
            m for m in self.MIGRATIONS
            if m.version > current
        ]


# ============================================================================
# CLI INTERFACE
# ============================================================================

def main():
    """CLI для управления миграциями"""
    import sys
    import sqlite3
    
    if len(sys.argv) < 3:
        print("Usage: python db_migrations_improved.py <db_path> <command> [args]")
        print()
        print("Commands:")
        print("  migrate [version]    - Apply migrations (up to version if specified)")
        print("  rollback <version>   - Rollback to specific version")
        print("  status               - Show current version and pending migrations")
        print("  verify               - Verify migrations integrity")
        print("  history              - Show migration history")
        sys.exit(1)
    
    db_path = sys.argv[1]
    command = sys.argv[2]
    
    # Подключиться к БД
    conn = sqlite3.connect(db_path)
    manager = MigrationManager(conn)
    
    # Выполнить команду
    if command == "migrate":
        target = int(sys.argv[3]) if len(sys.argv) > 3 else None
        manager.migrate(target_version=target)
    
    elif command == "rollback":
        if len(sys.argv) < 4:
            print("Error: rollback requires target version")
            sys.exit(1)
        target = int(sys.argv[3])
        manager.rollback(target_version=target)
    
    elif command == "status":
        current = manager.get_current_version()
        pending = manager.get_pending_migrations()
        
        print(f"Current version: {current}")
        print(f"Pending migrations: {len(pending)}")
        
        if pending:
            print("\nPending:")
            for m in pending:
                print(f"  v{m.version}: {m.description}")
    
    elif command == "verify":
        valid = manager.verify_integrity()
        sys.exit(0 if valid else 1)
    
    elif command == "history":
        history = manager.get_migration_history()
        
        print("Migration history:")
        for entry in history:
            print(f"  v{entry['version']}: {entry['description']}")
            print(f"    Applied: {entry['applied_at']}")
            print(f"    Checksum: {entry['checksum'][:16]}...")
            print()
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
    
    conn.close()


if __name__ == "__main__":
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    main()
