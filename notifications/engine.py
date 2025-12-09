
# notifications/engine.py
from __future__ import annotations
import logging, sqlite3, time, threading, string
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Tuple

from notifications.rules_manager import load_rules, Rule
from telegram_bot.notifier import TelegramNotifier
from config import LOCAL_DB_PATH

log = logging.getLogger(__name__)

DDL = """
CREATE TABLE IF NOT EXISTS status_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    status TEXT NOT NULL,
    ts_utc TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_status_events_email_ts ON status_events(email, ts_utc);

CREATE TABLE IF NOT EXISTS rule_last_sent (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id INTEGER NOT NULL,
    email TEXT,
    context TEXT,
    last_sent_utc TEXT NOT NULL,
    UNIQUE(rule_id, email, context)
);
"""

_poller_stop = None

def start_background_poller(interval_sec: int = 60):
    """Запускает фоновый опрос long_status/status_window."""
    global _poller_stop
    if _poller_stop:
        return _poller_stop
    _poller_stop = threading.Event()
    def _loop():
        while not _poller_stop.is_set():
            try:
                poll_long_running_remote()
            except Exception:
                log.exception("Long-status poll failed")
            _poller_stop.wait(interval_sec)
    threading.Thread(target=_loop, daemon=True).start()
    return _poller_stop

def _open_db() -> sqlite3.Connection:
    con = sqlite3.connect(LOCAL_DB_PATH)
    con.execute("PRAGMA journal_mode=WAL;")
    con.executescript(DDL)
    return con

def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

class _SafeDict(dict):
    # Возвращаем {placeholder} как текст, если ключ не найден
    def __missing__(self, key):
        return "{" + key + "}"

def _format_message(rule: Rule, ctx: dict) -> str:
    """Рендерим сообщение по шаблону; если его нет — даём человекочитаемый запасной текст."""
    tmpl = (rule.template or "").strip()
    if tmpl:
        try:
            return string.Formatter().vformat(tmpl, (), _SafeDict(**ctx))
        except Exception:
            log.exception("Message template render error")
            # человекочитаемый фолбэк по виду правила
    
    # разумные дефолты по типу правила
    if rule.kind == "long_status":
        return (f"⏱ Длительный статус: <b>{ctx.get('status', 'N/A')}</b> уже "
                f"{ctx.get('duration_min', 0)} мин (порог {ctx.get('min_duration_min', 0)} мин).")
    if rule.kind == "status_window":
        return (f"⚠️ Много изменений статусов: {ctx.get('count', 0)}/{ctx.get('limit', 0)} "
                f"за {ctx.get('window_min', 0)} мин.")
    return f"⚙️ Уведомление: {ctx}"

# === Событие: записать факт смены статуса (для status_window) ===
def record_status_event(email: str, status_name: str, ts_iso: Optional[str] = None) -> None:
    email = (email or "").strip().lower()
    if not email:
        return
    ts_iso = ts_iso or _now_iso()
    try:
        con = _open_db()
        with con:
            con.execute(
                "INSERT INTO status_events(email, status, ts_utc) VALUES (?,?,?)",
                (email, status_name or "", ts_iso),
            )
        _maybe_fire_status_window_rules(email)
    except Exception as e:
        log.exception("record_status_event error: %s", e)

def _maybe_fire_status_window_rules(email: str) -> None:
    rules = [r for r in load_rules() if r.kind == "status_window"]
    if not rules:
        return
    con = _open_db()
    for rule in rules:
        try:
            window_min = rule.window_min or 0
            limit = rule.limit or 0
            if window_min <= 0 or limit <= 0:
                continue
            start_ts = (datetime.now(timezone.utc) - timedelta(minutes=window_min)).replace(microsecond=0).isoformat()
            cur = con.execute(
                "SELECT COUNT(*) FROM status_events WHERE email=? AND ts_utc>=?",
                (email, start_ts),
            )
            cnt = int(cur.fetchone()[0])
            if cnt < limit:
                continue
            # антиспам по окну
            context = f"window:{window_min}:{start_ts[:16]}"  # приблизим до минуты
            if not _ratelimit_ok(con, rule, email, context):
                continue
            
            ctx = {
                "email": email, "status": "", "duration_min": "", 
                "limit": limit, "window_min": window_min, "group": rule.group_tag,
                "count": cnt
            }
            text = _format_message(rule, ctx)
            _send_by_scope(rule, email, ctx)
        except Exception as e:
            log.debug("status_window check failed: %s", e)

