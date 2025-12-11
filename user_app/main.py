
# user_app/main.py
import sys
import logging
from pathlib import Path
from typing import Dict, Any
from PyQt5.QtWidgets import QApplication, QMessageBox, QMainWindow
from PyQt5.QtCore import QObject, pyqtSignal, QThread
import traceback
import atexit

# Добавка  корень проекта в sys.path
ROOT = Path(__file__).parent.parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Инициализация логирования через единый модуль
from config import LOG_DIR, get_credentials_file, DB_MAIN_PATH, DB_FALLBACK_PATH
from logging_setup import setup_logging
from user_app.signals import SyncSignals
from api_adapter import get_sheets_api  # ← изменено: используем функцию вместо прямого импорта
from auto_sync import SyncManager  # ← добавили
from notifications.engine import start_background_poller
from user_app import db_local  # ← добавили импорт
atexit.register(db_local.close_connection)

# Системы отказоустойчивости
from shared.health import (
    get_health_checker,
    register_all_checks,
    HealthChecker
)
from shared.resilience import (
    get_degradation_manager,
    SystemMode,
    DegradationManager
)

# ----- Сигналы приложения -----
class ApplicationSignals(QObject):
    app_started = pyqtSignal()
    app_shutdown = pyqtSignal()
    login_attempt = pyqtSignal(str)
    login_success = pyqtSignal(dict)
    login_failed = pyqtSignal(str)
    sync_status_changed = pyqtSignal(bool)
    sync_progress = pyqtSignal(int, int)
    sync_finished = pyqtSignal(bool)

