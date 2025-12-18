"""
Безопасное хранение credentials

Варианты:
1. Windows Credential Manager (keyring) - для пароля от ZIP
2. Supabase Storage - для зашифрованного архива (опционально)
3. Локальный ZIP + пароль в keyring (текущий подход, улучшенный)
"""

import os
import sys
import logging
from pathlib import Path
from typing import Optional
import json

logger = logging.getLogger(__name__)

# Пробуем импортировать keyring
try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False
    logger.warning("keyring не установлен. Используйте: pip install keyring")

KEYRING_SERVICE = "WorkTimeTracker"
KEYRING_CREDENTIALS_PASSWORD_KEY = "credentials_zip_password"
KEYRING_SUPABASE_STORAGE_KEY = "supabase_storage_credentials"


def get_password_from_keyring() -> Optional[str]:
    """Получить пароль от ZIP архива из Windows Credential Manager"""
    if not KEYRING_AVAILABLE:
        return None
    
    try:
        password = keyring.get_password(KEYRING_SERVICE, KEYRING_CREDENTIALS_PASSWORD_KEY)
        if password:
            logger.info("✓ Пароль загружен из Windows Credential Manager")
        return password
    except Exception as e:
        logger.warning(f"Не удалось загрузить пароль из keyring: {e}")
        return None


def save_password_to_keyring(password: str) -> bool:
    """Сохранить пароль от ZIP архива в Windows Credential Manager"""
    if not KEYRING_AVAILABLE:
        logger.error("keyring не доступен. Установите: pip install keyring")
        return False
    
    try:
        keyring.set_password(KEYRING_SERVICE, KEYRING_CREDENTIALS_PASSWORD_KEY, password)
        logger.info("✓ Пароль сохранен в Windows Credential Manager")
        return True
    except Exception as e:
        logger.error(f"Не удалось сохранить пароль в keyring: {e}")
        return False


def delete_password_from_keyring() -> bool:
    """Удалить пароль из Windows Credential Manager"""
    if not KEYRING_AVAILABLE:
        return False
    
    try:
        keyring.delete_password(KEYRING_SERVICE, KEYRING_CREDENTIALS_PASSWORD_KEY)
        logger.info("✓ Пароль удален из Windows Credential Manager")
        return True
    except Exception as e:
        logger.warning(f"Не удалось удалить пароль из keyring: {e}")
        return False


def get_credentials_json_from_supabase() -> Optional[str]:
    """
    Получить credentials JSON из Supabase (таблица или Storage)
    
    Приоритет:
    1. Таблица credentials (если есть)
    2. Supabase Storage (если настроено)
    
    Returns:
        JSON строка с credentials или None
    """
    try:
        # Убеждаемся, что переменные окружения загружены
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        
        if not supabase_url or not supabase_key:
            logger.debug("SUPABASE_URL и SUPABASE_KEY не заданы")
            return None
        
        from supabase_api import SupabaseAPI, SupabaseConfig
        
        # Создаем конфигурацию напрямую
        config = SupabaseConfig(url=supabase_url, key=supabase_key)
        api = SupabaseAPI(config)
        
        if not hasattr(api, 'client'):
            return None
        
        # Пробуем получить из таблицы credentials
        try:
            result = api.client.table('credentials').select('credentials_json').limit(1).execute()
            if result.data and len(result.data) > 0:
                creds_json = result.data[0].get('credentials_json')
                if creds_json:
                    logger.info("✓ Credentials загружены из таблицы Supabase")
                    return creds_json
        except Exception as e:
            logger.debug(f"Таблица credentials не найдена или недоступна: {e}")
        
        # Пробуем получить из Storage как JSON файл
        try:
            bucket_name = os.getenv("SUPABASE_STORAGE_BUCKET", "credentials")
            file_name = os.getenv("SUPABASE_STORAGE_FILE", "service_account.json")
            
            response = api.client.storage.from_(bucket_name).download(file_name)
            if response:
                if isinstance(response, bytes):
                    creds_json = response.decode('utf-8')
                else:
                    creds_json = response
                logger.info(f"✓ Credentials загружены из Supabase Storage: {bucket_name}/{file_name}")
                return creds_json
        except Exception as e:
            logger.debug(f"Не удалось загрузить из Supabase Storage: {e}")
        
        return None
    except Exception as e:
        logger.debug(f"Не удалось загрузить credentials из Supabase: {e}")
        return None


def get_credentials_from_supabase_storage() -> Optional[bytes]:
    """
    Получить зашифрованный архив credentials из Supabase Storage (legacy, для совместимости)
    
    Требует настройки:
    - SUPABASE_STORAGE_BUCKET в переменных окружения
    - SUPABASE_STORAGE_FILE в переменных окружения (имя файла в storage)
    """
    try:
        from supabase_api import get_supabase_api
        
        bucket_name = os.getenv("SUPABASE_STORAGE_BUCKET", "credentials")
        file_name = os.getenv("SUPABASE_STORAGE_FILE", "secret_creds.zip")
        
        api = get_supabase_api()
        if not hasattr(api, 'client'):
            return None
        
        # Загружаем файл из Supabase Storage
        response = api.client.storage.from_(bucket_name).download(file_name)
        
        if response:
            logger.info(f"✓ Credentials загружены из Supabase Storage: {bucket_name}/{file_name}")
            if isinstance(response, bytes):
                return response
            return response.encode('utf-8') if isinstance(response, str) else None
        
        return None
    except Exception as e:
        logger.debug(f"Не удалось загрузить credentials из Supabase Storage: {e}")
        return None


