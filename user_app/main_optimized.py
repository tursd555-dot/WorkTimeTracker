# user_app/main.py - ОПТИМИЗИРОВАННАЯ ВЕРСИЯ
"""
Этап 3: Оптимизация производительности
- Lazy loading модулей
- Отложенная инициализация
- Асинхронная загрузка компонентов

Целевые метрики:
- Startup time: < 3 сек (было ~5-8 сек)
- Memory usage: < 50 MB (было ~80 MB)
"""

import sys
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import traceback
import atexit

# ============================================================================
# МИНИМАЛЬНЫЕ ИМПОРТЫ ПРИ СТАРТЕ
# Импортируем только то, что ДЕЙСТВИТЕЛЬНО нужно для запуска
# ============================================================================

# PyQt5 - только базовые классы
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QObject, pyqtSignal, QThread, QTimer

# Базовая конфигурация
ROOT = Path(__file__).parent.parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Только конфиг и логирование при старте
from config import LOG_DIR, DB_MAIN_PATH, DB_FALLBACK_PATH
from logging_setup import setup_logging

# ============================================================================
# LAZY LOADING FUNCTIONS
# Эти функции импортируют модули только при первом вызове
# ============================================================================

_sheets_api = None
_sync_manager = None
_notification_engine = None
_db_local = None

def get_sheets_api_lazy():
    """Ленивая загрузка Google Sheets API (импорт при первом вызове)"""
    global _sheets_api
    if _sheets_api is None:
        from api_adapter import get_sheets_api
        _sheets_api = get_sheets_api()
    return _sheets_api

def get_sync_manager_lazy(signals=None):
    """Ленивая загрузка Sync Manager"""
    global _sync_manager
    if _sync_manager is None:
        from auto_sync import SyncManager
        _sync_manager = SyncManager(signals=signals, background_mode=True)
    return _sync_manager

def get_notification_engine_lazy():
    """Ленивая загрузка Notification Engine"""
    global _notification_engine
    if _notification_engine is None:
        from notifications.engine import start_background_poller
        _notification_engine = start_background_poller()
    return _notification_engine

def get_db_local_lazy():
    """Ленивая загрузка DB модуля"""
    global _db_local
    if _db_local is None:
        from user_app import db_local
        _db_local = db_local
        atexit.register(db_local.close_connection)
    return _db_local

def create_login_window_lazy():
    """Ленивое создание Login Window"""
    from user_app.login_window import LoginWindow
    return LoginWindow()

def create_main_window_lazy(user_data):
    """Ленивое создание Main Window"""
    from user_app.gui import MainWindow
    return MainWindow(user_data)

# ============================================================================
# BACKGROUND INITIALIZATION THREAD
# Загружает тяжелые компоненты в фоне
# ============================================================================

class BackgroundInitializer(QThread):
    """
    Асинхронная инициализация тяжелых компонентов
    
    Загружает в фоне:
    - Google Sheets API
    - Sync Manager
    - Notification Engine
    - DB connection
    
    Это позволяет показать UI сразу, пока компоненты инициализируются
    """
    
    component_ready = pyqtSignal(str, object)  # (name, result)
    all_ready = pyqtSignal()
    error_occurred = pyqtSignal(str, str)  # (component, error_msg)
    
    def __init__(self, sync_signals=None):
        super().__init__()
        self.sync_signals = sync_signals
        self.logger = logging.getLogger(__name__)
        
        # Компоненты для инициализации
        self.components = [
            ('db', self._init_db),
            ('credentials', self._init_credentials),
            ('sheets_api', self._init_sheets_api),
            ('sync_manager', self._init_sync_manager),
            ('notifications', self._init_notifications),
        ]
    
    def run(self):
        """Запуск фоновой инициализации"""
        self.logger.info("=== ФОНОВАЯ ИНИЦИАЛИЗАЦИЯ НАЧАТА ===")
        
        for name, init_func in self.components:
            try:
                self.logger.info(f"Инициализация: {name}...")
                result = init_func()
                self.component_ready.emit(name, result)
                self.logger.info(f"✓ {name} готов")
            except Exception as e:
                error_msg = f"{name} failed: {str(e)}"
                self.logger.error(error_msg, exc_info=True)
                self.error_occurred.emit(name, str(e))
        
        self.logger.info("=== ФОНОВАЯ ИНИЦИАЛИЗАЦИЯ ЗАВЕРШЕНА ===")
        self.all_ready.emit()
    
    def _init_db(self):
        """Инициализация БД"""
        db = get_db_local_lazy()
        db.init_db()
        return db
    
    def _init_credentials(self):
        """Проверка credentials"""
        from config import get_credentials_file
        creds_path = get_credentials_file()
        if not creds_path.exists():
            raise FileNotFoundError(f"Credentials not found: {creds_path}")
        return creds_path
    
    def _init_sheets_api(self):
        """Инициализация Google Sheets API"""
        api = get_sheets_api_lazy()
        if not api.check_credentials():
            raise RuntimeError("Invalid Google Sheets credentials")
        return api
    
    def _init_sync_manager(self):
        """Инициализация Sync Manager"""
        manager = get_sync_manager_lazy(self.sync_signals)
        if hasattr(manager, "start"):
            manager.start()
        elif hasattr(manager, "start_background"):
            manager.start_background()
        return manager
    
    def _init_notifications(self):
        """Инициализация Notification Engine"""
        return get_notification_engine_lazy()

