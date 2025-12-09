
# user_app/session.py
from __future__ import annotations
from typing import Optional
import threading
import logging

class SessionManager:
    """Менеджер сессий для управления состоянием аутентификации пользователя."""
    
    def __init__(self):
        self._lock = threading.RLock()
        self._current_email: Optional[str] = None
        self._current_session_id: Optional[str] = None
        self._current_name: Optional[str] = None
        self._active: bool = False
        # SQLite connection would be initialized here in real implementation
        self.conn = None

    def start_local_session(self, email: str, session_id: str, name: str) -> None:
        """Начать локальную сессию пользователя."""
        with self._lock:
            self._current_email = (email or "").strip().lower()
            self._current_session_id = (session_id or "").strip()
            self._current_name = (name or "").strip()
            self._active = True
            
            # Здесь может быть логика сохранения в SQLite
            # try:
            #     cur = self.conn.cursor()
            #     cur.execute(
            #         "INSERT INTO sessions (email, session_id, name, status, login_time) "
            #         "VALUES (?, ?, ?, 'active', CURRENT_TIMESTAMP)",
            #         (self._current_email, self._current_session_id, self._current_name)
            #     )
            #     self.conn.commit()
            # except Exception as e:
            #     logging.error(f"Ошибка при старте локальной сессии: {e}")

    def finish_local_session(self) -> None:
        """Закрыть локальную сессию (SQLite + память)."""
        with self._lock:
            if not self._active:
                return
                
            try:
                # Логика завершения сессии в SQLite
                if self.conn:
                    cur = self.conn.cursor()
                    cur.execute(
                        "UPDATE sessions SET status = ?, logout_time = CURRENT_TIMESTAMP "
                        "WHERE email = ? AND session_id = ? AND status = 'active'",
                        ("finished", self._current_email, self._current_session_id),
                    )
                    self.conn.commit()
            except Exception as e:
                logging.error(f"Ошибка при завершении локальной сессии: {e}")
            finally:
                # Сброс состояния независимо от результата операции в БД
                self._active = False
                self._current_email = None
                self._current_session_id = None
                self._current_name = None

    def get_user_email(self) -> Optional[str]:
        """Получить email текущего пользователя."""
        with self._lock:
            return self._current_email

    def get_session_id(self) -> Optional[str]:
        """Получить ID текущей сессии."""
        with self._lock:
            return self._current_session_id

    def get_user_name(self) -> Optional[str]:
        """Получить имя текущего пользователя."""
        with self._lock:
            return self._current_name

    def is_active(self) -> bool:
        """Проверить, активна ли сессия."""
        with self._lock:
            return self._active

    def set_user_email(self, email: str) -> None:
        """Установить email пользователя (для обратной совместимости)."""
        with self._lock:
            self._current_email = (email or "").strip().lower()

    def set_session_id(self, session_id: str) -> None:
        """Установить ID сессии (для обратной совместимости)."""
        with self._lock:
            self._current_session_id = (session_id or "").strip()

# Глобальный экземпляр менеджера сессий для обратной совместимости
_session_manager = SessionManager()

# Функции для обратной совместимости со старым кодом
def set_user_email(email: str) -> None:
    _session_manager.set_user_email(email)

def get_user_email() -> Optional[str]:
    return _session_manager.get_user_email()

def set_session_id(session_id: str) -> None:
    _session_manager.set_session_id(session_id)

def get_session_id() -> Optional[str]:
    return _session_manager.get_session_id()

# Новые функции для работы с менеджером сессий
def get_session_manager() -> SessionManager:
    """Получить глобальный экземпляр менеджера сессий."""
    return _session_manager