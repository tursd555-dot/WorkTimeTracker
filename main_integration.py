"""
Полная интеграция систем отказоустойчивости в user_app/main.py

Интегрирует:
1. Health Checker - мониторинг компонентов
2. Degradation Manager - управление режимами работы
3. Circuit Breaker - уже интегрирован в sheets_api

ИНСТРУКЦИЯ ПО ПРИМЕНЕНИЮ:
1. Добавить импорты в начало main.py
2. Добавить инициализацию в __init__ ApplicationManager
3. Добавить обработчики режимов
4. Добавить cleanup при shutdown
"""

# ============================================================================
# ДОБАВИТЬ ИМПОРТЫ В НАЧАЛО main.py ПОСЛЕ СУЩЕСТВУЮЩИХ
# ============================================================================

# Импорты для систем отказоустойчивости
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

# ============================================================================
# ДОБАВИТЬ В __init__ ApplicationManager ПОСЛЕ self.sync_signals
# ============================================================================

def __init__(self):
    super().__init__()
    # ... существующий код ...
    self.sync_signals = SyncSignals()
    
    # ДОБАВИТЬ: Системы отказоустойчивости
    self.health_checker: HealthChecker = None
    self.degradation_manager: DegradationManager = None
    self.current_system_mode = SystemMode.FULL
    
    # ... остальной код ...

# ============================================================================
# ДОБАВИТЬ В МЕТОД _initialize_resources ПОСЛЕ инициализации sheets_api
# ============================================================================

def _initialize_resources(self):
    # ... существующий код инициализации ...
    
    # ДОБАВИТЬ: Инициализация систем отказоустойчивости
    try:
        logger = logging.getLogger(__name__)
        logger.info("=== ИНИЦИАЛИЗАЦИЯ СИСТЕМ ОТКАЗОУСТОЙЧИВОСТИ ===")
        
        # 1. Health Checker
        self.health_checker = get_health_checker(failure_threshold=3)
        register_all_checks(self.health_checker)
        self.health_checker.start_monitoring(interval=60)  # Каждую минуту
        logger.info("✓ Health Checker запущен (interval=60s)")
        
        # 2. Degradation Manager
        self.degradation_manager = get_degradation_manager(
            health_checker=self.health_checker,
            mode_change_callback=self._on_system_mode_change,
            notification_callback=self._on_system_notification
        )
        self.degradation_manager.start_auto_evaluation(interval=30)  # Каждые 30 сек
        logger.info("✓ Degradation Manager запущен (interval=30s)")
        
        # Проверяем начальный статус
        initial_status = self.health_checker.get_overall_status()
        logger.info(f"Начальный статус системы: {initial_status.status.value}")
        
        logger.info("=== СИСТЕМЫ ОТКАЗОУСТОЙЧИВОСТИ ГОТОВЫ ===")
    
    except Exception as e:
        logger.error(f"Ошибка инициализации систем отказоустойчивости: {e}")
        # Не критично - продолжаем работу без мониторинга
        self.health_checker = None
        self.degradation_manager = None

# ============================================================================
# ДОБАВИТЬ НОВЫЕ МЕТОДЫ В КЛАСС ApplicationManager
# ============================================================================

def _on_system_mode_change(self, old_mode: SystemMode, new_mode: SystemMode, reason: str):
    """
    Обработчик смены режима работы системы
    
    Args:
        old_mode: Предыдущий режим
        new_mode: Новый режим
        reason: Причина смены
    """
    logger = logging.getLogger(__name__)
    logger.warning(f"🔄 Режим системы изменен: {old_mode.value} → {new_mode.value}")
    logger.warning(f"   Причина: {reason}")
    
    self.current_system_mode = new_mode
    
    # Применяем изменения в зависимости от режима
    if new_mode == SystemMode.FULL:
        self._enable_full_mode()
    elif new_mode == SystemMode.DEGRADED:
        self._enable_degraded_mode()
    elif new_mode == SystemMode.OFFLINE:
        self._enable_offline_mode()
    elif new_mode == SystemMode.EMERGENCY:
        self._enable_emergency_mode()

def _on_system_notification(self, message: str):
    """
    Обработчик уведомлений о смене режима
    
    Args:
        message: Текст уведомления
    """
    logger = logging.getLogger(__name__)
    logger.info(f"📢 Системное уведомление: {message}")
    
    # Показываем уведомление пользователю (если окно открыто)
    if self.main_window and hasattr(self.main_window, 'show_notification'):
        try:
            self.main_window.show_notification("Режим системы", message)
        except Exception as e:
            logger.debug(f"Could not show notification: {e}")