# ----- Менеджер приложения -----
class ApplicationManager(QObject):
    def __init__(self):
        super().__init__()
        self.app = QApplication(sys.argv)
        self.app.setStyle("Fusion")
        self.app.setApplicationName("WorkTimeTracker")
        self.app.setApplicationVersion("1.0.0")
        # Окно может быть скрыто в трей — приложение должно жить до полной синхронизации
        self.app.setQuitOnLastWindowClosed(False)
        
        # КРИТИЧЕСКИ ВАЖНО: Инициализируем систему уведомлений в главном потоке
        # ПОСЛЕ создания QApplication!
        try:
            from sync.notifications import init_notification_system
            init_notification_system()
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to init notification system: {e}")

        self.login_window = None
        self.main_window = None
        self.signals = ApplicationSignals()

        self.sync_thread: QThread | None = None
        self.sync_worker: SyncManager | None = None
        self.sync_signals = SyncSignals()  # сигналы доступны и для GUI, и для SyncManager

        # Системы отказоустойчивости
        self.health_checker: HealthChecker = None
        self.degradation_manager: DegradationManager = None
        self.current_system_mode = SystemMode.FULL

        sys.excepthook = self.handle_uncaught_exception

        try:
            self._initialize_resources()
            self._start_sync_service()
            self.signals.app_started.emit()
            
            # Регистрация cleanup после успешной инициализации
            # Используем lambda для отложенного вызова
            atexit.register(lambda: self._cleanup() if hasattr(self, '_cleanup') else None)
        except Exception as e:
            self._show_error("Initialization Error", f"Failed to initialize: {e}")
            sys.exit(1)

    # --- Инициализация ресурсов ---
    def _initialize_resources(self):
        creds_path = get_credentials_file()
        if not creds_path.exists():
            raise FileNotFoundError(f"Credentials file not found: {creds_path}")
        
        # Инициализация клиента Google Sheets
        try:
            # ← изменено: используем функцию get_sheets_api() вместо прямого создания экземпляра
            api = get_sheets_api()
            self.sheets_api = api
        except Exception as e:
            logging.getLogger(__name__).error("SheetsAPI init failed: %s", e)
            raise
        
        # ← изменено: проверяем credentials через полученный API
        if not api.check_credentials():
            raise RuntimeError("Invalid Google Sheets credentials")
        
        # Инициализация систем отказоустойчивости
        try:
            logger = logging.getLogger(__name__)
            logger.info("=== ИНИЦИАЛИЗАЦИЯ СИСТЕМ ОТКАЗОУСТОЙЧИВОСТИ ===")
            
            # 1. Health Checker
            self.health_checker = get_health_checker(failure_threshold=3)
            register_all_checks(self.health_checker)
            self.health_checker.start_monitoring(interval=60)
            logger.info("✓ Health Checker запущен (interval=60s)")
            
            # 2. Degradation Manager
            self.degradation_manager = get_degradation_manager(
                health_checker=self.health_checker,
                mode_change_callback=self._on_system_mode_change,
                notification_callback=self._on_system_notification
            )
            self.degradation_manager.start_auto_evaluation(interval=30)
            logger.info("✓ Degradation Manager запущен (interval=30s)")
            
            logger.info("=== СИСТЕМЫ ОТКАЗОУСТОЙЧИВОСТИ ГОТОВЫ ===")
        
        except Exception as e:
            logger.error(f"Ошибка инициализации систем отказоустойчивости: {e}")
            # Не критично - продолжаем работу без мониторинга
            self.health_checker = None
            self.degradation_manager = None

    # --- Фоновая синхронизация ---
    def _start_sync_service(self):
        try:
            logger = logging.getLogger(__name__)
            logger.info("=== ЗАПУСК СЕРВИСА СИНХРОНИЗАЦИИ ===")
            
            # Запускаем сервис синхронизации в фоне
            logger.info("Создание SyncManager...")
            self.sync_manager = SyncManager(signals=self.sync_signals, background_mode=True)
            logger.info(f"SyncManager создан. Проверяем наличие метода start: {hasattr(self.sync_manager, 'start')}")
            
            if hasattr(self.sync_manager, "start"):
                logger.info("Вызов self.sync_manager.start()...")
                self.sync_manager.start()
                logger.info("✅ self.sync_manager.start() вызван")
            elif hasattr(self.sync_manager, "start_background"):
                logger.info("Вызов self.sync_manager.start_background()...")
                self.sync_manager.start_background()
                logger.info("✅ self.sync_manager.start_background() вызван")
            else:
                logger.error("❌ У SyncManager НЕТ методов start() или start_background()!")
            
            logger.info("Sync service started")
        except Exception as e:
            logger.error(f"Failed to start sync service: {e}")

    # --- UI потоки ---
    def show_login_window(self):
        try:
            from user_app.login_window import LoginWindow
            self.login_window = LoginWindow()
            self.login_window.login_success.connect(self.handle_login_success)
            self.login_window.login_failed.connect(self.handle_login_failed)
            self.login_window.show()
        except Exception as e:
            self._show_error("Login Error", f"Cannot show login window: {e}")
            self.quit_application()

    def handle_login_success(self, user_data: Dict[str, Any]):
        try:
            from user_app.gui import EmployeeApp

            # закрыть окно логина
            if self.login_window:
                try:
                    self.login_window.close()
                except Exception:
                    pass

            # достаём данные, которые LoginWindow уже собирает
            session_id = None
            login_was_performed = True
            if user_data.get("unfinished_session"):
                session_id = user_data["unfinished_session"].get("session_id")
            if "login_was_performed" in user_data:
                login_was_performed = bool(user_data["login_was_performed"])

            def on_logout_wrapper():
                # корректно завершаем приложение по запросу из EmployeeApp
                self.quit_application()

            # создаём главное окно как раньше
            self.main_window = EmployeeApp(
                email=user_data["email"],
                name=user_data["name"],
                role=user_data["role"],
                shift_hours=user_data["shift_hours"],
                telegram_login=user_data.get("telegram_login", ""),
                on_logout_callback=on_logout_wrapper,
                session_id=session_id,
                login_was_performed=login_was_performed,
                group=user_data.get("group", "")
            )
            
            # Сохраняем ссылку на login_window для возврата
            self.main_window.login_window = self.login_window
            
            self.main_window.show()

            # подключаем «принудительный разлогин» из сервиса синхронизации
            self.sync_signals.force_logout.connect(self.main_window.force_logout_by_admin)
            logger = logging.getLogger(__name__)
            logger.info("force_logout сигнал подключён к force_logout_by_admin")

        except Exception as e:
            self._show_error("Main Window Error", f"Cannot show main window: {e}")
            self.quit_application()

    def handle_login_failed(self, message: str):
        # Ошибка уже показана в LoginWindow через _show_error_once()
        # Здесь только логируем для отладки (debug уровень, чтобы не дублировать)
        logger = logging.getLogger(__name__)
        logger.debug("Login failed signal received: %s", message)

    # --- Общее ---
    def _show_error(self, title: str, message: str):
        QMessageBox.critical(None, title, message)
        logger = logging.getLogger(__name__)
        logger.error("%s: %s", title, message)

    def handle_uncaught_exception(self, exc_type, exc_value, exc_traceback):
        logger = logging.getLogger(__name__)
        logger.critical(
            "Unhandled exception",
            exc_info=(exc_type, exc_value, exc_traceback)
        )
        self._show_error("Critical Error", f"An unexpected error occurred:\n\n{exc_value}")
        self.quit_application()

    def quit_application(self):
        logger = logging.getLogger(__name__)
        logger.info("Shutting down application.")
        self.signals.app_shutdown.emit()

        # закрываем окна
        if self.main_window:
            try:
                self.main_window.close()
            except Exception as e:
                logger.error("Error on main_window.close(): %s", e)
            self.main_window = None

        if self.login_window:
            try:
                self.login_window.close()
            except Exception as e:
                logger.error("Error on login_window.close(): %s", e)
            self.login_window = None

        # останавливаем сервис синхронизации
        try:
            if self.sync_worker:
                self.sync_worker.stop()
        except Exception:
            pass
        if self.sync_thread and self.sync_thread.isRunning():
            self.sync_thread.quit()
            self.sync_thread.wait()

        self.app.quit()

    # точка входа UI
    def run(self):
        self.show_login_window()
        sys.exit(self.app.exec_())

