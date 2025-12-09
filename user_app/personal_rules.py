
# user_app/personal_rules.py
from __future__ import annotations
import sqlite3
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from config import (
    PERSONAL_RULES_ENABLED,
    PERSONAL_WINDOW_MIN,
    PERSONAL_STATUS_LIMIT_PER_WINDOW,
    LOCAL_DB_PATH,   # путь к вашей локальной БД, как в user_app.db_local
    BREAK_LIMIT_MINUTES,       # === добавлено для дефолтов BreakRules
    LUNCH_LIMIT_MINUTES,       # === добавлено для дефолтов BreakRules
)
from telegram_bot.notifier import TelegramNotifier
from notifications.engine import record_status_event, long_status_check

# Импортируем модуль для работы с общим подключением к БД
from user_app.db_local import read_cursor  # Вместо прямого подключения

# === NEW: динамические лимиты из BreakRules ===
from api_adapter import SheetsAPI

log = logging.getLogger(__name__)

DDL = """
CREATE TABLE IF NOT EXISTS status_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    status TEXT NOT NULL,
    ts_utc TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_status_events_email_ts ON status_events(email, ts_utc);
"""

def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def _open_db() -> sqlite3.Connection:
    con = sqlite3.connect(LOCAL_DB_PATH)
    con.execute("PRAGMA journal_mode=WAL;")
    con.executescript(DDL)
    return con

# === NEW: публичная функция получения лимитов из BreakRules (с fallback на config) ===
def get_user_break_limits(email: str, work_pattern: Optional[str] = None) -> dict:
    """
    Возвращает лимиты для пользователя из листа BreakRules.
    Если индивидуальное правило не найдено — берёт шаблон по WorkPattern.
    Если ничего нет — возвращает дефолты из config.py.
    """
    api = SheetsAPI()
    try:
        rule = api.find_rule_for_user(email, work_pattern)
    except Exception:
        rule = None

    if not rule:
        return {
            "breaks_per_day": 2,
            "break_duration_min": BREAK_LIMIT_MINUTES,
            "lunches_per_day": 1,
            "lunch_duration_min": LUNCH_LIMIT_MINUTES,
            "work_pattern": (work_pattern or "default"),
        }

    def _to_int(v, default=0):
        s = str(v or "").strip().replace(",", ".")
        try:
            return int(float(s)) if s != "" else default
        except Exception:
            return default

    return {
        "breaks_per_day": _to_int(rule.get("BreaksPerDay"), 2),
        "break_duration_min": _to_int(rule.get("BreakDurationMin"), BREAK_LIMIT_MINUTES),
        "lunches_per_day": _to_int(rule.get("LunchesPerDay"), 1),
        "lunch_duration_min": _to_int(rule.get("LunchDurationMin"), LUNCH_LIMIT_MINUTES),
        "work_pattern": (rule.get("WorkPattern") or work_pattern or "default"),
    }

def on_status_committed(email: str, status_name: str, ts_iso: Optional[str] = None) -> None:
    """Фиксирует событие статуса и даёт движку шанс сработать по правилам status_window."""
    if not PERSONAL_RULES_ENABLED:
        return

    email = (email or "").strip().lower()
    if not email:
        return

    ts_iso = ts_iso or _utcnow_iso()
    try:
        record_status_event(email=email, status_name=status_name, ts_iso=ts_iso)
    except Exception as e:
        log.exception("personal_rules.on_status_committed error: %s", e)

def check_long_status(email: str, status_name: str, started_iso: str, elapsed_min: int) -> None:
    """
    Проверяет длительные статусы и передаёт информацию в движок правил.
    """
    if not PERSONAL_RULES_ENABLED:
        return

    email = (email or "").strip().lower()
    if not email:
        return

    try:
        # Преобразуем строку в datetime с учетом таймзоны
        started_dt = datetime.fromisoformat(started_iso)
        
        # Если тайзона отсутствует — считаем это ЛОКАЛЬНЫМ временем машины
        local_tz = datetime.now().astimezone().tzinfo
        if started_dt.tzinfo is None:
            started_local = started_dt.replace(tzinfo=local_tz)
        else:
            started_local = started_dt.astimezone(local_tz)
        
        # Нормализуем в UTC для расчётов
        started_utc = started_local.astimezone(timezone.utc)
        
        # Добавляем отладочную информацию
        log.debug(
            "long-status poll: status=%s started_local=%s started_utc=%s elapsed_min=%d",
            status_name, started_local.isoformat(), started_utc.isoformat(), elapsed_min
        )
        
        # Передаём в движок правил: он сам решит, какие long_status правила совпадают
        long_status_check(
            email=email, 
            status_name=status_name, 
            started_dt=started_utc, 
            elapsed_min=elapsed_min
        )
    except Exception as e:
        log.exception("personal_rules.check_long_status error: %s", e)

def poll_long_running_local() -> None:
    """Опрос длительных статусов через централизованное подключение."""
    if not PERSONAL_RULES_ENABLED:
        return

    try:
        with read_cursor() as cur:
            # ИСПРАВЛЕНИЕ: Предполагаем, что таблица long_running_statuses существует
            # Если нет - добавить в миграции
            cur.execute("""
                SELECT email, status_name, started_iso, elapsed_min
                FROM long_running_statuses
                WHERE elapsed_min > 0
            """)
            
            for row in cur.fetchall():
                email, status_name, started_iso, elapsed_min = row
                check_long_status(email, status_name, started_iso, elapsed_min)
                
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            log.debug("Table long_running_statuses not created yet")
        else:
            log.exception("poll_long_running_local error: %s", e)
    except Exception as e:
        log.exception("poll_long_running_local error: %s", e)