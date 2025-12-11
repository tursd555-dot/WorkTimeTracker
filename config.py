
# config.py  v1.2.0-security-patch  (полный, без вырезаний)
from __future__ import annotations

import hashlib
import io
import os
import platform
import stat
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Generator, List, Optional, Set, Union

import pyzipper
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# ============================================================================
# ПЕРЕКЛЮЧЕНИЕ НА SUPABASE (v20.5)
# ============================================================================
USE_SUPABASE = True  # True = Supabase, False = Google Sheets

if USE_SUPABASE:
    # Credentials загружаются из .env файла через load_dotenv()
    # SUPABASE_URL и SUPABASE_KEY должны быть установлены в .env

    # Импортируем Supabase API вместо Sheets API
    from supabase_api import get_supabase_api
    
    # Создаем алиас для совместимости
    def get_sheets_api():
        return get_supabase_api()
    
    SheetsAPI = type('SheetsAPI', (), {'__init__': lambda self: get_supabase_api()})

print(f"✅ Использование: {'Supabase' if USE_SUPABASE else 'Google Sheets'}")
# ============================================================================

# ==================== Загрузка переменных окружения из .env ====================
from dotenv import load_dotenv

def _load_env() -> None:
    """
    Ищем .env там, где запущен EXE (или распаковка PyInstaller),
    затем в текущей папке и рядом с модулем.
    """
    candidates = []
    if getattr(sys, "frozen", False):
        # onedir/onefile
        candidates.append(Path(sys.executable).parent / ".env")
        if hasattr(sys, "_MEIPASS"):
            candidates.append(Path(sys._MEIPASS) / ".env")
    candidates += [Path.cwd() / ".env", Path(__file__).parent / ".env"]
    for p in candidates:
        if p.exists():
            load_dotenv(p)
            return
    # на всякий случай — стандартный поиск
    load_dotenv()

_load_env()

# ==================== Импорт для работы с зашифрованным credentials ====================
import tempfile

# ==================== Базовые настройки ====================
if getattr(sys, 'frozen', False):
    # Режим сборки (PyInstaller)
    BASE_DIR = Path(sys.executable).parent
else:
    # Режим разработки
    BASE_DIR = Path(__file__).parent.absolute()

# --- Исправлено: Создаем LOG_DIR сразу ---
if platform.system() == "Windows":
    LOG_DIR = Path(os.getenv('APPDATA')) / "WorkTimeTracker" / "logs"
else:
    LOG_DIR = Path.home() / ".local" / "share" / "WorkTimeTracker" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)  # Создаем при импорте модуля
# ---

# ==================== Пути к файлам (credentials) ====================
# Приоритет: ZIP рядом с EXE (+ пароль) → иначе JSON из .env
CREDENTIALS_ZIP_NAME = os.getenv("CREDENTIALS_ZIP_NAME", "secret_creds.zip")
CREDENTIALS_ZIP = BASE_DIR / CREDENTIALS_ZIP_NAME
CREDENTIALS_ZIP_PASSWORD = os.getenv("CREDENTIALS_ZIP_PASSWORD", "")
GOOGLE_CREDENTIALS_FILE_ENV = (os.getenv("GOOGLE_CREDENTIALS_FILE") or "").strip()

# Детектируем режимы
USE_ZIP = bool(CREDENTIALS_ZIP.exists() and CREDENTIALS_ZIP_PASSWORD)
USE_JSON_DIRECT = bool(GOOGLE_CREDENTIALS_FILE_ENV and not USE_ZIP)

if USE_ZIP:
    CREDENTIALS_ZIP_PASSWORD = CREDENTIALS_ZIP_PASSWORD.encode("utf-8")
elif not USE_JSON_DIRECT:
    # Ни ZIP+пароля, ни JSON-пути
    raise RuntimeError(
        "Учетные данные не найдены. Положи зашифрованный архив рядом с EXE "
        f"({CREDENTIALS_ZIP_NAME}) и укажи CREDENTIALS_ZIP_PASSWORD в .env, "
        "или укажи GOOGLE_CREDENTIALS_FILE."
    )