# ============================================================================
# APPLICATION SIGNALS
# ============================================================================

class ApplicationSignals(QObject):
    """Сигналы приложения"""
    app_started = pyqtSignal()
    app_shutdown = pyqtSignal()
    login_attempt = pyqtSignal(str)
    login_success = pyqtSignal(dict)
    login_failed = pyqtSignal(str)
    sync_status_changed = pyqtSignal(bool)
    sync_progress = pyqtSignal(int, int)
    sync_finished = pyqtSignal(bool)

# ============================================================================
# APPLICATION MANAGER
# ============================================================================

class ApplicationManager(QObject):
    """
    Менеджер приложения с оптимизациями:
    - Lazy loading модулей
    - Асинхронная инициализация
    - Немедленный показ UI
    """
    
    def __init__(self):
        super().__init__()
        
        # QApplication
        self.app = QApplication(sys.argv)
        self.app.setStyle("Fusion")
        self.app.setApplicationName("WorkTimeTracker")
        self.app.setApplicationVersion("1.0.0")
        self.app.setQuitOnLastWindowClosed(False)
        
        # Состояние
        self.login_window = None
        self.main_window = None
        self.signals = ApplicationSignals()
        
        # Компоненты (загружаются в фоне)
        self.sheets_api = None
        self.sync_manager = None
        self.bg_initializer = None
        
        # Сигналы синхронизации
        from user_app.signals import SyncSignals
        self.sync_signals = SyncSignals()
        
        # Обработчик ошибок
        sys.excepthook = self.handle_uncaught_exception
        
        # Запуск
        self._quick_start()
    
    def _quick_start(self):
        """
        Быстрый старт приложения
        
        1. Показываем Login Window СРАЗУ
        2. Запускаем фоновую инициализацию
        3. Компоненты готовы → разрешаем вход
        """
        try:
            logger = logging.getLogger(__name__)
            logger.info("=== БЫСТРЫЙ СТАРТ ПРИЛОЖЕНИЯ ===")
            
            # Создаем Login Window (легкий)
            self.login_window = create_login_window_lazy()
            self.login_window.login_requested.connect(self._on_login_attempt)
            
            # Показываем окно СРАЗУ
            self.login_window.show()
            logger.info("✓ Login Window показан")
            
            # Запускаем фоновую инициализацию
            self._start_background_init()
            
            # Сигнализируем о старте
            self.signals.app_started.emit()
            
            logger.info("=== СТАРТ ЗАВЕРШЕН (UI готов) ===")
            
        except Exception as e:
            self._show_error("Startup Error", f"Failed to start: {e}")
            sys.exit(1)
    
    def _start_background_init(self):
        """Запуск фоновой инициализации"""
        logger = logging.getLogger(__name__)
        logger.info("Запуск фоновой инициализации...")
        
        self.bg_initializer = BackgroundInitializer(self.sync_signals)
        self.bg_initializer.component_ready.connect(self._on_component_ready)
        self.bg_initializer.all_ready.connect(self._on_all_components_ready)
        self.bg_initializer.error_occurred.connect(self._on_init_error)
        
        # Блокируем кнопку входа до готовности
        if self.login_window:
            self.login_window.set_loading(True, "Инициализация...")
        
        # Запускаем
        self.bg_initializer.start()
    
    def _on_component_ready(self, name: str, result):
        """Обработка готовности компонента"""
        logger = logging.getLogger(__name__)
        logger.info(f"Компонент готов: {name}")
        
        # Сохраняем ссылки на важные компоненты
        if name == 'sheets_api':
            self.sheets_api = result
        elif name == 'sync_manager':
            self.sync_manager = result
        
        # Обновляем статус в Login Window
        if self.login_window:
            status_messages = {
                'db': "База данных готова",
                'credentials': "Credentials проверены",
                'sheets_api': "Google Sheets подключен",
                'sync_manager': "Синхронизация запущена",
                'notifications': "Уведомления активированы",
            }
            message = status_messages.get(name, f"{name} готов")
            self.login_window.set_loading(True, message)
    
    def _on_all_components_ready(self):
        """Все компоненты готовы"""
        logger = logging.getLogger(__name__)
        logger.info("=== ВСЕ КОМПОНЕНТЫ ГОТОВЫ ===")
        
        # Разблокируем вход
        if self.login_window:
            self.login_window.set_loading(False)
    
    def _on_init_error(self, component: str, error_msg: str):
        """Ошибка инициализации компонента"""
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка инициализации {component}: {error_msg}")
        
        # Показываем ошибку пользователю
        if self.login_window:
            self.login_window.set_loading(False)
            self.login_window.show_error(
                f"Ошибка инициализации",
                f"Не удалось инициализировать {component}:\n{error_msg}\n\n"
                f"Приложение может работать с ограничениями."
            )
    
    def _on_login_attempt(self, email: str, password: str):
        """Попытка входа"""
        logger = logging.getLogger(__name__)
        logger.info(f"Login attempt: {email}")
        
        # Проверяем, готовы ли компоненты
        if self.bg_initializer and self.bg_initializer.isRunning():
            if self.login_window:
                self.login_window.show_error(
                    "Инициализация не завершена",
                    "Пожалуйста, подождите окончания инициализации"
                )
            return
        
        # Обработка входа (импортируем при необходимости)
        try:
            from user_app.api import authenticate_user
            
            user_data = authenticate_user(email, password)
            if user_data:
                self._on_login_success(user_data)
            else:
                self._on_login_failed("Неверный email или пароль")
        
        except Exception as e:
            logger.error(f"Login error: {e}", exc_info=True)
            self._on_login_failed(f"Ошибка входа: {e}")
    
    def _on_login_success(self, user_data: Dict[str, Any]):
        """Успешный вход"""
        logger = logging.getLogger(__name__)
        logger.info(f"Login successful: {user_data.get('email')}")
        
        self.signals.login_success.emit(user_data)
        
        # Создаем Main Window (только сейчас, когда нужно)
        self.main_window = create_main_window_lazy(user_data)
        self.main_window.show()
        
        # Скрываем Login Window
        if self.login_window:
            self.login_window.hide()
    
    def _on_login_failed(self, error_msg: str):
        """Ошибка входа"""
        logger = logging.getLogger(__name__)
        logger.warning(f"Login failed: {error_msg}")
        
        self.signals.login_failed.emit(error_msg)
        
        if self.login_window:
            self.login_window.show_error("Ошибка входа", error_msg)
    
    def _show_error(self, title: str, message: str):
        """Показать ошибку"""
        QMessageBox.critical(None, title, message)
    
    def handle_uncaught_exception(self, exc_type, exc_value, exc_traceback):
        """Обработка неперехваченных исключений"""
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        logger = logging.getLogger(__name__)
        logger.critical(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, exc_traceback)
        )
        
        self._show_error(
            "Critical Error",
            f"An uncaught exception occurred:\n{exc_value}\n\n"
            f"The application will try to continue."
        )
    
    def run(self):
        """Запуск приложения"""
        return self.app.exec_()
    
    def shutdown(self):
        """Выключение приложения"""
        logger = logging.getLogger(__name__)
        logger.info("=== SHUTDOWN STARTED ===")
        
        self.signals.app_shutdown.emit()
        
        # Останавливаем sync manager
        if self.sync_manager and hasattr(self.sync_manager, 'stop'):
            self.sync_manager.stop()
        
        # Ждем фоновую инициализацию
        if self.bg_initializer and self.bg_initializer.isRunning():
            self.bg_initializer.wait(1000)
        
        # Закрываем БД
        if _db_local:
            _db_local.close_connection()
        
        logger.info("=== SHUTDOWN COMPLETE ===")

# ============================================================================
# MAIN
# ============================================================================

def main():
    """Точка входа"""
    # Настройка логирования
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("="*60)
    logger.info("WorkTimeTracker - User App (OPTIMIZED)")
    logger.info("="*60)
    
    try:
        # Создаем и запускаем приложение
        manager = ApplicationManager()
        return_code = manager.run()
        
        # Выключение
        manager.shutdown()
        
        return return_code
    
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main())