def check_limit_exceeded(email: str, status_name: str, started_dt: datetime, elapsed_min: int, 
                         limit_min: int, username: Optional[str] = None) -> None:
    """
    Проверяет превышение лимита и отправляет уведомление в мониторинг-группу.
    
    Args:
        email: Email пользователя
        status_name: Название статуса (Перерыв/Обед)
        started_dt: Время начала статуса
        elapsed_min: Прошло минут
        limit_min: Лимит в минутах
        username: Имя пользователя (опционально)
    """
    log.info(f"check_limit_exceeded вызвана: email={email}, status={status_name}, "
             f"elapsed={elapsed_min}, limit={limit_min}")
    
    if elapsed_min <= limit_min:
        log.debug(f"Лимит не превышен: {elapsed_min} <= {limit_min}")
        return
    
    email = (email or "").strip().lower()
    exceeded_min = elapsed_min - limit_min
    
    # Формируем контекст для антиспама
    context = f"exceed:{status_name.lower()}:{email}:{started_dt.replace(microsecond=0).isoformat()}"
    
    # Проверяем, не отправляли ли уже это уведомление
    con = _open_db()
    cur = con.execute(
        "SELECT last_sent_utc FROM rule_last_sent WHERE rule_id=? AND email=? AND context=?",
        (-1, email, context)  # rule_id=-1 для системных уведомлений
    )
    row = cur.fetchone()
    if row:
        try:
            prev = datetime.fromisoformat(row[0])
            gap = (datetime.now(timezone.utc) - prev).total_seconds()
            # Повторно не отправляем в течение 30 минут
            if gap < 1800:
                log.debug(f"Антиспам: уведомление уже отправлялось {gap:.0f} сек назад")
                return
        except Exception:
            pass
    
    # Получаем username если не передан
    if not username:
        username = _get_username(email)
    
    # Формируем текст сообщения
    status_ru = "перерыв" if "перерыв" in status_name.lower() else "обед"
    text = f"⚠️ Пользователь <b>{username or email}</b> превысил {status_ru} на <b>{exceeded_min}</b> минут.\n"
    text += f"Лимит: {limit_min} мин, фактически: {elapsed_min} мин."
    
    log.info(f"Формируем уведомление о превышении: {text}")
    
    # Отправляем в мониторинг-группу
    try:
        notifier = TelegramNotifier()
        success = notifier.send_monitoring(text, silent=False)
        
        if success:
            # Сохраняем факт отправки
            with con:
                con.execute(
                    """INSERT OR REPLACE INTO rule_last_sent(rule_id, email, context, last_sent_utc)
                       VALUES(?,?,?,?)""",
                    (-1, email, context, _now_iso())
                )
            log.info(f"✓ Отправлено уведомление о превышении: {email}, {status_name}, {exceeded_min} мин")
        else:
            log.error(f"✗ Не удалось отправить уведомление о превышении")
    except Exception as e:
        log.exception(f"Ошибка отправки мониторинга превышения: {e}")


def _get_username(email: str) -> Optional[str]:
    """Получает имя пользователя из листа Users."""
    try:
        from api_adapter import SheetsAPI
        from config import GOOGLE_SHEET_NAME, USERS_SHEET
        
        api = SheetsAPI()
        ss = api.client.open(GOOGLE_SHEET_NAME)
        ws = ss.worksheet(USERS_SHEET)
        header = api._request_with_retry(ws.row_values, 1) or []
        values = api._request_with_retry(ws.get_all_values) or []
        
        lh = [str(h or "").strip().lower() for h in header]
        ix_email = lh.index("email") if "email" in lh else None
        ix_name = None
        for name in ("name", "username", "имя", "фио"):
            if name in lh:
                ix_name = lh.index(name)
                break
        
        if ix_email is not None and ix_name is not None:
            for r in values[1:]:
                e = (r[ix_email] if ix_email < len(r) else "").strip().lower()
                if e == email:
                    return (r[ix_name] if ix_name < len(r) else "").strip()
    except Exception as e:
        log.debug(f"Не удалось получить username для {email}: {e}")
    return None

