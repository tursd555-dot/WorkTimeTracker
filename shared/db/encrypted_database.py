"""
Encrypted Database Wrapper

Обертка над SQLite с поддержкой прозрачного шифрования через SQLCipher.

Features:
- AES-256 шифрование
- Автоматическое управление ключами через системный keyring
- Миграция из незашифрованной БД в зашифрованную
- Ротация ключей шифрования
- Fallback на обычный SQLite если SQLCipher недоступен
- Проверка целостности БД

Использование:
    from shared.db import EncryptedDatabase
    
    # Создать/открыть зашифрованную БД
    db = EncryptedDatabase("data.db")
    conn = db.connect()
    
    # Работать как с обычной SQLite
    conn.execute("CREATE TABLE users (id INTEGER, name TEXT)")
    conn.execute("INSERT INTO users VALUES (1, 'Alice')")
    conn.commit()
    
    # Закрыть
    db.close()
    
    # Ротация ключа
    db.rotate_key()

Требования:
    pip install sqlcipher3-binary  # или sqlcipher3
    pip install keyring
    pip install cryptography

Автор: WorkTimeTracker Security Team
Дата: 2025-11-24
"""

import os
import logging
import keyring
from pathlib import Path
from typing import Optional
from cryptography.fernet import Fernet

# Попытка импорта SQLCipher
try:
    from sqlcipher3 import dbapi2 as sqlite
    HAS_SQLCIPHER = True
except ImportError:
    try:
        # Альтернативный импорт для некоторых систем
        import pysqlcipher3.dbapi2 as sqlite
        HAS_SQLCIPHER = True
    except ImportError:
        # Fallback на обычный SQLite
        import sqlite3 as sqlite
        HAS_SQLCIPHER = False
        logging.warning(
            "SQLCipher not available, using unencrypted SQLite. "
            "Install: pip install sqlcipher3-binary"
        )

# Настройка логирования
logger = logging.getLogger(__name__)


# ============================================================================
# CUSTOM EXCEPTIONS
# ============================================================================

class DatabaseError(Exception):
    """Базовое исключение для ошибок БД"""
    pass


class EncryptionError(DatabaseError):
    """Ошибка шифрования БД"""
    pass


class MigrationError(DatabaseError):
    """Ошибка миграции БД"""
    pass


# ============================================================================
# ENCRYPTED DATABASE
# ============================================================================

