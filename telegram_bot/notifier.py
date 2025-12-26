
# telegram_bot/notifier.py
from __future__ import annotations
import logging, time
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple, List
import requests
import os

# Импорт для работы с московским временем
try:
    from shared.time_utils import format_datetime_moscow, now_moscow
except ImportError:
    # Фолбэк если модуль недоступен
    def format_datetime_moscow(dt, format_str='%Y-%m-%d %H:%M:%S'):
        if dt is None:
            dt = datetime.now()
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        return dt.strftime(format_str)
    
    def now_moscow():
        return datetime.now(timezone.utc).astimezone()

# Импорты из config.py с обработкой исключений на случай отсутствия модуля
try:
    from config import (
        GOOGLE_SHEET_NAME,
        USERS_SHEET,
        TELEGRAM_BOT_TOKEN as CFG_TELEGRAM_BOT_TOKEN,
        TELEGRAM_ADMIN_CHAT_ID as CFG_TELEGRAM_ADMIN_CHAT_ID,
        TELEGRAM_BROADCAST_CHAT_ID as CFG_TELEGRAM_BROADCAST_CHAT_ID,
        TELEGRAM_MONITORING_CHAT_ID as CFG_TELEGRAM_MONITORING_CHAT_ID,
        TELEGRAM_MIN_INTERVAL_SEC as CFG_TELEGRAM_MIN_INTERVAL_SEC,
        TELEGRAM_SILENT as CFG_TELEGRAM_SILENT,
    )
except ImportError:
    # Фолбэк значения если config.py не существует
    GOOGLE_SHEET_NAME = ""
    USERS_SHEET = "Users"
    CFG_TELEGRAM_BOT_TOKEN = ""
    CFG_TELEGRAM_ADMIN_CHAT_ID = ""
    CFG_TELEGRAM_BROADCAST_CHAT_ID = ""
    CFG_TELEGRAM_MONITORING_CHAT_ID = ""
    CFG_TELEGRAM_MIN_INTERVAL_SEC = 600
    CFG_TELEGRAM_SILENT = False

from api_adapter import SheetsAPI

log = logging.getLogger(__name__)
NOTIFICATIONS_LOG_SHEET = "NotificationsLog"


def _now_iso() -> str:
    """Возвращает текущее время в московском часовом поясе в ISO формате"""
    return now_moscow().isoformat(timespec="seconds")


def _bool(v, default=False):
    if v is None:
        return default
    s = str(v).strip().lower()
    return s in ("1", "true", "yes", "y", "да")