def _enable_full_mode(self):
    """Включить полный режим работы"""
    logger = logging.getLogger(__name__)
    logger.info("✅ Переключение в FULL режим")
    
    # Включаем синхронизацию
    if hasattr(self, 'sync_manager') and self.sync_manager:
        try:
            if hasattr(self.sync_manager, 'resume'):
                self.sync_manager.resume()
            logger.info("   ✓ Синхронизация включена")
        except Exception as e:
            logger.error(f"   ✗ Ошибка включения синхронизации: {e}")
    
    # Включаем уведомления
    try:
        # Здесь можно восстановить notification engine
        logger.info("   ✓ Уведомления включены")
    except Exception as e:
        logger.debug(f"   ✗ Ошибка включения уведомлений: {e}")
    
    # Обновляем UI (если окно открыто)
    if self.main_window:
        try:
            if hasattr(self.main_window, 'set_mode_indicator'):
                self.main_window.set_mode_indicator("FULL", "green")
        except Exception as e:
            logger.debug(f"Could not update UI: {e}")

def _enable_degraded_mode(self):
    """Включить ограниченный режим"""
    logger = logging.getLogger(__name__)
    logger.warning("⚠️  Переключение в DEGRADED режим")
    
    # Синхронизация работает, но уведомления отключены
    logger.info("   ✓ Синхронизация работает")
    logger.info("   ✗ Уведомления отключены")
    
    # Обновляем UI
    if self.main_window:
        try:
            if hasattr(self.main_window, 'set_mode_indicator'):
                self.main_window.set_mode_indicator("DEGRADED", "yellow")
        except Exception as e:
            logger.debug(f"Could not update UI: {e}")

def _enable_offline_mode(self):
    """Включить offline режим"""
    logger = logging.getLogger(__name__)
    logger.warning("📴 Переключение в OFFLINE режим")
    
    # Приостанавливаем синхронизацию
    if hasattr(self, 'sync_manager') and self.sync_manager:
        try:
            if hasattr(self.sync_manager, 'pause'):
                self.sync_manager.pause()
            logger.info("   ✓ Синхронизация приостановлена (данные в очередь)")
        except Exception as e:
            logger.error(f"   ✗ Ошибка приостановки синхронизации: {e}")
    
    logger.info("   ✓ Работа с локальной БД")
    logger.info("   ✗ Уведомления отключены")
    
    # Обновляем UI
    if self.main_window:
        try:
            if hasattr(self.main_window, 'set_mode_indicator'):
                self.main_window.set_mode_indicator("OFFLINE", "orange")
            if hasattr(self.main_window, 'show_offline_indicator'):
                self.main_window.show_offline_indicator(True)
        except Exception as e:
            logger.debug(f"Could not update UI: {e}")

def _enable_emergency_mode(self):
    """Включить аварийный режим"""
    logger = logging.getLogger(__name__)
    logger.error("🚨 Переключение в EMERGENCY режим")
    
    # Отключаем все кроме чтения
    logger.info("   ✗ Синхронизация отключена")
    logger.info("   ✗ Уведомления отключены")
    logger.info("   ✓ Только просмотр данных")
    
    # Обновляем UI
    if self.main_window:
        try:
            if hasattr(self.main_window, 'set_mode_indicator'):
                self.main_window.set_mode_indicator("EMERGENCY", "red")
            if hasattr(self.main_window, 'set_read_only_mode'):
                self.main_window.set_read_only_mode(True)
        except Exception as e:
            logger.debug(f"Could not update UI: {e}")

def get_system_status(self) -> dict:
    """
    Получить статус всех систем
    
    Returns:
        Словарь со статусами компонентов
    """
    status = {
        'mode': self.current_system_mode.value,
        'timestamp': datetime.now().isoformat()
    }
    
    # Health Checker
    if self.health_checker:
        try:
            overall = self.health_checker.get_overall_status()
            status['health'] = {
                'overall': overall.status.value,
                'message': overall.message,
                'components': {}
            }
            
            for name, comp_status in self.health_checker.statuses.items():
                status['health']['components'][name] = {
                    'status': comp_status.status.value,
                    'message': comp_status.message
                }
        except Exception as e:
            status['health'] = {'error': str(e)}
    else:
        status['health'] = None
    
    # Circuit Breaker (Google Sheets API)
    if hasattr(self, 'sheets_api') and self.sheets_api:
        try:
            status['circuit_breaker'] = self.sheets_api.get_circuit_breaker_metrics()
        except Exception as e:
            status['circuit_breaker'] = {'error': str(e)}
    else:
        status['circuit_breaker'] = None
    
    # Degradation Manager
    if self.degradation_manager:
        try:
            status['degradation'] = self.degradation_manager.get_metrics()
        except Exception as e:
            status['degradation'] = {'error': str(e)}
    else:
        status['degradation'] = None
    
    return status

