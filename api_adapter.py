"""
API Adapter - Переключение между Google Sheets и Supabase
Без изменения кода приложений!
"""
import os
import logging

# Загружаем переменные окружения из .env файла
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv не установлен

logger = logging.getLogger(__name__)

# ============================================================================
# EXCEPTION CLASSES
# ============================================================================

class SheetsAPIError(Exception):
    """Базовое исключение для ошибок API (Sheets или Supabase)"""
    pass

# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================

# Выберите бэкенд: "supabase" или "sheets"
USE_BACKEND = os.getenv("USE_BACKEND", "supabase")  # supabase или sheets

# Supabase credentials
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://jtgaobxbwibjcvasefzi.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")  # Будет взят из переменных окружения

# ============================================================================
# ADAPTER
# ============================================================================

if USE_BACKEND == "supabase":
    logger.info("🚀 Using Supabase backend")
    
    try:
        from supabase_api import SupabaseAPI, SupabaseConfig
        
        # Проверяем credentials
        if not SUPABASE_KEY:
            logger.warning("⚠️  SUPABASE_KEY not set, trying sheets_api...")
            USE_BACKEND = "sheets"
        else:
            # Создаем экземпляр
            config = SupabaseConfig(url=SUPABASE_URL, key=SUPABASE_KEY)
            _api_instance = SupabaseAPI(config)
            
            # Функция-фабрика для get_sheets_api()
            def get_sheets_api():
                """Возвращает Supabase API вместо Sheets API"""
                return _api_instance
            
            # Класс-алиас для SheetsAPI
            SheetsAPI = lambda: _api_instance
            
            logger.info(f"✅ Supabase API initialized: {SUPABASE_URL}")
            
    except ImportError as e:
        logger.error(f"❌ Failed to import supabase_api: {e}")
        logger.warning("⚠️  Falling back to Google Sheets")
        USE_BACKEND = "sheets"

if USE_BACKEND == "sheets":
    logger.info("📊 Using Google Sheets backend")
    
    from sheets_api import SheetsAPI, get_sheets_api
    
    logger.info("✅ Google Sheets API loaded")

# ============================================================================
# EXPORT
# ============================================================================

__all__ = ["get_sheets_api", "SheetsAPI", "SheetsAPIError", "USE_BACKEND"]


if __name__ == "__main__":
    print(f"Current backend: {USE_BACKEND}")
    
    if USE_BACKEND == "supabase":
        print(f"Supabase URL: {SUPABASE_URL}")
        print(f"Supabase KEY: {'***' + SUPABASE_KEY[-10:] if SUPABASE_KEY else 'NOT SET'}")
    
    api = get_sheets_api()
    print(f"API instance: {type(api).__name__}")
    
    try:
        users = api.get_users()
        print(f"✅ Loaded {len(users)} users")
    except Exception as e:
        print(f"❌ Error: {e}")