# ----- Базовый класс MainWindow с обработкой закрытия -----
class MainWindow(QMainWindow):
    def __init__(self, session_manager, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_manager = session_manager
        self.login_window = None  # будем возвращаться сюда

    def closeEvent(self, event):
        """Обработка закрытия через крестик"""
        reply = QMessageBox.question(
            self,
            "Завершение работы",
            "Вы действительно хотите завершить сессию?\n"
            "Текущая смена будет завершена.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            try:
                # Завершаем локальную и удалённую сессии
                email = self.session_manager.email
                session_id = self.session_manager.session_id
                # ← изменено: используем функцию get_sheets_api() вместо прямого импорта
                api = get_sheets_api()
                api.finish_active_session(email, session_id)
                self.session_manager.finish_local_session()
            except Exception as e:
                import logging
                logging.error(f"Ошибка при завершении сессии: {e}")

            # Скрываем текущее окно и возвращаем LoginWindow
            if self.login_window:
                self.hide()
                self.login_window.show()
            else:
                super().closeEvent(event)
        else:
            event.ignore()
    
    # --- Обработчики систем отказоустойчивости ---
    def _on_system_mode_change(self, old_mode: SystemMode, new_mode: SystemMode, reason: str):
        """Обработчик смены режима работы системы"""
        logger = logging.getLogger(__name__)
        logger.warning(f"🔄 Режим: {old_mode.value} → {new_mode.value} ({reason})")
        
        self.current_system_mode = new_mode
        
        if new_mode == SystemMode.FULL:
            logger.info("✅ FULL mode: все функции доступны")
        elif new_mode == SystemMode.DEGRADED:
            logger.warning("⚠️  DEGRADED mode: ограниченный функционал")
        elif new_mode == SystemMode.OFFLINE:
            logger.warning("📴 OFFLINE mode: только локальная работа")
        elif new_mode == SystemMode.EMERGENCY:
            logger.error("🚨 EMERGENCY mode: только просмотр")
    
    def _on_system_notification(self, message: str):
        """Обработчик уведомлений о смене режима"""
        logger = logging.getLogger(__name__)
        logger.info(f"📢 {message}")
    
    def _cleanup(self):
        """Очистка ресурсов при завершении"""
        logger = logging.getLogger(__name__)
        logger.info("=== CLEANUP СИСТЕМ ОТКАЗОУСТОЙЧИВОСТИ ===")
        
        if self.health_checker:
            try:
                self.health_checker.stop_monitoring()
                logger.info("✓ Health Checker остановлен")
            except Exception as e:
                logger.error(f"Ошибка: {e}")
        
        if self.degradation_manager:
            try:
                self.degradation_manager.stop_auto_evaluation()
                logger.info("✓ Degradation Manager остановлен")
            except Exception as e:
                logger.error(f"Ошибка: {e}")

# ----- CLI -----
def main():
    poller_stop = None
    try:
        # единый логгер
        log_path = setup_logging(app_name="wtt-user", log_dir=LOG_DIR)
        logger = logging.getLogger(__name__)
        logger.info("Logging initialized (path=%s)", log_path)
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Инициализация БД перед всем остальным
        from user_app.db_local import init_db
        from config import LOCAL_DB_PATH
        from pathlib import Path
        
        home_fallback = Path.home() / "WorkTimeTracker" / "local_backup.db"
        try:
            conn, db_path = init_db(str(LOCAL_DB_PATH), str(home_fallback))
            logger.info(f"Database initialized: {db_path}")
        except Exception as e:
            logger.critical(f"Failed to initialize database: {e}")
            QMessageBox.critical(
                None,
                "Критическая ошибка",
                f"Не удалось инициализировать базу данных:\n{e}\n\nПриложение будет закрыто."
            )
            return 1
        
        # один раз при старте
        db_local.init_db(DB_MAIN_PATH, DB_FALLBACK_PATH)
        
        # Запускаем фоновый опросчик уведомлений
        poller_stop = start_background_poller(60)
        
        app_manager = ApplicationManager()
        app_manager.run()
    except Exception as e:
        logging.critical(f"Fatal error: {e}\n{traceback.format_exc()}")
        QMessageBox.critical(None, "Fatal Error", f"Application failed to start:\n{e}")
        sys.exit(1)
    finally:
        logger.info("Shutting down application.")
        if poller_stop:
            poller_stop.set()

if __name__ == "__main__":
    main()