# --- Ленивая загрузка credentials ---
_CRED_MEMORY: Dict[int, tuple] = {}
_CRED_TTL = 60 * 60
_MASTER_KEY = os.getenv("CREDENTIALS_MASTER_KEY", "")

def _derive_key(password: str) -> bytes:
    return hashlib.pbkdf2_hmac('sha256', password.encode(), b'stable salt', 100_000, 32)

def _decrypt(data: bytes, key: bytes) -> bytes:
    nonce, ct = data[:12], data[12:]
    return AESGCM(key).decrypt(nonce, ct, b"")

def _encrypt(data: bytes, key: bytes) -> bytes:
    import os
    nonce = os.urandom(12)
    return nonce + AESGCM(key).encrypt(nonce, data, b"")

@contextmanager
def credentials_path() -> Generator[Path, None, None]:
    """
    Возвращает путь к service_account.json.
    Приоритет:
      1) ZIP рядом с EXE + CREDENTIALS_ZIP_PASSWORD
      2) GOOGLE_CREDENTIALS_FILE из .env (может быть относительным путём)
    Используйте: with credentials_path() as p: ...
    """
    global _CRED_MEMORY
    if USE_ZIP:
        zip_path = CREDENTIALS_ZIP
        if not zip_path.exists():
            raise FileNotFoundError(f"Archive not found: {zip_path}")
        cache_key = zip_path.stat().st_mtime
        cached = _CRED_MEMORY.get(cache_key)
        if cached and time.time() - cached[0] < _CRED_TTL:
            json_bytes = cached[1]
        else:
            password = CREDENTIALS_ZIP_PASSWORD
            with pyzipper.AESZipFile(zip_path) as zf:
                zf.pwd = password
                json_bytes = zf.read("service_account.json")
            if _MASTER_KEY:
                json_bytes = _encrypt(json_bytes, bytes.fromhex(_MASTER_KEY))
            _CRED_MEMORY[cache_key] = (time.time(), json_bytes)

        with tempfile.NamedTemporaryFile(mode='wb', suffix='.json', delete=False) as tmp:
            tmp.write(_decrypt(json_bytes, bytes.fromhex(_MASTER_KEY)) if _MASTER_KEY else json_bytes)
            tmp_name = Path(tmp.name)
        try:
            yield tmp_name
        finally:
            tmp_name.unlink(missing_ok=True)
    elif USE_JSON_DIRECT:
        direct = Path(GOOGLE_CREDENTIALS_FILE_ENV)
        if not direct.is_absolute():
            direct = (BASE_DIR / direct).resolve()
        if not direct.exists():
            raise FileNotFoundError(f"GOOGLE_CREDENTIALS_FILE не найден: {direct}")
        yield direct
    else:
        raise RuntimeError("Не удалось определить путь к credentials (ни ZIP, ни JSON).")

def get_credentials_file() -> Path:
    """Обратная совместимость: получить путь к JSON (извлечёт при первом вызове)."""
    with credentials_path() as p:
        return Path(p)

# ==================== Пути локальной SQLite-БД (основной и резервный) ====================
# Основной — рядом с проектом (local_backup.db),
# Резервный — в профиле пользователя: ~/WorkTimeTracker/local_backup.db
_BASE_DIR = Path(__file__).resolve().parent
_USER_DIR = Path.home() / "WorkTimeTracker"
# ==================== Пути локальной SQLite-БД ====================
LOCAL_DB_PATH = BASE_DIR / 'local_backup.db'

# Строки путей (без создания файлов/директорий при импорте)
DB_MAIN_PATH = str((_BASE_DIR / "local_backup.db").resolve())
DB_FALLBACK_PATH = str((_USER_DIR / "local_backup.db").resolve())

def get_local_db_paths():
    """Вернуть кортеж (основной_путь, резервный_путь)."""
    return DB_MAIN_PATH, DB_FALLBACK_PATH