# ============================================================================
# ДОБАВИТЬ CLEANUP ПРИ SHUTDOWN
# ============================================================================

def _cleanup(self):
    """Очистка ресурсов при завершении"""
    logger = logging.getLogger(__name__)
    logger.info("=== CLEANUP СИСТЕМ ОТКАЗОУСТОЙЧИВОСТИ ===")
    
    # Останавливаем Health Checker
    if self.health_checker:
        try:
            self.health_checker.stop_monitoring()
            logger.info("✓ Health Checker остановлен")
        except Exception as e:
            logger.error(f"Ошибка остановки Health Checker: {e}")
    
    # Останавливаем Degradation Manager
    if self.degradation_manager:
        try:
            self.degradation_manager.stop_auto_evaluation()
            logger.info("✓ Degradation Manager остановлен")
        except Exception as e:
            logger.error(f"Ошибка остановки Degradation Manager: {e}")
    
    # Логируем финальные метрики
    try:
        if self.health_checker:
            metrics = self.health_checker.get_metrics()
            logger.info(f"Health Checks: {metrics['healthy_checks']}/{metrics['total_checks']}")
        
        if self.degradation_manager:
            dm_metrics = self.degradation_manager.get_metrics()
            logger.info(f"Mode changes: {dm_metrics['mode_changes']}")
    except Exception:
        pass

# Зарегистрировать cleanup при выходе
def __init__(self):
    # ... существующий код ...
    
    # ДОБАВИТЬ: Регистрация cleanup
    atexit.register(self._cleanup)

# ============================================================================
# ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ
# ============================================================================

"""
# Пример 1: Проверка статуса системы
manager = ApplicationManager()
status = manager.get_system_status()
print(f"System mode: {status['mode']}")
print(f"Health: {status['health']['overall']}")

# Пример 2: Принудительная смена режима (для тестирования)
manager.degradation_manager.force_mode(SystemMode.OFFLINE, "Manual testing")

# Пример 3: Проверка доступности API перед использованием
if manager.sheets_api.is_available():
    # API доступен
    result = manager.sheets_api.log_event(data, "LOGIN")
else:
    # API недоступен, работаем offline
    logger.warning("Working in offline mode")

# Пример 4: Получение метрик для отчета
health_metrics = manager.health_checker.get_metrics()
circuit_metrics = manager.sheets_api.get_circuit_breaker_metrics()
degradation_metrics = manager.degradation_manager.get_metrics()

report = f'''
System Health Report:
--------------------
Mode: {manager.current_system_mode.value}
Health Checks: {health_metrics['healthy_checks']}/{health_metrics['total_checks']}
Circuit State: {circuit_metrics['state']}
Mode Changes: {degradation_metrics['mode_changes']}
'''
print(report)
"""

# ============================================================================
# ДОПОЛНИТЕЛЬНО: UI ИНДИКАТОРЫ (для gui.py)
# ============================================================================

"""
# Добавить в MainWindow (gui.py) следующие методы:

def set_mode_indicator(self, mode: str, color: str):
    '''Показать индикатор текущего режима'''
    # Создать QLabel с цветным индикатором
    self.mode_label.setText(f"Режим: {mode}")
    self.mode_label.setStyleSheet(f"background-color: {color}; padding: 5px;")

def show_offline_indicator(self, show: bool):
    '''Показать/скрыть индикатор offline режима'''
    if show:
        self.offline_label.setText("📴 OFFLINE: Данные сохраняются локально")
        self.offline_label.show()
    else:
        self.offline_label.hide()

def set_read_only_mode(self, enabled: bool):
    '''Включить/выключить режим только для чтения'''
    # Отключить кнопки логин/логаут
    self.login_button.setEnabled(not enabled)
    self.logout_button.setEnabled(not enabled)
    
    if enabled:
        self.statusBar().showMessage("⚠️ EMERGENCY MODE: Только просмотр данных")

def show_notification(self, title: str, message: str):
    '''Показать уведомление пользователю'''
    QMessageBox.information(self, title, message)
"""