# === Событие: длительный статус (подаётся подготовленными данными) ===
def long_status_check(email: str, status_name: str, started_dt: datetime, elapsed_min: int) -> None:
    email = (email or "").strip().lower()
    
    # НОВОЕ: Проверяем превышение лимитов для Перерыва и Обеда
    from config import BREAK_LIMIT_MINUTES, LUNCH_LIMIT_MINUTES
    status_lower = (status_name or "").strip().lower()
    
    log.debug(f"long_status_check: email={email}, status={status_name}, elapsed={elapsed_min}")
    
    if "перерыв" in status_lower:
        log.debug(f"Проверка перерыва: {elapsed_min} мин (лимит {BREAK_LIMIT_MINUTES})")
        check_limit_exceeded(email, status_name, started_dt, elapsed_min, BREAK_LIMIT_MINUTES)
    elif "обед" in status_lower:
        log.debug(f"Проверка обеда: {elapsed_min} мин (лимит {LUNCH_LIMIT_MINUTES})")
        check_limit_exceeded(email, status_name, started_dt, elapsed_min, LUNCH_LIMIT_MINUTES)
    
    # Существующий код проверки правил
    rules = [r for r in load_rules() if r.kind == "long_status"]
    if not rules:
        return
    con = _open_db()
    s_lc = (status_name or "").strip().lower()
    for rule in rules:
        try:
            # если rule.statuses пуст — применяем ко всем, иначе матчим по списку
            if rule.statuses and s_lc not in [x.lower() for x in rule.statuses]:
                continue
            need = rule.min_duration_min or 0
            if need <= 0 or elapsed_min < need:
                continue
            context = f"long:{s_lc}:{started_dt.replace(microsecond=0).astimezone(timezone.utc).isoformat()}"
            if not _ratelimit_ok(con, rule, email, context):
                continue
            
            ctx = {
                "email": email, "status": status_name, "duration_min": elapsed_min,
                "min_duration_min": need, "limit": "", "window_min": "", "group": rule.group_tag
            }
            text = _format_message(rule, ctx)
            _send_by_scope(rule, email, ctx)
        except Exception as e:
            log.debug("long_status check failed: %s", e)

