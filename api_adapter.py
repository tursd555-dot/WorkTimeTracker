"""
API Adapter - переключение между Google Sheets и Supabase.

Ключевое правило:
- если в config.py USE_SUPABASE=True, НЕ делаем тихий fallback в sheets,
  чтобы не получать ложную ошибку "Пользователь не найден".
"""
import os
import logging
from pathlib import Path

# Загружаем .env файл ПЕРЕД чтением переменных окружения
try:
    from dotenv import load_dotenv

    env_candidates = [
        Path.cwd() / ".env",
        Path(__file__).parent / ".env",
    ]

    for env_path in env_candidates:
        if env_path.exists():
            load_dotenv(env_path, override=False)
            break
    else:
        load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)

# Пытаемся прочитать переключатель из config.py (если доступен).
CONFIG_USE_SUPABASE = None
try:
    from config import USE_SUPABASE as CONFIG_USE_SUPABASE  # type: ignore
except Exception:
    CONFIG_USE_SUPABASE = None

# Выбор backend: config имеет приоритет над ENV.
if CONFIG_USE_SUPABASE is True:
    USE_BACKEND = "supabase"
elif CONFIG_USE_SUPABASE is False:
    USE_BACKEND = "sheets"
else:
    USE_BACKEND = os.getenv("USE_BACKEND", "supabase").strip().lower() or "supabase"

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://jtgaobxbwibjcvasefzi.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

logger.debug(
    "Adapter config: USE_BACKEND=%s (config=%s), SUPABASE_URL=%s, SUPABASE_KEY=%s",
    USE_BACKEND,
    CONFIG_USE_SUPABASE,
    SUPABASE_URL,
    "SET" if SUPABASE_KEY else "NOT SET",
)

if USE_BACKEND == "supabase":
    logger.info("🚀 Using Supabase backend")
    from supabase_api import SupabaseAPI, SupabaseConfig

    if not SUPABASE_KEY:
        # Явная ошибка вместо тихого fallback в sheets.
        raise RuntimeError(
            "SUPABASE_KEY is not set while USE_SUPABASE=True. "
            "Set SUPABASE_KEY in environment/.env."
        )

    _api_instance = SupabaseAPI(SupabaseConfig(url=SUPABASE_URL, key=SUPABASE_KEY))

    def get_sheets_api():
        """Возвращает Supabase API вместо Sheets API."""
        return _api_instance

    SheetsAPI = lambda: _api_instance

    class SheetsAPIError(Exception):
        """Исключение для совместимости интерфейса."""
        def __init__(self, message: str, is_retryable: bool = False, details: str = ""):
            self.message = message
            self.is_retryable = is_retryable
            self.details = details
            super().__init__(message)

else:
    logger.info("📊 Using Google Sheets backend")
    from sheets_api import SheetsAPI, get_sheets_api, SheetsAPIError
    logger.info("✅ Google Sheets API loaded")

__all__ = ["get_sheets_api", "SheetsAPI", "SheetsAPIError", "USE_BACKEND"]