class EncryptedDatabase:
    """
    Обертка для SQLite с прозрачным шифрованием.
    
    Шифрование реализовано через SQLCipher:
    - AES-256 encryption
    - PBKDF2-HMAC-SHA512 для генерации ключа
    - 64000 итераций KDF
    - HMAC-SHA512 для проверки целостности
    
    Ключ шифрования хранится в системном keyring (безопасно).
    
    Attributes:
        db_path: Путь к файлу БД
        conn: Соединение с БД
        encryption_key: Ключ шифрования (из keyring)
    """
    
    # Константы для keyring
    KEYRING_SERVICE = "WorkTimeTracker"
    KEYRING_KEY_NAME = "db_encryption_key"
    
    def __init__(
        self,
        db_path: str,
        auto_migrate: bool = True,
        create_if_missing: bool = True
    ):
        """
        Инициализация зашифрованной БД.
        
        Args:
            db_path: Путь к файлу БД
            auto_migrate: Автоматически мигрировать из незашифрованной БД
            create_if_missing: Создать БД если не существует
        """
        self.db_path = Path(db_path)
        self.conn: Optional[sqlite.Connection] = None
        self.encryption_key: Optional[str] = None
        
        # Создать директорию если нужно
        if create_if_missing:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Получить или создать ключ шифрования
        self.encryption_key = self._get_or_create_key()
        
        # Проверить, нужна ли миграция
        if auto_migrate and HAS_SQLCIPHER:
            if self._is_unencrypted_db_exists():
                logger.info("Detected unencrypted database, starting migration...")
                self._migrate_from_unencrypted()
    
    def _get_or_create_key(self) -> str:
        """
        Получить ключ шифрования из keyring или создать новый.
        
        Returns:
            Ключ шифрования (base64 string)
        """
        # Попытка получить существующий ключ
        key = keyring.get_password(self.KEYRING_SERVICE, self.KEYRING_KEY_NAME)
        
        if key:
            logger.debug("Encryption key loaded from keyring")
            return key
        
        # Создать новый ключ
        new_key = Fernet.generate_key().decode()
        
        # Сохранить в keyring
        keyring.set_password(self.KEYRING_SERVICE, self.KEYRING_KEY_NAME, new_key)
        
        logger.info("Generated new database encryption key and stored in keyring")
        return new_key
    
    def connect(self) -> sqlite.Connection:
        """
        Подключиться к зашифрованной БД.
        
        Returns:
            Соединение с БД
            
        Raises:
            EncryptionError: Если ключ неверный или БД повреждена
        """
        if self.conn:
            return self.conn
        
        # Подключиться к БД
        self.conn = sqlite.connect(str(self.db_path))
        
        if HAS_SQLCIPHER:
            # Настроить шифрование
            self._configure_encryption()
            
            # Проверить, что ключ правильный
            try:
                self.conn.execute("SELECT count(*) FROM sqlite_master")
                logger.debug(f"Successfully connected to encrypted database: {self.db_path}")
            except sqlite.DatabaseError as e:
                raise EncryptionError(
                    f"Failed to decrypt database. "
                    f"The encryption key might be incorrect or the database is corrupted. "
                    f"Error: {e}"
                )
        else:
            logger.warning(
                f"Connected to UNENCRYPTED database: {self.db_path}. "
                f"Install sqlcipher3 for encryption support."
            )
        
        return self.conn
    
    def _configure_encryption(self):
        """Настроить параметры шифрования SQLCipher"""
        if not HAS_SQLCIPHER:
            return
        
        # Установить ключ шифрования
        self.conn.execute(f"PRAGMA key = '{self.encryption_key}'")
        
        # Настроить параметры шифрования (максимальная безопасность)
        self.conn.execute("PRAGMA cipher_page_size = 4096")
        self.conn.execute("PRAGMA kdf_iter = 64000")
        self.conn.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512")
        self.conn.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512")
        
        logger.debug("Encryption configured: AES-256, PBKDF2-HMAC-SHA512, 64000 iterations")
    
    def _is_unencrypted_db_exists(self) -> bool:
        """
        Проверить, существует ли незашифрованная версия БД.
        
        Returns:
            True если найдена незашифрованная БД, требующая миграции
        """
        if not self.db_path.exists():
            return False
        
        # Если уже есть .old файл, значит миграция уже была
        backup_path = self.db_path.with_suffix('.db.old')
        if backup_path.exists():
            return False
        
        # Попытаться открыть как незашифрованную БД
        try:
            test_conn = sqlite.connect(str(self.db_path))
            test_conn.execute("SELECT count(*) FROM sqlite_master")
            test_conn.close()
            
            # Если открылась без ключа - значит незашифрованная
            logger.info(f"Found unencrypted database: {self.db_path}")
            return True
            
        except sqlite.DatabaseError:
            # Либо уже зашифрована, либо повреждена
            return False
    
    def _migrate_from_unencrypted(self):
        """
        Мигрировать данные из незашифрованной БД в зашифрованную.
        
        Процесс:
        1. Переименовать старую БД в .db.old
        2. Создать новую зашифрованную БД
        3. Скопировать схему и данные
        4. Сохранить backup старой БД
        
        Raises:
            MigrationError: Если миграция не удалась
        """
        logger.info("Starting database migration to encrypted version...")
        
        backup_path = self.db_path.with_suffix('.db.old')
        temp_path = self.db_path.with_suffix('.db.tmp')
        
        try:
            # 1. Создать backup незашифрованной БД
            logger.info(f"Creating backup: {backup_path}")
            self.db_path.rename(backup_path)
            
            # 2. Подключиться к обеим БД
            old_conn = sqlite.connect(str(backup_path))
            new_conn = sqlite.connect(str(temp_path))
            
            # 3. Настроить шифрование для новой БД
            if HAS_SQLCIPHER:
                new_conn.execute(f"PRAGMA key = '{self.encryption_key}'")
                new_conn.execute("PRAGMA cipher_page_size = 4096")
                new_conn.execute("PRAGMA kdf_iter = 64000")
            
            # 4. Скопировать схему
            logger.info("Copying database schema...")
            schema = old_conn.execute(
                "SELECT sql FROM sqlite_master WHERE type IN ('table', 'index', 'trigger') AND sql IS NOT NULL"
            ).fetchall()
            
            for (sql,) in schema:
                try:
                    new_conn.execute(sql)
                except sqlite.OperationalError as e:
                    # Игнорировать ошибки для автоматических индексов
                    if 'already exists' not in str(e):
                        logger.warning(f"Schema copy warning: {e}")
            
            # 5. Скопировать данные
            logger.info("Copying data...")
            tables = old_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
            
            total_rows = 0
            for (table_name,) in tables:
                logger.debug(f"Copying table: {table_name}")
                
                # Получить все данные
                data = old_conn.execute(f"SELECT * FROM {table_name}").fetchall()
                
                if data:
                    # Узнать количество колонок
                    columns_count = len(data[0])
                    placeholders = ','.join(['?'] * columns_count)
                    
                    # Вставить данные
                    new_conn.executemany(
                        f"INSERT INTO {table_name} VALUES ({placeholders})",
                        data
                    )
                    
                    total_rows += len(data)
                    logger.debug(f"Copied {len(data)} rows from {table_name}")
            
            # 6. Commit и закрыть
            new_conn.commit()
            old_conn.close()
            new_conn.close()
            
            # 7. Переименовать временную БД в основную
            temp_path.rename(self.db_path)
            
            logger.info(f"✅ Migration completed successfully!")
            logger.info(f"   Copied {total_rows} total rows")
            logger.info(f"   Old database backed up to: {backup_path}")
            logger.info(f"   You can delete {backup_path} after verifying the new database")
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            
            # Попытаться восстановить
            if temp_path.exists():
                temp_path.unlink()
            
            if backup_path.exists() and not self.db_path.exists():
                logger.info("Restoring original database...")
                backup_path.rename(self.db_path)
            
            raise MigrationError(f"Database migration failed: {e}")
    
    def rotate_key(self, new_key: Optional[str] = None):
        """
        Ротация ключа шифрования.
        
        Создает новый ключ и перешифровывает всю БД.
        
        Args:
            new_key: Новый ключ (если None, генерируется автоматически)
            
        Raises:
            EncryptionError: Если ротация не удалась
        """
        if not HAS_SQLCIPHER:
            logger.warning("Key rotation not available without SQLCipher")
            return
        
        logger.info("Starting encryption key rotation...")
        
        # Генерировать новый ключ если не указан
        if new_key is None:
            new_key = Fernet.generate_key().decode()
        
        try:
            # Подключиться с текущим ключом
            conn = self.connect()
            
            # Перешифровать с новым ключом
            logger.info("Re-encrypting database with new key...")
            conn.execute(f"PRAGMA rekey = '{new_key}'")
            conn.commit()
            
            # Сохранить новый ключ в keyring
            keyring.set_password(self.KEYRING_SERVICE, self.KEYRING_KEY_NAME, new_key)
            self.encryption_key = new_key
            
            logger.info("✅ Encryption key rotated successfully")
            
        except Exception as e:
            raise EncryptionError(f"Key rotation failed: {e}")
    
    def verify_integrity(self) -> bool:
        """
        Проверить целостность БД.
        
        Returns:
            True если БД в порядке, False если есть проблемы
        """
        try:
            conn = self.connect()
            
            # SQLCipher integrity check
            if HAS_SQLCIPHER:
                result = conn.execute("PRAGMA cipher_integrity_check").fetchone()
                if result and result[0] == 'ok':
                    logger.info("Database integrity check: OK")
                    return True
                else:
                    logger.error(f"Database integrity check failed: {result}")
                    return False
            else:
                # Обычный SQLite integrity check
                result = conn.execute("PRAGMA integrity_check").fetchone()
                if result and result[0] == 'ok':
                    logger.info("Database integrity check: OK")
                    return True
                else:
                    logger.error(f"Database integrity check failed: {result}")
                    return False
                    
        except Exception as e:
            logger.error(f"Integrity check failed: {e}")
            return False
    
    def get_stats(self) -> dict:
        """
        Получить статистику БД.
        
        Returns:
            Словарь со статистикой (размер, количество таблиц, и т.д.)
        """
        stats = {
            'path': str(self.db_path),
            'exists': self.db_path.exists(),
            'encrypted': HAS_SQLCIPHER,
            'size_bytes': self.db_path.stat().st_size if self.db_path.exists() else 0
        }
        
        if self.conn:
            try:
                # Количество таблиц
                tables = self.conn.execute(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
                ).fetchone()[0]
                stats['tables_count'] = tables
                
                # Размер страницы
                page_size = self.conn.execute("PRAGMA page_size").fetchone()[0]
                stats['page_size'] = page_size
                
                # Количество страниц
                page_count = self.conn.execute("PRAGMA page_count").fetchone()[0]
                stats['page_count'] = page_count
                
            except Exception as e:
                logger.warning(f"Failed to get detailed stats: {e}")
        
        return stats
    
    def close(self):
        """Закрыть соединение с БД"""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.debug(f"Database connection closed: {self.db_path}")
    
    def __enter__(self):
        """Context manager support"""
        return self.connect()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager support"""
        self.close()
    
    def __repr__(self):
        """String representation"""
        encrypted = "encrypted" if HAS_SQLCIPHER else "unencrypted"
        connected = "connected" if self.conn else "disconnected"
        return f"<EncryptedDatabase({self.db_path}, {encrypted}, {connected})>"


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_encrypted_db(db_path: str) -> EncryptedDatabase:
    """
    Создать новую зашифрованную БД.
    
    Args:
        db_path: Путь к файлу БД
        
    Returns:
        Экземпляр EncryptedDatabase
    """
    return EncryptedDatabase(db_path, auto_migrate=True, create_if_missing=True)


def is_sqlcipher_available() -> bool:
    """
    Проверить, доступен ли SQLCipher.
    
    Returns:
        True если SQLCipher установлен, False иначе
    """
    return HAS_SQLCIPHER


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

if __name__ == "__main__":
    """
    Пример использования EncryptedDatabase.
    
    Запуск:
        python shared/db/encrypted_database.py
    """
    
    # Настройка логирования
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 80)
    print("EncryptedDatabase - Usage Example")
    print("=" * 80)
    print()
    
    # Проверка SQLCipher
    if HAS_SQLCIPHER:
        print("✅ SQLCipher is available")
    else:
        print("⚠️  SQLCipher is NOT available, using unencrypted SQLite")
    print()
    
    # Создать тестовую БД
    db_path = "test_encrypted.db"
    print(f"Creating encrypted database: {db_path}")
    
    db = EncryptedDatabase(db_path)
    conn = db.connect()
    
    # Создать таблицу
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL
        )
    """)
    
    # Вставить данные
    conn.execute("INSERT INTO users (name, email) VALUES (?, ?)", ("Alice", "alice@example.com"))
    conn.execute("INSERT INTO users (name, email) VALUES (?, ?)", ("Bob", "bob@example.com"))
    conn.commit()
    
    print("✅ Created table and inserted data")
    print()
    
    # Прочитать данные
    print("Reading data:")
    cursor = conn.execute("SELECT * FROM users")
    for row in cursor:
        print(f"  {row}")
    print()
    
    # Статистика
    print("Database statistics:")
    stats = db.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    print()
    
    # Проверка целостности
    print("Integrity check:")
    if db.verify_integrity():
        print("  ✅ OK")
    else:
        print("  ❌ FAILED")
    print()
    
    # Закрыть
    db.close()
    print("✅ Database closed")
    print()
    
    # Очистка
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"✅ Cleaned up test database: {db_path}")
    
    print()
    print("=" * 80)