# ==================== Настройки Google Sheets ====================
# Имя книги может использоваться в UI/логах; доступ к книге — по ID (через sheets_api)
GOOGLE_SHEET_NAME = "WorkLog"
USERS_SHEET = "Users"
WORKLOG_SHEET = "WorkLog"
ARCHIVE_SHEET = "Archive"
ACTIVE_SESSIONS_SHEET = "ActiveSessions"
SHIFT_CALENDAR_SHEET = ""  # опционально: 'ShiftCalendar' / 'График' если появится лист графика

# Break management sheets (v20.3 - unified with AdminApp Dashboard)
BREAK_SCHEDULES_SHEET = "BreakSchedules"
USER_BREAK_ASSIGNMENTS_SHEET = "UserBreakAssignments"
BREAK_VIOLATIONS_SHEET = "Violations"     # v20.3: renamed from BreakViolations
BREAK_USAGE_LOG_SHEET = "BreakLog"       # v20.3: renamed from BreakUsageLog

# Break type constants
BREAK_TYPE_SHORT = "Перерыв"
BREAK_TYPE_LUNCH = "Обед"

# Violation types
VIOLATION_EARLY_START = "Ранний уход"
VIOLATION_LATE_RETURN = "Поздний возврат"
VIOLATION_EXCESS_COUNT = "Превышение количества"
VIOLATION_WRONG_WINDOW = "Вне допустимого окна"

# ==================== Лимиты API ====================
GOOGLE_API_LIMITS: Dict[str, int] = {
    'max_requests_per_minute': 60,
    'max_rows_per_request': 50,
    'max_cells_per_request': 10000,
    'daily_limit': 100000
}

# ==================== Настройки синхронизации ====================
SYNC_INTERVAL: int = 10  # ✅ Первый цикл через 10 секунд для быстрого старта
SYNC_BATCH_SIZE: int = 50  # Размер пакета для обычной синхронизации (не приоритетной)
API_MAX_RETRIES: int = 3  # ✅ Уменьшено для быстрого детектирования offline
API_DELAY_SECONDS: float = 1.0  # Базовый интервал между запросами
SYNC_RETRY_STRATEGY: List[int] = [60, 300, 900, 1800, 3600]  # 1, 5, 15, 30, 60 минут

# Интервалы синхронизации для разных режимов работы
SYNC_INTERVAL_ONLINE: int = 10  # ✅ 10 секунд при нормальной работе - быстрые циклы!
SYNC_INTERVAL_OFFLINE_RECOVERY: int = 5  # ✅ 5 секунд при восстановлении - быстрая очистка очереди!

# ==================== Группы обработки ====================
GROUP_MAPPING: Dict[str, str] = {
    "call": "Входящие",
    "appointment": "Запись",
    "mail": "Почта",
    "dental": "Стоматология",
    "default": "Входящие"
}

# ==================== Статусы системы ====================
STATUSES: List[str] = [
    "В работе",
    "Чат",
    "Аудио",
    "Запись",
    "Анкеты",
    "Перерыв",
    "Обед",
    "ЦИТО",
    "Обучение"
]

# Группы для интерфейса (раскладка кнопок)
STATUS_GROUPS: List[List[str]] = [
    ["В работе", "Чат", "Аудио", "Запись", "Анкеты"],   # Основная работа
    ["Перерыв", "Обед"],                                # Перерывы
    ["ЦИТО", "Обучение"]                                # Специальные
]

CONFIRMATION_STATUSES: Set[str] = {"Перерыв", "Обед", "ЦИТО"}
RESTRICTED_STATUSES_FIRST_2H: Set[str] = {"Перерыв", "Обед"}
MAX_COMMENT_LENGTH: int = 500
MAX_HISTORY_DAYS: int = 30

# ==================== Настройки безопасности ====================
PASSWORD_MIN_LENGTH: int = 8
SESSION_TIMEOUT: int = 3600  # секунды
ALLOWED_DOMAINS: List[str] = ["company.com", "sberhealth.ru"]