def save_credentials_json_to_supabase(credentials_json: str) -> bool:
    """
    Сохранить credentials JSON в Supabase (таблица или Storage)
    
    Args:
        credentials_json: JSON строка с credentials
    
    Returns:
        True если успешно сохранено
    """
    try:
        # Убеждаемся, что переменные окружения загружены
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        
        if not supabase_url or not supabase_key:
            logger.error("SUPABASE_URL и SUPABASE_KEY должны быть заданы в переменных окружения")
            logger.error("Проверьте .env файл или config.py")
            return False
        
        from supabase_api import SupabaseAPI, SupabaseConfig
        
        # Создаем конфигурацию напрямую
        config = SupabaseConfig(url=supabase_url, key=supabase_key)
        api = SupabaseAPI(config)
        
        if not hasattr(api, 'client'):
            return False
        
        # Пробуем сохранить в таблицу credentials
        try:
            # Проверяем существование записи
            existing = api.client.table('credentials').select('id').limit(1).execute()
            
            if existing.data and len(existing.data) > 0:
                # Обновляем существующую запись
                api.client.table('credentials').update({
                    'credentials_json': credentials_json,
                    'updated_at': 'now()'
                }).eq('id', existing.data[0]['id']).execute()
            else:
                # Создаем новую запись
                api.client.table('credentials').insert({
                    'credentials_json': credentials_json
                }).execute()
            
            logger.info("✓ Credentials сохранены в таблицу Supabase")
            return True
        except Exception as e:
            logger.debug(f"Не удалось сохранить в таблицу, пробуем Storage: {e}")
        
        # Fallback: сохраняем в Storage
        try:
            bucket_name = os.getenv("SUPABASE_STORAGE_BUCKET", "credentials")
            file_name = os.getenv("SUPABASE_STORAGE_FILE", "service_account.json")
            
            api.client.storage.from_(bucket_name).upload(
                file_name,
                credentials_json.encode('utf-8'),
                file_options={"content-type": "application/json", "upsert": "true"}
            )
            
            logger.info(f"✓ Credentials сохранены в Supabase Storage: {bucket_name}/{file_name}")
            return True
        except Exception as e:
            logger.error(f"Не удалось сохранить в Storage: {e}")
            return False
        
    except Exception as e:
        logger.error(f"Не удалось сохранить credentials в Supabase: {e}")
        return False


def save_credentials_to_supabase_storage(zip_data: bytes) -> bool:
    """
    Сохранить зашифрованный архив credentials в Supabase Storage (legacy, для совместимости)
    
    Требует настройки:
    - SUPABASE_STORAGE_BUCKET в переменных окружения
    - SUPABASE_STORAGE_FILE в переменных окружения (имя файла в storage)
    """
    try:
        from supabase_api import get_supabase_api
        
        bucket_name = os.getenv("SUPABASE_STORAGE_BUCKET", "credentials")
        file_name = os.getenv("SUPABASE_STORAGE_FILE", "secret_creds.zip")
        
        api = get_supabase_api()
        if not hasattr(api, 'client'):
            return False
        
        # Сохраняем файл в Supabase Storage
        api.client.storage.from_(bucket_name).upload(
            file_name,
            zip_data,
            file_options={"content-type": "application/zip", "upsert": "true"}
        )
        
        logger.info(f"✓ Credentials сохранены в Supabase Storage: {bucket_name}/{file_name}")
        return True
    except Exception as e:
        logger.error(f"Не удалось сохранить credentials в Supabase Storage: {e}")
        return False


def get_credentials_password() -> Optional[str]:
    """
    Получить пароль от credentials (приоритет: keyring > env)
    """
    # Сначала пробуем из keyring
    password = get_password_from_keyring()
    if password:
        return password
    
    # Fallback на переменную окружения
    password = os.getenv("CREDENTIALS_ZIP_PASSWORD", "")
    if password:
        logger.info("✓ Пароль загружен из переменной окружения")
        return password
    
    return None


def setup_credentials_storage(zip_path: Optional[Path] = None, password: Optional[str] = None) -> bool:
    """
    Настроить безопасное хранение credentials
    
    Args:
        zip_path: Путь к ZIP архиву (если None, будет использован стандартный)
        password: Пароль от архива (если None, будет запрошен или взят из keyring)
    
    Returns:
        True если настройка успешна
    """
    if not KEYRING_AVAILABLE:
        logger.warning("keyring не доступен. Рекомендуется установить для безопасного хранения пароля.")
        return False
    
    # Если пароль не передан, пробуем получить из keyring
    if not password:
        password = get_password_from_keyring()
    
    # Если пароль все еще не найден, запрашиваем у пользователя
    if not password:
        try:
            import getpass
            password = getpass.getpass("Введите пароль от архива credentials: ")
            if not password:
                logger.error("Пароль не может быть пустым")
                return False
        except Exception as e:
            logger.error(f"Не удалось запросить пароль: {e}")
            return False
    
    # Сохраняем пароль в keyring
    if save_password_to_keyring(password):
        logger.info("✓ Пароль сохранен в Windows Credential Manager")
        logger.info("  Теперь пароль не нужно указывать в .env файле")
        return True
    
    return False
