
import sys
import os
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Callable
import threading

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import STATUSES, STATUS_GROUPS, MAX_COMMENT_LENGTH
from api_adapter import get_sheets_api, get_break_manager
from user_app.db_local import LocalDB, LocalDBError, write_tx
from shared.break_status_integration import init_integration, on_status_change

try:
    from sync.notifications import Notifier
except ImportError:
    try:
        from .sync.notifications import Notifier
    except ImportError:
        from notifications import Notifier

from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QMessageBox, QTextEdit,
    QSizePolicy, QApplication, QSystemTrayIcon, QStyle
)
from PyQt5.QtCore import QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap, QIcon

logger = logging.getLogger(__name__)

class EmployeeApp(QWidget):
    status_changed = pyqtSignal(str)
    app_closed = pyqtSignal(str)

    def __init__(
        self,
        email: str,
        name: str,
        role: str = "специалист",
        group: str = "",
        shift_hours: str = "8 часов",
        telegram_login: str = "",
        on_logout_callback: Optional[Callable] = None,
        session_id: Optional[str] = None,
        login_was_performed: bool = True
    ):
        super().__init__()
        self.email = email
        self.name = name
        self.role = role
        self.group = group
        self.shift_hours = shift_hours
        self.telegram_login = telegram_login
        self.on_logout_callback = on_logout_callback

        self.current_status = "В работе"
        self.status_start_time = datetime.now()
        self.shift_start_time = datetime.now()
        self.last_sync_time = None
        self.shift_ended = False
        self._status_change_in_progress = False  # Флаг для debouncing кнопок статуса

        # Логика закрытия: None, "admin_logout", "user_close", "auto_logout"
        self._closing_reason = None

        if session_id is not None:
            self.session_id = session_id
            self._continue_existing_session = True
        else:
            self.session_id = self._generate_session_id()
            self._continue_existing_session = False
        self.status_buttons = {}

        self.login_was_performed = login_was_performed

        self._init_db()
        self._init_ui()
        self._init_timers()
        self._init_shift_check_timer()

    def get_user(self):
        return {
            "Email": self.email,
            "Name": self.name,
            "Role": self.role,
            "Telegram": self.telegram_login,
            "ShiftHours": self.shift_hours,
            "Group": self.group,
        }

    def _generate_session_id(self) -> str:
        return f"{self.email[:8]}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    def _make_action_payload_from_row(self, row):
        # Порядок столбцов в logs:
        # 0:id 1:session_id 2:email 3:name 4:status 5:action_type 6:comment
        # 7:timestamp 8:synced 9:sync_attempts 10:last_sync_attempt 11:priority
        # 12:status_start_time 13:status_end_time 14:reason 15:user_group
        return {
            "session_id": row[1],
            "email": row[2],
            "name": row[3],
            "status": row[4],
            "action_type": row[5],
            "comment": row[6],
            "timestamp": row[7],
            "status_start_time": row[12],
            "status_end_time": row[13],
            "reason": row[14] if len(row) > 14 else None,
        }

    def _send_action_to_sheets(self, record_id, user_group=None):
        threading.Thread(target=self._send_action_to_sheets_worker, args=(record_id, user_group), daemon=True).start()

    def _send_action_to_sheets_worker(self, record_id, user_group=None):
        # ВАЖНО: Проверяем интернет ПЕРЕД попыткой отправки
        from sync.network import is_internet_available_fast
        if not is_internet_available_fast(timeout=0.3):  # ✅ Очень быстрая проверка!
            logger.warning("Нет интернета, данные будут синхронизированы позже")
            Notifier.show("Оффлайн режим", "Данные будут отправлены при появлении интернета.")
            return
        
        try:
            row = self.db.get_action_by_id(record_id)
            if not row:
                logger.error(f"Не удалось найти запись с id={record_id} для отправки в Sheets")
                return

            action = self._make_action_payload_from_row(row)
            # ВАЖНО: сначала actions (список словарей), затем email
            api = get_sheets_api()
            ok = api.log_user_actions([action], action["email"], user_group=user_group or self.group)
            if ok:
                self.db.mark_actions_synced([record_id])
            else:
                logger.warning("Sheets: log_user_actions вернул False — оставляю запись несинхронизированной")
        except Exception as e:
            logger.warning(f"Ошибка отправки действия в Google Sheets: {e}")
            Notifier.show("Оффлайн режим", "Данные будут отправлены при появлении интернета.")

    def _finish_and_send_previous_status(self):
        prev_id = self.db.finish_last_status(self.email, self.session_id)
        if prev_id:
            threading.Thread(target=self._finish_and_send_previous_status_worker, args=(prev_id,), daemon=True).start()

    def _finish_and_send_previous_status_worker(self, prev_id):
        row = self.db.get_action_by_id(prev_id)
        if not row:
            return
        
        # ВАЖНО: Проверяем интернет ПЕРЕД попыткой отправки
        from sync.network import is_internet_available_fast
        if not is_internet_available_fast(timeout=0.3):  # ✅ Очень быстрая проверка!
            logger.warning("Нет интернета, предыдущий статус будет синхронизирован позже")
            Notifier.show("Оффлайн режим", "Предыдущий статус будет синхронизирован позже.")
            return
        try:
            action = self._make_action_payload_from_row(row)
            api = get_sheets_api()
            ok = api.log_user_actions([action], action["email"], user_group=self.group)
            if ok:
                self.db.mark_actions_synced([prev_id])
            else:
                logger.warning("Sheets: log_user_actions вернул False — оставляю запись несинхронизированной")
        except Exception as e:
            logger.warning(f"Ошибка отправки завершённого статуса в Sheets: {e}")
            Notifier.show("Оффлайн режим", "Предыдущий статус будет синхронизирован позже.")

    def _init_db(self):
        try:
            # ИСПРАВЛЕНИЕ: Используем get_db() вместо создания нового экземпляра
            from user_app.db_local import get_db
            self.db = get_db()
            
            # Инициализация системы перерывов v2.1
            try:
                self.break_mgr = get_break_manager()
                sheets_api = get_sheets_api()
                init_integration(self.break_mgr, sheets_api)
                logger.info("✅ Break system v2.1 initialized")
            except Exception as e:
                logger.error(f"Failed to initialize break system: {e}")
                self.break_mgr = None
            
            if self.login_was_performed:
                now = datetime.now().isoformat()
                has_session = bool(self._continue_existing_session)
                action_type = "STATUS_CHANGE" if has_session else "LOGIN"
                comment = "Начало смены" if action_type == "LOGIN" else "Смена статуса"
                
                # Записываем в ActiveSessions только при LOGIN
                if action_type == "LOGIN":
                    api = get_sheets_api()
                    api.set_active_session(
                        self.email,
                        self.name,
                        self.session_id,
                        now
                    )
                
                # ИСПРАВЛЕНИЕ: Используем write_tx напрямую
                from user_app.db_local import write_tx
                with write_tx() as conn:
                    record_id = self.db.log_action_tx(
                        conn=conn,
                        email=self.email,
                        name=self.name,
                        status=self.current_status,
                        action_type=action_type,
                        comment=comment,
                        session_id=self.session_id,
                        status_start_time=now,
                        status_end_time=None,
                        reason=None
                    )
                self.status_start_time = datetime.fromisoformat(now)
                self._send_action_to_sheets(record_id)
        except Exception as e:
            logger.error(f"Ошибка инициализации БД: {e}")
            QMessageBox.critical(self, "Ошибка", "Не удалось инициализировать локальную базу данных")
            raise

    def _init_ui(self):
        self.setWindowTitle("🕓 Учёт рабочего времени")
        self.setWindowIcon(QIcon(str(Path(__file__).parent / "sberhealf.png")))
        self.resize(500, 440)
        self.setMinimumSize(400, 350)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        header_layout = QHBoxLayout()
        logo_label = QLabel()
        logo_path = Path(__file__).parent / "sberhealf.png"
        if logo_path.exists():
            pixmap = QPixmap(str(logo_path))
            pixmap = pixmap.scaled(180, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(pixmap)
        header_layout.addWidget(logo_label)

        title_label = QLabel("Учёт рабочего времени")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title_label, alignment=Qt.AlignCenter)
        main_layout.addLayout(header_layout)

        self.info_label = QLabel()
        self.info_label.setStyleSheet("QLabel { background-color: #f5f5f5; border-radius: 5px; padding: 10px; }")
        self._update_info_text()
        main_layout.addWidget(self.info_label)

        self.comment_input = QTextEdit()
        self.comment_input.setPlaceholderText("Введите комментарий...")
        self.comment_input.setMaximumHeight(80)
        self.comment_input.setStyleSheet("QTextEdit { border: 1px solid #ddd; border-radius: 5px; padding: 5px; }")
        main_layout.addWidget(self.comment_input)

        self.time_label = QLabel("⏱ Время в статусе: 00:00:00")
        self.time_label.setAlignment(Qt.AlignCenter)
        self.time_label.setStyleSheet("font-size: 14px;")
        main_layout.addWidget(self.time_label)

        self.shift_timer_label = QLabel("⏰ Время смены: 00:00:00")
        self.shift_timer_label.setAlignment(Qt.AlignCenter)
        self.shift_timer_label.setStyleSheet("font-size: 14px; color: #0069c0;")
        main_layout.addWidget(self.shift_timer_label)

        for group in STATUS_GROUPS:
            btn_layout = QHBoxLayout()
            btn_layout.setSpacing(10)
            for status in group:
                btn = QPushButton(status)
                btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                btn.clicked.connect(lambda _, s=status: self.set_status(s))
                btn_layout.addWidget(btn)
                self.status_buttons[status] = btn
            main_layout.addLayout(btn_layout)

        self.finish_btn = QPushButton("Завершить смену")
        self.finish_btn.setStyleSheet("""
            QPushButton {
                padding: 10px;
                border-radius: 5px;
                background-color: #f44336;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        self.finish_btn.clicked.connect(self.finish_shift)
        main_layout.addWidget(self.finish_btn)

        self.setLayout(main_layout)
        self._update_button_states()

    def _init_timers(self):
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self._update_time_display)
        self.status_timer.start(1000)

        self.sync_timer = QTimer(self)
        self.sync_timer.timeout.connect(self._check_sync_status)
        self.sync_timer.start(60000)

    def _init_shift_check_timer(self):
        self.shift_check_timer = QTimer(self)
        self.shift_check_timer.timeout.connect(self._auto_check_shift_ended)
        self.shift_check_timer.start(30000)  # каждые 30 сек
        self._auto_check_shift_ended()

    def _is_session_finished_remote(self) -> bool:
        """
        True — если в ActiveSessions текущая (или последняя по email) сессия
        имеет статус 'finished' или 'kicked'.
        """
        try:
            api = get_sheets_api()
            if hasattr(api, "check_user_session_status"):
                logger.info(f"🔍 [GUI] Checking session: email={self.email}, session_id={self.session_id}")
                st = str(api.check_user_session_status(self.email, self.session_id)).strip().lower()
                logger.info(f"📊 [GUI] Remote status for {self.email}/{self.session_id}: {st}")
                if st in ("finished", "kicked"):
                    logger.info(f"🚨 [GUI] Session kicked/finished detected! Status: {st}")
                    return True

            if hasattr(api, "get_all_active_sessions"):
                sessions = api.get_all_active_sessions() or []
                last_for_email = None
                for s in sessions:
                    if str(s.get("Email", "")).strip().lower() == self.email.lower():
                        last_for_email = s
                if last_for_email:
                    st2 = str(last_for_email.get("Status", "")).strip().lower()
                    logger.info(f"📊 [GUI] Fallback status for {self.email}: {st2}")
                    return st2 in ("finished", "kicked")
        except Exception as e:
            logger.error(f"_is_session_finished_remote error: {e}")
        return False

    def _is_shift_ended(self) -> bool:
        """Проверяет, есть ли локальная запись LOGOUT для текущей сессии"""
        try:
            return self.db.check_existing_logout(self.email, session_id=self.session_id)
        except Exception as e:
            logger.debug(f"_is_shift_ended error: {e}")
            return False

    def _auto_check_shift_ended(self):
        """Периодическая проверка завершения смены"""
        if self.shift_ended:
            return

        # 1) локальная проверка
        if self._is_shift_ended():
            self.shift_ended = True
            self.finish_btn.setEnabled(False)
            for btn in self.status_buttons.values():
                btn.setEnabled(False)
            Notifier.show("WorkLog", "Смена завершена (автоматически, по данным системы).")
            logger.info(f"[AUTO_LOGOUT_DETECT] Локально найден LOGOUT для {self.email}")
            return

        # 2) удалённая проверка ActiveSessions
        if self._is_session_finished_remote():
            logger.info(f"[AUTO_LOGOUT_DETECT] В ActiveSessions статус kicked/finished для {self.email}, session={self.session_id}")
            # ВАЖНО: вызываем force_logout_by_admin вместо ручной логики
            self.force_logout_by_admin()
            return

    def _update_info_text(self):
        info_text = f"""
        <b>Сотрудник:</b> {self.name}<br>
        <b>Должность:</b> {self.role}<br>
        <b>Статус:</b> {self.current_status}<br>
        <b>Продолжительность смены:</b> {self.shift_hours}
        """
        self.info_label.setText(info_text)

    def _update_time_display(self):
        now = datetime.now()
        status_duration = now - self.status_start_time
        shift_duration = now - self.shift_start_time

        status_str = str(status_duration).split('.')[0]
        shift_str = str(shift_duration).split('.')[0]

        self.time_label.setText(f"⏱ Время в статусе: {status_str}")
        self.shift_timer_label.setText(f"⏰ Время смены: {shift_str}")

    def _update_button_states(self):
        for status, btn in self.status_buttons.items():
            # Устанавливаем enabled/disabled
            btn.setEnabled(status != self.current_status)
            
            # Устанавливаем стили
            if status == self.current_status:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #4CAF50;
                        color: white;
                        font-weight: bold;
                        border-radius: 5px;
                        padding: 8px;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #2196F3;
                        color: white;
                        border-radius: 5px;
                        padding: 8px;
                    }
                    QPushButton:hover {
                        background-color: #1976D2;
                    }
                """)
    
    def _disable_status_buttons(self):
        """Блокирует все кнопки статусов (для debouncing)."""
        for btn in self.status_buttons.values():
            btn.setEnabled(False)
    
    def _enable_status_buttons(self):
        """Разблокирует кнопки статусов (кроме текущего)."""
        if not self.shift_ended:
            for status, btn in self.status_buttons.items():
                # Разблокируем все кнопки, кроме текущего статуса
                btn.setEnabled(status != self.current_status)

    def set_status(self, new_status: str):
        if self.shift_ended:
            QMessageBox.information(self, "Смена завершена", "Нельзя изменить статус после завершения смены.")
            return
        
        # DEBOUNCING: Блокируем повторные клики во время обработки
        if self._status_change_in_progress:
            logger.warning(f"⏳ Игнорируем клик на '{new_status}' - предыдущая смена статуса еще обрабатывается")
            return
        
        # Сохраняем old_status ДО проверки на дубликат
        old_status = self.current_status
        

        if new_status == self.current_status:
            return
        
        # Устанавливаем флаг "обработка идет"
        self._status_change_in_progress = True
        # Блокируем ВСЕ кнопки статусов
        self._disable_status_buttons()

        # Интеграция перерывов (в фоновом потоке)
        def break_integration_worker():
            try:
                on_status_change(self.email, old_status, new_status, self.session_id)
            except Exception as e:
                logger.error(f"Break integration error: {e}")
        
        threading.Thread(target=break_integration_worker, daemon=True).start()

        comment = self.comment_input.toPlainText()[:MAX_COMMENT_LENGTH]
        self.comment_input.clear()

        self._finish_and_send_previous_status()

        self.current_status = new_status
        self.status_start_time = datetime.now()

        now = datetime.now().isoformat()
        logger.info(f"🔵 НАЧАЛО: Запись STATUS_CHANGE в БД (status={new_status})")
        try:
            with write_tx() as conn:
                record_id = self.db.log_action_tx(
                    conn=conn,
                    email=self.email,
                    name=self.name,
                    status=new_status,
                    action_type="STATUS_CHANGE",
                    comment=comment,
                    session_id=self.session_id,
                    status_start_time=now,
                    status_end_time=None,
                    reason=None
                )
            logger.info(f"✅ УСПЕХ: STATUS_CHANGE записан в БД (record_id={record_id}, status={new_status})")
        except Exception as e:
            logger.error(f"❌ ОШИБКА: STATUS_CHANGE НЕ записан в БД! Exception: {e}", exc_info=True)
            Notifier.show("Ошибка", f"Не удалось записать статус в БД: {e}")
            return

        self._update_info_text()
        self._update_button_states()
        self.status_changed.emit(new_status)
        self._send_action_to_sheets(record_id)
        
        # Разблокируем кнопки после небольшой задержки (чтобы избежать двойных кликов)
        QTimer.singleShot(300, self._enable_status_buttons)
        self._status_change_in_progress = False

    def _perform_shift_finish(self):
        """Внутренняя логика завершения смены без диалогов подтверждения"""
        if self.shift_ended:
            logger.warning("_perform_shift_finish вызван повторно, игнорируем")
            return

        # Завершаем активный перерыв если он есть (ПЕРЕД завершением смены)
        from shared.break_status_integration import on_logout
        try:
            on_logout(self.email)
            logger.info(f"✅ Break logout hook called for {self.email}")
        except Exception as e:
            logger.error(f"❌ Break logout hook failed for {self.email}: {e}", exc_info=True)

        self.shift_ended = True
        self.finish_btn.setEnabled(False)
        for btn in self.status_buttons.values():
            btn.setEnabled(False)

        now = datetime.now().isoformat()

        with write_tx() as conn:
            # Завершаем предыдущий статус
            cursor = conn.execute(
                "SELECT id FROM logs WHERE email=? AND session_id=? "
                "AND status_end_time IS NULL "
                "AND action_type IN ('LOGIN', 'STATUS_CHANGE') "
                "ORDER BY id DESC LIMIT 1",
                (self.email, self.session_id)
            )
            row = cursor.fetchone()
            if row:
                conn.execute("UPDATE logs SET status_end_time=? WHERE id=?", (now, row[0]))
                prev_id = row[0]
            else:
                prev_id = None
            
            # Записываем LOGOUT
            record_id = self.db.log_action_tx(
                conn=conn,
                email=self.email,
                name=self.name,
                status="Завершено",
                action_type="LOGOUT",
                comment="Завершение смены",
                session_id=self.session_id,
                status_start_time=now,
                status_end_time=now,
                reason="user",
                user_group=self.group
            )
        
        logger.info(f"LOGOUT записан в локальную БД: record_id={record_id}")
        
        # Отправка в фоне
        if prev_id:
            threading.Thread(target=self._send_action_to_sheets_worker, args=(prev_id, self.group), daemon=True).start()
        threading.Thread(target=self._send_action_to_sheets_worker, args=(record_id, self.group), daemon=True).start()

        # Обновляем ActiveSessions
        try:
            api = get_sheets_api()
            api.finish_active_session(self.email, self.session_id, now)
        except Exception as e:
            logger.warning(f"Не удалось обновить ActiveSessions: {e}")

        Notifier.show("WorkLog", "Смена завершена. Данные отправлены.")
        self._closing_reason = "user_close"
        self._enter_background_until_synced()

    def finish_shift(self):
        """Нормальное завершение смены пользователем"""
        if self.shift_ended:
            logger.warning("finish_shift вызван повторно, игнорируем")
            return

        reply = QMessageBox.question(
            self, "Завершение смены",
            "Вы уверены, что хотите завершить смену?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        logger.info("Пользователь подтвердил завершение смены через кнопку")
        self._perform_shift_finish()

    def force_logout_by_admin(self):
        """Принудительное завершение сессии администратором"""
        logger.info(f"[ADMIN_LOGOUT] Принудительный выход для {self.email}")
        
        if self.shift_ended:
            logger.info(f"[ADMIN_LOGOUT] Попытка принудительного выхода для уже завершённой смены: {self.email}")
            return

        # Завершаем активный перерыв если он есть (ПЕРЕД завершением смены)
        from shared.break_status_integration import on_logout
        try:
            on_logout(self.email)
            logger.info(f"✅ [ADMIN_LOGOUT] Break logout hook called for {self.email}")
        except Exception as e:
            logger.error(f"❌ [ADMIN_LOGOUT] Break logout hook failed for {self.email}: {e}", exc_info=True)

        # Блокируем все кнопки немедленно
        self.shift_ended = True
        self.finish_btn.setEnabled(False)
        for btn in self.status_buttons.values():
            btn.setEnabled(False)

        self._closing_reason = "admin_logout"
        
        # Завершаем текущий статус и записываем LOGOUT
        now = datetime.now().isoformat()
        
        prev_id = None
        record_id = None
        
        with write_tx() as conn:
            # Завершаем последний статус
            cursor = conn.execute(
                "SELECT id FROM logs WHERE email=? AND session_id=? "
                "AND status_end_time IS NULL "
                "AND action_type IN ('LOGIN', 'STATUS_CHANGE') "
                "ORDER BY id DESC LIMIT 1",
                (self.email, self.session_id)
            )
            row = cursor.fetchone()
            if row:
                conn.execute("UPDATE logs SET status_end_time=? WHERE id=?", (now, row[0]))
                prev_id = row[0]
                logger.info(f"[ADMIN_LOGOUT] Завершён предыдущий статус: id={prev_id}")
            
            # Записываем LOGOUT с причиной "admin"
            record_id = self.db.log_action_tx(
                conn=conn,
                email=self.email,
                name=self.name,
                status="Завершено",
                action_type="LOGOUT",
                comment="Принудительное завершение администратором",
                session_id=self.session_id,
                status_start_time=now,
                status_end_time=now,
                reason="admin",
                user_group=self.group
            )
            logger.info(f"[ADMIN_LOGOUT] LOGOUT записан в локальную БД: record_id={record_id}")

        # Отправляем данные в Sheets синхронно (блокирующе), чтобы гарантировать доставку
        def send_and_wait():
            import time
            # Отправляем предыдущий статус
            if prev_id:
                logger.info(f"[ADMIN_LOGOUT] Отправка предыдущего статуса: id={prev_id}")
                self._send_action_to_sheets_worker(prev_id, self.group)
                time.sleep(0.5)  # Небольшая задержка между запросами
            
            # Отправляем LOGOUT
            if record_id:
                logger.info(f"[ADMIN_LOGOUT] Отправка LOGOUT: id={record_id}")
                self._send_action_to_sheets_worker(record_id, self.group)
                logger.info(f"[ADMIN_LOGOUT] LOGOUT отправлен в Sheets")
        
        # Запускаем отправку в отдельном потоке, но даём ему время
        send_thread = threading.Thread(target=send_and_wait, daemon=False)
        send_thread.start()
        
        # Обновляем ActiveSessions
        try:
            api = get_sheets_api()
            api.finish_active_session(self.email, self.session_id, now)
            logger.info(f"[ADMIN_LOGOUT] ActiveSessions обновлён для {self.email}")
        except Exception as e:
            logger.warning(f"[ADMIN_LOGOUT] Не удалось обновить ActiveSessions: {e}")

        # Немодальное уведомление с обратным отсчётом
        self._admin_msg = QMessageBox(self)
        self._admin_msg.setWindowTitle("Смена завершена администратором")
        self._admin_msg.setWindowModality(Qt.WindowModal)
        self._admin_msg.setText("Вы были разлогинены администратором.")
        self._admin_msg.setInformativeText("Приложение закроется через 10 секунд.")
        self._admin_msg.setIcon(QMessageBox.Information)
        self._admin_msg.setStandardButtons(QMessageBox.NoButton)
        self._admin_msg.setWindowFlags(self._admin_msg.windowFlags() & ~Qt.WindowCloseButtonHint)
        self._admin_msg.show()

        self._admin_logout_countdown = 10
        self._admin_timer = QTimer(self)
        
        def _tick():
            self._admin_logout_countdown -= 1
            if self._admin_logout_countdown > 0:
                self._admin_msg.setInformativeText(f"Приложение закроется через {self._admin_logout_countdown} секунд.")
            else:
                self._admin_timer.stop()
                try:
                    self._admin_msg.close()
                except Exception:
                    pass
                # Ждём завершения отправки данных
                send_thread.join(timeout=3)
                self._enter_background_until_synced()
                
        self._admin_timer.timeout.connect(_tick)
        self._admin_timer.start(1000)

    def _check_sync_status(self):
        unsynced_count = self.db.count_unsynced_actions(email=self.email)
        if unsynced_count > 0:
            self.last_sync_time = datetime.now()
            logger.debug(f"Несинхронизированных записей: {unsynced_count}")

    def _enter_background_until_synced(self):
        """Переводит приложение в фоновый режим до завершения синхронизации"""
        logger.info("Переход в фоновый режим до завершения синхронизации")
        
        # Скрываем основное окно
        self.hide()
        
        # Создаем системный трей
        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        self._tray.setToolTip("Синхронизация данных...")
        self._tray.show()
        
        # Запускаем таймер проверки синхронизации
        self._sync_wait_timer = QTimer(self)
        self._sync_wait_timer.setInterval(1000)  # ✅ Проверяем каждую секунду
        
        check_count = 0
        max_checks = 300  # 5 минут максимум
        
        def _poll():
            nonlocal check_count
            check_count += 1
            
            try:
                # Проверяем только записи текущей сессии
                pending = self.db.count_unsynced_actions(email=self.email)
            except Exception:
                pending = 0
                
            if pending > 0:
                self._tray.setToolTip(f"Синхронизация… Ожидает отправки: {pending}")
                logger.debug(f"Ожидание синхронизации: {pending} записей (проверка {check_count}/{max_checks})")
                
                # Если прошло 5 минут - все равно закрываемся
                if check_count >= max_checks:
                    logger.warning(f"Таймаут ожидания синхронизации. Осталось {pending} несинхронизированных записей.")
                    self._sync_wait_timer.stop()
                    self._tray.hide()
                    QApplication.quit()
                return
                
            logger.info("✅ Все данные синхронизированы, завершаем приложение")
            self._sync_wait_timer.stop()
            self._tray.hide()
            QApplication.quit()
            
        self._sync_wait_timer.timeout.connect(_poll)
        self._sync_wait_timer.start()

    def closeEvent(self, event):
        """Обработка закрытия через крестик"""
        # Автозавершение активного перерыва
        if hasattr(self, 'current_status') and self.current_status in ["Перерыв", "Обед"]:
            try:
                logger.info(f"Auto-ending break on close: {self.current_status}")
                on_status_change(self.email, self.current_status, "В работе", self.session_id)
            except Exception as e:
                logger.error(f"Failed to auto-end break: {e}")
        
        if self._closing_reason == "admin_logout":
            logger.info("closeEvent: admin_logout - закрытие без подтверждения")
            event.accept()
            self._closing_reason = None
            return

        if self._closing_reason == "auto_logout":
            logger.info("closeEvent: auto_logout - закрытие без подтверждения")
            event.accept()
            self._closing_reason = None
            return

        if self._closing_reason == "user_close":
            # Смена уже завершается через finish_shift, не мешаем
            logger.info("closeEvent: user_close - смена завершается")
            event.ignore()
            return

        # Если смена не завершена, предлагаем завершить
        if not self.shift_ended:
            reply = QMessageBox.question(
                self, "Завершение смены",
                "Вы действительно хотите завершить смену?\n"
                "Текущая сессия будет завершена и отправлена в систему.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                logger.info("Пользователь подтвердил завершение смены через крестик")
                # ИСПРАВЛЕНИЕ: вызываем внутреннюю логику без повторного диалога
                self._perform_shift_finish()
                event.ignore()
            else:
                logger.info("Пользователь отменил завершение смены")
                event.ignore()
        else:
            # Смена уже завершена
            event.accept()

if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication

    logging.basicConfig(level=logging.DEBUG)
    
    app = QApplication(sys.argv)
    
    # Демо-данные
    email = "demo@example.com"
    name = "Иванов Иван Иванович"
    role = "Специалист"
    
    window = EmployeeApp(email, name, role)
    window.show()
    
    sys.exit(app.exec_())