# ==================== Telegram уведомления ====================
# Имена переменных должны быть КЛЮЧАМИ, а не значениями.
# В .env должно быть:
#   TELEGRAM_BOT_TOKEN=123456:ABC...
#   TELEGRAM_ADMIN_CHAT_ID=1053909260
#   TELEGRAM_BROADCAST_CHAT_ID=-1001234567890   (опционально)
#   TELEGRAM_MONITORING_CHAT_ID=-1002917784307
TELEGRAM_BOT_TOKEN: str | None = os.getenv("TELEGRAM_BOT_TOKEN") or None
TELEGRAM_ADMIN_CHAT_ID: str | None = os.getenv("TELEGRAM_ADMIN_CHAT_ID") or None
TELEGRAM_BROADCAST_CHAT_ID: str | None = os.getenv("TELEGRAM_BROADCAST_CHAT_ID") or None
TELEGRAM_MONITORING_CHAT_ID: str | None = os.getenv("TELEGRAM_MONITORING_CHAT_ID") or "-1002917784307"

# Настройки лимитов для мониторинга
BREAK_LIMIT_MINUTES: int = int(os.getenv("BREAK_LIMIT_MINUTES", "15"))  # лимит перерыва
LUNCH_LIMIT_MINUTES: int = int(os.getenv("LUNCH_LIMIT_MINUTES", "60"))  # лимит обеда

# Анти-спам ключей (минут между одинаковыми событиями)
TELEGRAM_MIN_INTERVAL_SEC: int = int(os.getenv("TELEGRAM_MIN_INTERVAL_SEC", "600"))
# Тихие уведомления по умолчанию
TELEGRAM_SILENT: bool = os.getenv("TELEGRAM_SILENT", "0") == "1"
TELEGRAM_ALERTS_ENABLED: bool = bool(TELEGRAM_BOT_TOKEN and (TELEGRAM_ADMIN_CHAT_ID or TELEGRAM_BROADCAST_CHAT_ID or TELEGRAM_MONITORING_CHAT_ID))

# ==================== Архивирование ====================
ARCHIVE_DELETE_SOURCE_ROWS: bool = os.getenv("ARCHIVE_DELETE_SOURCE_ROWS", "1") == "1"

# ==================== Пороги правил уведомлений ====================
# опоздание на логин, минут
LATE_LOGIN_MINUTES: int = int(os.getenv("LATE_LOGIN_MINUTES", "15"))
# слишком частая смена статусов, штук за час
OVER_STATUS_MAX_PER_HOUR: int = int(os.getenv("OVER_STATUS_MAX_PER_HOUR", "10"))
# порог очереди несинхрона
NOTIFY_QUEUE_THRESHOLD: int = int(os.getenv("NOTIFY_QUEUE_THRESHOLD", "50"))

# ==================== Настройки мониторинга и логирования ====================
LOG_LEVEL: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_ROTATION_SIZE: int = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT: int = 5  # Количество резервных копий логов

# ==================== Утилиты для работы с переменными окружения ====================
def _bool_env(name: str, default: bool) -> bool:
    """Безопасно преобразует переменную окружения в булево значение."""
    v = os.getenv(name)
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "y", "да")

def _int_env(name: str, default: int) -> int:
    """Безопасно преобразует переменную окружения в целое число."""
    try:
        return int(os.getenv(name, str(default)))
    except (ValueError, TypeError):
        return default

# ==================== Telegram rules toggles & thresholds ====================
# Персональные оповещения сотрудникам
PERSONAL_RULES_ENABLED: bool = _bool_env("PERSONAL_RULES_ENABLED", True)
PERSONAL_WINDOW_MIN: int = _int_env("PERSONAL_WINDOW_MIN", 60)                  # окно в минутах
PERSONAL_STATUS_LIMIT_PER_WINDOW: int = _int_env("PERSONAL_STATUS_LIMIT", 12)   # порог событий/окно

# Служебные оповещения админу
SERVICE_ALERTS_ENABLED: bool = _bool_env("SERVICE_ALERTS_ENABLED", True)
SERVICE_ALERT_MIN_SECONDS: int = _int_env("SERVICE_ALERT_MIN_SECONDS", 900)     # антиспам: не чаще, чем раз в 15 минут

