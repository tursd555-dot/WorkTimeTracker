"""
API Adapter - Переключение между Google Sheets и Supabase
Без изменения кода приложений!
"""
import os
import logging

logger = logging.getLogger(__name__)

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
# BREAK MANAGER FACTORY
# ============================================================================

_break_manager_instance = None


def get_break_manager():
    """
    Фабричный метод для получения правильного BreakManager

    Автоматически выбирает BreakManagerSupabase или BreakManager
    в зависимости от текущего бэкенда.
    """
    global _break_manager_instance

    if _break_manager_instance is not None:
        return _break_manager_instance

    api = get_sheets_api()

    if USE_BACKEND == "supabase":
        try:
            from admin_app.break_manager_supabase import BreakManagerSupabase
            _break_manager_instance = BreakManagerSupabase(api)
            logger.info("✅ BreakManagerSupabase initialized")
        except ImportError as e:
            logger.warning(f"Failed to import BreakManagerSupabase: {e}, using original")
            from admin_app.break_manager import BreakManager
            _break_manager_instance = BreakManager(api)
    else:
        from admin_app.break_manager import BreakManager
        _break_manager_instance = BreakManager(api)
        logger.info("✅ BreakManager (Sheets) initialized")

    return _break_manager_instance


def reset_break_manager():
    """Сбрасывает кэшированный BreakManager (для тестов)"""
    global _break_manager_instance
    _break_manager_instance = None


# ============================================================================
# EXPORT
# ============================================================================

__all__ = ["get_sheets_api", "SheetsAPI", "USE_BACKEND", "get_break_manager"]


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

    # Тест BreakManager
    print("\n--- Testing BreakManager ---")
    try:
        break_mgr = get_break_manager()
        print(f"✅ BreakManager: {type(break_mgr).__name__}")

        # Тестируем получение статуса (без реального email)
        status = break_mgr.get_break_status("test@example.com")
        print(f"✅ Break status: {status}")
    except Exception as e:
        print(f"❌ BreakManager error: {e}")