class TelegramNotifier:
    """
    Четыре типа уведомлений:
      - service/admin → TELEGRAM_ADMIN_CHAT_ID
      - personal(email) → chat_id из Users.<Telegram/TelegramChatID/tg>
      - group/broadcast → TELEGRAM_BROADCAST_CHAT_ID с префиксом [Группа]/[Все]
      - monitoring → TELEGRAM_MONITORING_CHAT_ID (превышения лимитов)
    Аудит в лист NotificationsLog (создаётся автоматически).
    """
    def __init__(
        self,
        token: Optional[str] = None,
        admin_chat_id: Optional[str] = None,
        broadcast_chat_id: Optional[str] = None,
        min_interval_sec: Optional[int] = None,
        default_silent: Optional[bool] = None,
    ):
        # Приоритет: явный аргумент → ENV → config.py
        self.token = (
            token
            or os.getenv("TELEGRAM_BOT_TOKEN", "")
            or (CFG_TELEGRAM_BOT_TOKEN or "")
        ).strip()
        if not self.token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN не задан.")
        self.api_url = f"https://api.telegram.org/bot{self.token}"

        self.admin_chat = str(
            admin_chat_id
            or os.getenv("TELEGRAM_ADMIN_CHAT_ID", "")
            or (CFG_TELEGRAM_ADMIN_CHAT_ID or "")
        ).strip()
        
        self.broadcast_chat = str(
            broadcast_chat_id
            or os.getenv("TELEGRAM_BROADCAST_CHAT_ID", "")
            or (CFG_TELEGRAM_BROADCAST_CHAT_ID or "")
        ).strip()
        
        self.monitoring_chat = str(
            os.getenv("TELEGRAM_MONITORING_CHAT_ID", "")
            or (CFG_TELEGRAM_MONITORING_CHAT_ID or "")
        ).strip()
        
        self.min_interval = int(
            (min_interval_sec if min_interval_sec is not None else 0)
            or os.getenv("TELEGRAM_MIN_INTERVAL_SEC", "")
            or (CFG_TELEGRAM_MIN_INTERVAL_SEC if CFG_TELEGRAM_MIN_INTERVAL_SEC is not None else 600)
        )
        
        self.default_silent = (
            _bool(default_silent)
            if default_silent is not None
            else _bool(os.getenv("TELEGRAM_SILENT"))
            if os.getenv("TELEGRAM_SILENT") is not None
            else _bool(CFG_TELEGRAM_SILENT)
        )

        self._last_sent: Dict[str, float] = {}      # анти-спам (key -> ts)
        self._links_cache: Dict[str, str] = {}      # email -> chat_id
        self._links_ts: float = 0.0
        self._links_ttl: float = 300.0              # 5 минут
        self._sheets: SheetsAPI | None = None
        
        # Модернизация: добавляем сессию с keep-alive и таймаутами
        self._session = requests.Session()
        self._session.headers.update({"Connection": "keep-alive"})
        self._timeout = (5, 15)  # (connect, read)
        
        # Логируем инициализацию
        log.info(f"TelegramNotifier инициализирован: admin={bool(self.admin_chat)}, "
                 f"broadcast={bool(self.broadcast_chat)}, monitoring={bool(self.monitoring_chat)}")

    # ---------- публичные API ----------
    def send_service(self, text: str, *, silent: Optional[bool] = None) -> bool:
        """Отправка служебного сообщения админу."""
        if not self.admin_chat:
            log.warning("TELEGRAM_ADMIN_CHAT_ID не настроен.")
            return False
        key = f"svc:{hash(text)}"
        if self._skip_by_rate(key):
            return False
        ok, err = self._send_text(self.admin_chat, text, silent)
        self._audit("service", f"admin:{self.admin_chat}", text, ok, err)
        return ok

    def send_personal(self, email: str, text: str, *, silent: Optional[bool] = None) -> bool:
        """Отправка персонального сообщения пользователю."""
        chat_id = self._resolve_chat_id(email)
        if not chat_id:
            log.warning(f"chat_id не найден для email: {email}")
            self._audit("personal", f"email:{email}", text, False, "chat_id not found")
            return False
        key = f"pm:{email}:{hash(text)}"
        if self._skip_by_rate(key):
            return False
        ok, err = self._send_text(chat_id, text, silent)
        self._audit("personal", f"email:{email}", text, ok, err)
        return ok

    def send_group(self, text: str, *, group: Optional[str] = None, for_all: bool = False,
                   silent: Optional[bool] = None) -> bool:
        """Отправка группового сообщения."""
        if not self.broadcast_chat:
            log.warning("TELEGRAM_BROADCAST_CHAT_ID не настроен.")
            return False
        tag = f"[{group}] " if (group and not for_all) else "[Все] " if for_all else ""
        payload_text = f"{tag}{text}"
        key = f"grp:{group or 'all'}:{hash(text)}"
        if self._skip_by_rate(key):
            return False
        ok, err = self._send_text(self.broadcast_chat, payload_text, silent)
        self._audit("group_all" if for_all else "group", f"chat:{self.broadcast_chat}", payload_text, ok, err)
        return ok

    def send_monitoring(self, text: str, *, silent: Optional[bool] = None) -> bool:
        """
        Отправляет уведомление в группу мониторинга превышений лимитов.
        
        Args:
            text: Текст сообщения
            silent: Тихое уведомление (по умолчанию False для важных событий)
        
        Returns:
            True если отправка успешна, False инач
"""
        if not self.monitoring_chat:
            log.warning("TELEGRAM_MONITORING_CHAT_ID не настроен.")
            return False
        
        log.info(f"Отправка мониторинг-уведомления в {self.monitoring_chat}: {text[:50]}...")
        
        # Для мониторинга не применяем антиспам - важные события всегда доставляем
        ok, err = self._send_text(self.monitoring_chat, text, silent if silent is not None else False)
        self._audit("monitoring", f"chat:{self.monitoring_chat}", text, ok, err)
        
        if ok:
            log.info("✓ Мониторинг-уведомление успешно отправлено")
        else:
            log.error(f"✗ Ошибка отправки мониторинг-уведомления: {err}")
        
        return ok

    # ---------- helpers ----------
    def _sheets_api(self) -> SheetsAPI:
        if self._sheets is None:
            self._sheets = SheetsAPI()
        return self._sheets

    def _skip_by_rate(self, key: str) -> bool:
        now = time.monotonic()
        last = self._last_sent.get(key, 0.0)
        if (now - last) < max(1, self.min_interval):
            log.debug("Анти-спам: пропуск %s", key)
            return True
        self._last_sent[key] = now
        return False

    def _send_text(self, chat_id: str, text: str, silent: Optional[bool]) -> Tuple[bool, Optional[str]]:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_notification": self.default_silent if silent is None else bool(silent),
        }
        try:
            log.debug(f"Отправка сообщения в {chat_id}: {text[:100]}...")
            # Модернизация: используем сессию с таймаутом
            r = self._session.post(f"{self.api_url}/sendMessage", json=payload, timeout=self._timeout)
            data = r.json()
            if not data.get("ok", False):
                err = data.get("description") or r.text
                log.error("Telegram sendMessage error: %s", err)
                return False, err
            log.debug("✓ Сообщение успешно отправлено")
            return True, None
        except Exception as e:
            log.exception("Telegram sendMessage exception: %s", e)
            return False, str(e)

    def _resolve_chat_id(self, email: str) -> Optional[str]:
        email = (email or "").strip().lower()
        links = self._load_links_cache()
        return links.get(email)

    def _load_links_cache(self) -> Dict[str, str]:
        if (time.monotonic() - self._links_ts) < self._links_ttl and self._links_cache:
            return self._links_cache
        try:
            api = self._sheets_api()
            ws = api.get_worksheet(USERS_SHEET)
            header = api._request_with_retry(ws.row_values, 1) or []
            values = api._request_with_retry(ws.get_all_values) or []
            lh = [str(h or "").strip().lower() for h in header]
            ix_email = lh.index("email") if "email" in lh else None
            ix_tg = None
            for name in ("telegram", "telegramchatid", "tg"):
                if name in lh:
                    ix_tg = lh.index(name); break
            cache: Dict[str, str] = {}
            if ix_email is not None and ix_tg is not None:
                for r in values[1:]:
                    e = (r[ix_email] if ix_email < len(r) else "").strip().lower()
                    c = (r[ix_tg] if ix_tg < len(r) else "").strip()
                    if e and c:
                        cache[e] = c
            self._links_cache, self._links_ts = cache, time.monotonic()
        except Exception as e:
            log.error("Не удалось загрузить Users -> Telegram: %s", e)
        return self._links_cache

    def _audit(self, kind: str, target: str, text: str, ok: bool, err: Optional[str]) -> None:
        try:
            api = self._sheets_api()
            ss = api.client.open(GOOGLE_SHEET_NAME)
            titles = [w.title for w in ss.worksheets()]
            if NOTIFICATIONS_LOG_SHEET not in titles:
                ws_new = ss.add_worksheet(title=NOTIFICATIONS_LOG_SHEET, rows=2000, cols=6)
                api._request_with_retry(ws_new.update, "A1", [["Ts","Kind","Target","Status","Preview","Error"]])
            ws = ss.worksheet(NOTIFICATIONS_LOG_SHEET)
            row = [_now_iso(), kind, target, "OK" if ok else "FAIL", (text or "")[:180], (err or "")[:180]]
            api._request_with_retry(ws.append_rows, [row], value_input_option="RAW")
        except Exception as e:
            log.debug("Аудит недоступен: %s", e)