# ==================== Валидация конфигурации ====================
def validate_config() -> None:
    """Проверяет корректность конфигурации при запуске."""
    errors = []
    
    # Проверяем наличие credentials в одном из режимов
    try:
        with credentials_path() as creds_file:
            if not creds_file.exists():
                errors.append(f"Файл учетных данных не найден: {creds_file}")
    except Exception as e:
        errors.append(f"Ошибка доступа к учетным данным: {e}")

    # Проверим выбранную стратегию
    if USE_ZIP:
        if not CREDENTIALS_ZIP.exists():
            errors.append(f"Архив с ключом не найден: {CREDENTIALS_ZIP}")
        if not CREDENTIALS_ZIP_PASSWORD:
            errors.append("CREDENTIALS_ZIP_PASSWORD не задан в .env")
    elif not USE_JSON_DIRECT:
        errors.append(
            "Ни ZIP+пароль, ни GOOGLE_CREDENTIALS_FILE не заданы. "
            "Ожидается архив рядом с EXE и CREDENTIALS_ZIP_PASSWORD в .env, "
            "или переменная GOOGLE_CREDENTIALS_FILE."
        )
    
    if not LOG_DIR.exists():
        try:
            LOG_DIR.mkdir(parents=True)
        except Exception as e:
            errors.append(f"Не удалось создать директорию логов: {e}")
    
    if not GROUP_MAPPING.get("default"):
        errors.append("Не определена группы по умолчанию в GROUP_MAPPING")
    
    # Проверяем стратегию ретраев
    if len(SYNC_RETRY_STRATEGY) < 3:
        errors.append("Стратегия повторных попыток синхронизации должна содержать минимум 3 интервала")
    
    if max(SYNC_RETRY_STRATEGY) < 1800:
        errors.append("Максимальный интервал повторных попыток должен быть не менее 1800 секунд (30 минут)")
    
    if errors:
        raise ValueError("Ошибки конфигурации:\n- " + "\n- ".join(errors))

# ==================== Утилиты для работы с конфигурации ====================
def get_sync_retry_delay(attempt: int) -> int:
    """
    Возвращает задержку для повторной попытки синхронизации.
    
    Args:
        attempt: Номер попытки (начиная с 0)
    
    Returns:
        Задержка в секундах
    """
    if attempt < len(SYNC_RETRY_STRATEGY):
        return SYNC_RETRY_STRATEGY[attempt]
    return SYNC_RETRY_STRATEGY[-1]  # Последний интервал для всех последующих попыток

def should_retry_sync(error: Exception) -> bool:
    """
    Определяет, следует ли повторять попытку синхронизации при данной ошибке.
    
    Args:
        error: Исключение, которое произошло
        
    Returns:
        True если следует повторить, False если нет
    """
    # Ошибки, при которых стоит повторять попытку
    retryable_errors = [
        "ConnectionError",
        "TimeoutError",
        "HttpError",
        "ServiceUnavailable",
        "RateLimitExceeded"
    ]
    
    error_name = type(error).__name__
    return any(retryable in error_name for retryable in retryable_errors)

# ==================== Инициализация конфигурации ====================
try:
    validate_config()
    print("✓ Конфигурация успешно проверена")
    print(f"✓ Стратегия повторных попыток: {SYNC_RETRY_STRATEGY}")
    print(f"✓ Мониторинг chat ID: {TELEGRAM_MONITORING_CHAT_ID}")
    print(f"✓ Лимиты: Перерыв={BREAK_LIMIT_MINUTES}мин, Обед={LUNCH_LIMIT_MINUTES}мин")
except Exception as e:
    print(f"✗ Ошибка конфигурации: {e}")
    raise

# ==================== Утилиты для PyInstaller ====================
def get_resource_path(relative_path: str) -> str:
    """Возвращает абсолютный путь к ресурсу, учитывая PyInstaller."""
    if hasattr(sys, '_MEIPASS'):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = BASE_DIR
    return str(base_path / relative_path)