def poll_long_running_remote() -> None:
    """
    Периодический бэкграунд-чек «длительных статусов» для текущего пользователя.
    1) Берём последний статус по (email, session_id) из локальной БД (без IS NULL).
    2) Если локально ничего нет — читаем ActiveSessions (только чтение).
    3) Считаем длительность с учётом локальной TZ → UTC и применяем long_status-правила.
    """
    logger = logging.getLogger(__name__)
    try:
        from user_app import session as session_state
        from user_app.db_local import LocalDB
    except Exception:
        logger.debug("poll_long_running_remote: session/LocalDB not available")
        return

    email = (session_state.get_user_email() or "").strip().lower()
    if not email:
        return

    db = LocalDB()
    sess = db.get_active_session(email)
    if not sess:
        sess = {}

    session_id = (sess.get("session_id") or "").strip()

    # 1) Пробуем локальную БД: последняя запись статуса в рамках сессии
    status_name = None
    started_iso = None
    if session_id:
        with db._lock:
            cur = db.conn.cursor()
            cur.execute("""
                SELECT status, COALESCE(status_start_time, timestamp) AS started_iso
                FROM logs
                WHERE email=? AND session_id=? AND action_type IN ('LOGIN','STATUS_CHANGE')
                ORDER BY id DESC LIMIT 1
            """, (email, session_id))
            row = cur.fetchone()
            if row:
                status_name, started_iso = row

    # 2) Если локально не нашли — фолбэк к ActiveSessions
    if not status_name or not started_iso:
        try:
            from api_adapter import SheetsAPI
            from config import GOOGLE_SHEET_NAME
            api = SheetsAPI()
            ss = api.client.open(GOOGLE_SHEET_NAME)
            ws = ss.worksheet("ActiveSessions")
            header = api._request_with_retry(ws.row_values, 1) or []
            values = api._request_with_retry(ws.get_all_values) or []
            def _find_idx(names: list[str]) -> Optional[int]:
                h = [str(x or "").strip().lower() for x in header]
                for n in names:
                    if n.strip().lower() in h:
                        return h.index(n.strip().lower())
                return None
            ix_email = _find_idx(["email", "e-mail"])
            ix_status = _find_idx(["status", "статус"])
            ix_start  = _find_idx(["starttime", "start", "начало", "startedat"])
            if ix_email is not None and ix_status is not None and ix_start is not None:
                for r in values[1:]:
                    e = (r[ix_email] if ix_email < len(r) else "").strip().lower()
                    if e == email:
                        status_name = (r[ix_status] if ix_status < len(r) else "").strip()
                        started_iso = (r[ix_start]  if ix_start  < len(r) else "").strip()
                        break
        except Exception as e:
            logger.debug("ActiveSessions fallback failed: %s", e)

    if not status_name or not started_iso:
        return

    # 3) Парсим время: если «наивное» — трактуем как локальное и конвертируем в UTC
    try:
        parsed = datetime.fromisoformat(started_iso.replace("Z", "+00:00"))
    except Exception:
        logger.debug("poll_long_running_remote: bad started_iso=%r", started_iso)
        return
    if parsed.tzinfo is None:
        local_tz = datetime.now().astimezone().tzinfo or timezone.utc
        started_dt = parsed.replace(tzinfo=local_tz)
    else:
        started_dt = parsed
    started_utc = started_dt.astimezone(timezone.utc)
    elapsed_min = max(0, int((datetime.now(timezone.utc) - started_utc).total_seconds() // 60))

    logger.debug(
        "long-status poll: status=%s started_local=%s started_utc=%s elapsed_min=%d",
        status_name, started_dt.isoformat(), started_utc.isoformat(), elapsed_min
    )
    try:
        long_status_check(
            email=email,
            status_name=status_name,
            started_dt=started_utc,
            elapsed_min=elapsed_min,
        )
    except Exception:
        logger.exception("poll_long_running_remote: long_status_check failed")

# === helpers ===
def _ratelimit_ok(con: sqlite3.Connection, rule: Rule, email: Optional[str], context: str) -> bool:
    cur = con.execute(
        "SELECT last_sent_utc FROM rule_last_sent WHERE rule_id=? AND COALESCE(email,'')=COALESCE(?, '') AND context=?",
        (rule.id, email, context)
    )
    row = cur.fetchone()
    if not row:
        return True
    try:
        prev = datetime.fromisoformat(row[0])
    except Exception:
        return True
    gap = (datetime.now(timezone.utc) - prev).total_seconds()
    return gap >= max(1, rule.rate_limit_sec)

def _touch_last_sent(con: sqlite3.Connection, rule: Rule, email: Optional[str], context: str) -> None:
    con.execute(
        """INSERT OR REPLACE INTO rule_last_sent(rule_id, email, context, last_sent_utc)
           VALUES(?,?,?,?)""",
        (rule.id, email, context, _now_iso())
    )

def _default_template(rule: Rule) -> str:
    """Генерирует дефолтный шаблон по типу правила."""
    if rule.kind == "long_status":
        return "⏱ Длительный статус: {status} уже {duration_min} мин (порог {min_duration_min} мин)."
    if rule.kind == "status_window":
        return "⚠️ Много изменений статусов: {count}/{limit} за {window_min} мин."
    return "⚙️ Уведомление: {context}"

def _send_by_scope(rule: Rule, email: str, ctx: Dict[str, object]) -> None:
    n = TelegramNotifier()
    # 1) Нормализуем шаблон
    raw = (rule.template or "").strip()
    if raw.upper() in ("TRUE", "FALSE"):   # защитимся от булевых из Sheets
        raw = ""
    # 2) Дефолт если шаблона нет
    text = raw or _default_template(rule)
    # 3) Безопасное форматирование (не падаем, плейсхолдеры сохраняем как {name})
    try:
        text = text.format_map(_SafeDict(ctx))
    except Exception:
        log.debug("template format failed; ctx=%s", ctx)
        # оставляем text как есть

    if rule.scope == "service":
        n.send_service(text, silent=rule.silent)
    elif rule.scope == "group":
        n.send_group(text, group=rule.group_tag or None, for_all=not bool(rule.group_tag), silent=rule.silent)
    else:
        n.send_personal(email, text, silent=rule.silent)