# ==================== Константы для тестирования ====================
if __name__ == "__main__":
    print(f"BASE_DIR: {BASE_DIR}")
    print(f"LOG_DIR: {LOG_DIR}")
    print(f"CREDENTIALS_ZIP: {CREDENTIALS_ZIP}")
    print(f"SYNC_RETRY_STRATEGY: {SYNC_RETRY_STRATEGY}")
    print(f"Максимальная задержка: {max(SYNC_RETRY_STRATEGY)} секунд ({max(SYNC_RETRY_STRATEGY)/60} минут)")
    
    # Тестируем ленивую загрузку credentials
    try:
        with credentials_path() as creds:
            print(f"✓ Credentials file: {creds}")
            print(f"✓ File exists: {creds.exists()}")
    except Exception as e:
        print(f"✗ Error accessing credentials: {e}")
    
    # Тестируем новые настройки правил
    print(f"PERSONAL_RULES_ENABLED: {PERSONAL_RULES_ENABLED}")
    print(f"PERSONAL_WINDOW_MIN: {PERSONAL_WINDOW_MIN}")
    print(f"PERSONAL_STATUS_LIMIT_PER_WINDOW: {PERSONAL_STATUS_LIMIT_PER_WINDOW}")
    print(f"SERVICE_ALERTS_ENABLED: {SERVICE_ALERTS_ENABLED}")
    print(f"SERVICE_ALERT_MIN_SECONDS: {SERVICE_ALERT_MIN_SECONDS}")
    
    # Тестируем пути к БД
    main_db, fallback_db = get_local_db_paths()
    print(f"Основная БД: {main_db}")
    print(f"Резервная БД: {fallback_db}")
    
    # Тестируем новые настройки мониторинга
    print(f"TELEGRAM_MONITORING_CHAT_ID: {TELEGRAM_MONITORING_CHAT_ID}")
    print(f"BREAK_LIMIT_MINUTES: {BREAK_LIMIT_MINUTES}")
    print(f"LUNCH_LIMIT_MINUTES: {LUNCH_LIMIT_MINUTES}")
# ============================================================================
# ДОПОЛНЕНИЯ ДЛЯ config.py
# ============================================================================
# Скопируйте эти строки в конец вашего config.py файла

# ============================================================================
# СИСТЕМА ПЕРЕРЫВОВ v2.0
# ============================================================================

# Названия листов Google Sheets (v20.3 - unified)
BREAK_SCHEDULES_SHEET = "BreakSchedules"
USER_BREAK_ASSIGNMENTS_SHEET = "UserBreakAssignments"
BREAK_USAGE_LOG_SHEET = "BreakLog"           # v20.3: renamed
BREAK_VIOLATIONS_SHEET = "Violations"        # v20.3: renamed

# Порог превышения для уведомления (в минутах)
# Если перерыв превышен на эту величину - отправляется уведомление
BREAK_OVERTIME_THRESHOLD = 2

# Включить/выключить уведомления
BREAK_NOTIFY_USER_ON_VIOLATION = True      # Уведомлять пользователя
BREAK_NOTIFY_ADMIN_ON_VIOLATION = True     # Уведомлять админа

# Типы нарушений
VIOLATION_TYPE_OUT_OF_WINDOW = "OUT_OF_WINDOW"      # Вне временного окна (мягкое)
VIOLATION_TYPE_OVER_LIMIT = "OVER_LIMIT"            # Превышен лимит времени (критическое)
VIOLATION_TYPE_QUOTA_EXCEEDED = "QUOTA_EXCEEDED"    # Превышено количество перерывов (критическое)

# Уровни критичности нарушений
SEVERITY_INFO = "INFO"          # Только логирование, без уведомлений
SEVERITY_WARNING = "WARNING"    # Уведомление пользователю
SEVERITY_CRITICAL = "CRITICAL"  # Уведомление пользователю + админу

# ============================================================================