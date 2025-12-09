"""
Graceful Degradation Manager для WorkTimeTracker

Автоматическое управление режимами работы системы в зависимости
от состояния компонентов.

Режимы работы:
- FULL: Все работает (Google Sheets + Telegram + все функции)
- DEGRADED: Ограниченная функциональность (только Sheets или только Telegram)
- OFFLINE: Только локальная БД (синхронизация в очередь)
- EMERGENCY: Минимальный функционал (только логин/логаут)

Автоматическое переключение на основе Health Checks.

Usage:
    from shared.resilience.degradation_manager import get_degradation_manager
    from shared.health import get_health_checker
    
    # Создаем manager
    manager = get_degradation_manager(
        health_checker=get_health_checker()
    )
    
    # Запускаем автоматическую оценку
    manager.start_auto_evaluation(interval=30)
    
    # Текущий режим
    mode = manager.get_current_mode()
    if mode == SystemMode.OFFLINE:
        # Работаем только локально
        work_offline()

Author: WorkTimeTracker Resilience Team
Date: 2025-12-04
"""

import logging
import threading
import time
from typing import Optional, Callable, Dict, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS
# ============================================================================

class SystemMode(Enum):
    """Режимы работы системы"""
    FULL = "full"                # Все работает
    DEGRADED = "degraded"        # Ограниченная функциональность
    OFFLINE = "offline"          # Только локальная работа
    EMERGENCY = "emergency"      # Минимальная функциональность


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class ModeTransition:
    """История перехода между режимами"""
    timestamp: datetime
    from_mode: SystemMode
    to_mode: SystemMode
    reason: str
    component_statuses: Dict = field(default_factory=dict)


@dataclass
class ModeCapabilities:
    """Возможности в текущем режиме"""
    sync_enabled: bool
    notifications_enabled: bool
    full_features: bool
    read_only: bool
    description: str


# ============================================================================
# DEGRADATION MANAGER
# ============================================================================

class DegradationManager:
    """
    Управление деградацией системы при сбоях
    
    Автоматически переключает режимы работы в зависимости от
    состояния компонентов (на основе Health Checks).
    
    Parameters:
        health_checker: HealthChecker instance для проверки компонентов
        mode_change_callback: Функция, вызываемая при смене режима
        notification_callback: Функция для уведомлений пользователей
    
    Example:
        >>> from shared.health import get_health_checker
        >>> 
        >>> manager = DegradationManager(
        ...     health_checker=get_health_checker()
        ... )
        >>> 
        >>> # Автоматическая оценка каждые 30 секунд
        >>> manager.start_auto_evaluation(interval=30)
        >>> 
        >>> # Проверить текущий режим
        >>> mode = manager.get_current_mode()
        >>> if mode == SystemMode.OFFLINE:
        ...     work_offline()
    """
    
    def __init__(
        self,
        health_checker,
        mode_change_callback: Optional[Callable] = None,
        notification_callback: Optional[Callable] = None
    ):
        self.health_checker = health_checker
        self.mode_change_callback = mode_change_callback
        self.notification_callback = notification_callback
        
        # Текущий режим
        self.current_mode = SystemMode.FULL
        
        # История переходов
        self.mode_history: List[ModeTransition] = []
        
        # Оценка режимов
        self.evaluation_thread: Optional[threading.Thread] = None
        self.running = False
        
        # Thread safety
        self.lock = threading.Lock()
        
        # Метрики
        self.metrics = {
            'mode_changes': 0,
            'time_in_full': 0.0,
            'time_in_degraded': 0.0,
            'time_in_offline': 0.0,
            'time_in_emergency': 0.0,
            'last_evaluation': None
        }
        self.last_mode_change = datetime.now()
        
        logger.info("DegradationManager initialized")
    
    def evaluate_mode(self) -> SystemMode:
        """
        Оценить текущий режим работы на основе Health Checks
        
        Returns:
            Рекомендуемый SystemMode
        """
        if not self.health_checker:
            logger.warning("No health checker available, staying in current mode")
            return self.current_mode
        
        # Получаем статусы всех компонентов
        statuses = self.health_checker.statuses
        
        # Проверяем критичные компоненты
        db_healthy = statuses.get('database', None)
        sheets_healthy = statuses.get('sheets_api', None)
        telegram_healthy = statuses.get('telegram_api', None)
        internet_healthy = statuses.get('internet', None)
        
        # Проверяем БД (критично для всех режимов)
        db_ok = db_healthy and db_healthy.healthy if db_healthy else False
        
        # Проверяем внешние сервисы
        sheets_ok = sheets_healthy and sheets_healthy.healthy if sheets_healthy else False
        telegram_ok = telegram_healthy and telegram_healthy.healthy if telegram_healthy else False
        internet_ok = internet_healthy and internet_healthy.healthy if internet_healthy else False
        
        # Определяем режим по приоритету
        if not db_ok:
            # БД недоступна - EMERGENCY режим
            new_mode = SystemMode.EMERGENCY
            reason = "Database unhealthy"
        
        elif sheets_ok and telegram_ok and internet_ok:
            # Все работает - FULL режим
            new_mode = SystemMode.FULL
            reason = "All systems operational"
        
        elif sheets_ok and internet_ok:
            # Sheets работает, но Telegram нет - DEGRADED режим
            new_mode = SystemMode.DEGRADED
            reason = "Telegram unavailable, sync enabled"
        
        elif internet_ok and db_ok:
            # Интернет есть, но сервисы недоступны - DEGRADED
            new_mode = SystemMode.DEGRADED
            reason = "External services unavailable"
        
        else:
            # Нет интернета или все внешние сервисы down - OFFLINE режим
            new_mode = SystemMode.OFFLINE
            reason = "No internet or all external services down"
        
        # Логируем оценку
        logger.debug(
            f"Mode evaluation: DB={db_ok}, Sheets={sheets_ok}, "
            f"Telegram={telegram_ok}, Internet={internet_ok} → {new_mode.value}"
        )
        
        # Если режим изменился, переключаем
        if new_mode != self.current_mode:
            self._switch_mode(new_mode, reason, {
                'database': db_ok,
                'sheets_api': sheets_ok,
                'telegram_api': telegram_ok,
                'internet': internet_ok
            })
        
        with self.lock:
            self.metrics['last_evaluation'] = datetime.now()
        
        return new_mode
    
    def force_mode(self, mode: SystemMode, reason: str = "Manual override"):
        """
        Принудительно установить режим (для админа)
        
        Args:
            mode: Новый режим
            reason: Причина смены
        """
        logger.info(f"Forcing mode to {mode.value}: {reason}")
        self._switch_mode(mode, reason, {})
    
    def get_current_mode(self) -> SystemMode:
        """Получить текущий режим работы"""
        return self.current_mode
    
    def get_capabilities(self) -> ModeCapabilities:
        """
        Получить возможности в текущем режиме
        
        Returns:
            ModeCapabilities с описанием доступных функций
        """
        mode = self.current_mode
        
        if mode == SystemMode.FULL:
            return ModeCapabilities(
                sync_enabled=True,
                notifications_enabled=True,
                full_features=True,
                read_only=False,
                description="Все функции доступны"
            )
        
        elif mode == SystemMode.DEGRADED:
            return ModeCapabilities(
                sync_enabled=True,
                notifications_enabled=False,
                full_features=True,
                read_only=False,
                description="Синхронизация работает, уведомления отключены"
            )
        
        elif mode == SystemMode.OFFLINE:
            return ModeCapabilities(
                sync_enabled=False,
                notifications_enabled=False,
                full_features=True,
                read_only=False,
                description="Работа только с локальной БД, синхронизация в очередь"
            )
        
        elif mode == SystemMode.EMERGENCY:
            return ModeCapabilities(
                sync_enabled=False,
                notifications_enabled=False,
                full_features=False,
                read_only=True,
                description="Только просмотр данных, минимальный функционал"
            )
    
    def get_mode_history(self, limit: int = 10) -> List[ModeTransition]:
        """
        Получить историю переходов между режимами
        
        Args:
            limit: Максимальное количество записей
        
        Returns:
            Список последних переходов
        """
        with self.lock:
            return self.mode_history[-limit:]
    
    def get_metrics(self) -> Dict:
        """Получить метрики degradation manager"""
        self._update_time_metrics()
        
        with self.lock:
            return {
                **self.metrics,
                'current_mode': self.current_mode.value,
                'time_in_current_mode': (datetime.now() - self.last_mode_change).total_seconds(),
                'history_length': len(self.mode_history),
                'evaluation_active': self.running
            }
    
    def start_auto_evaluation(self, interval: int = 30):
        """
        Запустить автоматическую оценку режима
        
        Args:
            interval: Интервал оценки в секундах (default: 30)
        """
        if self.running:
            logger.warning("Auto evaluation already running")
            return
        
        self.running = True
        
        def evaluation_loop():
            logger.info(f"Auto evaluation started (interval={interval}s)")
            
            while self.running:
                try:
                    # Оцениваем режим
                    self.evaluate_mode()
                    
                    # Спим до следующей оценки
                    time.sleep(interval)
                
                except Exception as e:
                    logger.error(f"Auto evaluation error: {e}", exc_info=True)
                    time.sleep(interval)
        
        self.evaluation_thread = threading.Thread(
            target=evaluation_loop,
            name="DegradationEvaluator",
            daemon=True
        )
        self.evaluation_thread.start()
    
    def stop_auto_evaluation(self):
        """Остановить автоматическую оценку"""
        if not self.running:
            return
        
        logger.info("Stopping auto evaluation...")
        self.running = False
        
        if self.evaluation_thread:
            self.evaluation_thread.join(timeout=5)
        
        logger.info("Auto evaluation stopped")
    
    # ========================================================================
    # PRIVATE METHODS
    # ========================================================================
    
    def _switch_mode(self, new_mode: SystemMode, reason: str, component_statuses: Dict):
        """Переключить режим работы"""
        old_mode = self.current_mode
        
        if old_mode == new_mode:
            return
        
        # Обновляем метрики времени
        self._update_time_metrics()
        
        with self.lock:
            # Сохраняем переход
            transition = ModeTransition(
                timestamp=datetime.now(),
                from_mode=old_mode,
                to_mode=new_mode,
                reason=reason,
                component_statuses=component_statuses
            )
            self.mode_history.append(transition)
            
            # Обновляем режим
            self.current_mode = new_mode
            self.last_mode_change = datetime.now()
            self.metrics['mode_changes'] += 1
        
        # Логируем
        logger.warning(
            f"🔄 System mode changed: {old_mode.value} → {new_mode.value} | "
            f"Reason: {reason}"
        )
        
        # Применяем изменения
        self._apply_mode(new_mode)
        
        # Уведомляем пользователей
        self._notify_mode_change(old_mode, new_mode, reason)
        
        # Вызываем callback если есть
        if self.mode_change_callback:
            try:
                self.mode_change_callback(old_mode, new_mode, reason)
            except Exception as e:
                logger.error(f"Mode change callback error: {e}")
    
    def _apply_mode(self, mode: SystemMode):
        """
        Применить режим работы
        
        Здесь можно добавить код для реальной активации/деактивации
        функций системы.
        """
        capabilities = self.get_capabilities()
        
        logger.info(f"Applying mode {mode.value}:")
        logger.info(f"  - Sync: {capabilities.sync_enabled}")
        logger.info(f"  - Notifications: {capabilities.notifications_enabled}")
        logger.info(f"  - Full features: {capabilities.full_features}")
        logger.info(f"  - Read only: {capabilities.read_only}")
        
        # TODO: Реальная интеграция
        # if mode == SystemMode.FULL:
        #     enable_sync()
        #     enable_notifications()
        #     enable_all_features()
        # elif mode == SystemMode.DEGRADED:
        #     enable_sync()
        #     disable_notifications()
        # elif mode == SystemMode.OFFLINE:
        #     disable_sync()
        #     enable_offline_mode()
        # elif mode == SystemMode.EMERGENCY:
        #     disable_sync()
        #     enable_read_only_mode()
    
    def _notify_mode_change(self, old_mode: SystemMode, new_mode: SystemMode, reason: str):
        """Уведомить пользователей о смене режима"""
        
        # Формируем сообщение
        if new_mode == SystemMode.FULL:
            icon = "✅"
            message = "Система восстановлена! Все функции доступны."
        elif new_mode == SystemMode.DEGRADED:
            icon = "⚠️"
            message = "Система работает в ограниченном режиме. Некоторые функции недоступны."
        elif new_mode == SystemMode.OFFLINE:
            icon = "📴"
            message = "Система в offline режиме. Работаем только с локальной БД."
        elif new_mode == SystemMode.EMERGENCY:
            icon = "🚨"
            message = "Система в аварийном режиме. Доступен только просмотр данных."
        else:
            icon = "ℹ️"
            message = f"Режим изменен: {new_mode.value}"
        
        notification = (
            f"{icon} РЕЖИМ СИСТЕМЫ ИЗМЕНЕН\n\n"
            f"Было: {old_mode.value}\n"
            f"Стало: {new_mode.value}\n\n"
            f"{message}\n\n"
            f"Причина: {reason}"
        )
        
        logger.info(f"Mode change notification: {notification}")
        
        # Используем callback если есть
        if self.notification_callback:
            try:
                self.notification_callback(notification)
            except Exception as e:
                logger.error(f"Notification callback error: {e}")
        else:
            # Пытаемся отправить через Telegram
            try:
                from config import TELEGRAM_MONITORING_CHAT_ID
                from telegram_api import send_message
                send_message(TELEGRAM_MONITORING_CHAT_ID, notification)
            except Exception as e:
                logger.debug(f"Could not send mode change notification: {e}")
    
    def _update_time_metrics(self):
        """Обновить метрики времени в режимах"""
        elapsed = (datetime.now() - self.last_mode_change).total_seconds()
        
        with self.lock:
            if self.current_mode == SystemMode.FULL:
                self.metrics['time_in_full'] += elapsed
            elif self.current_mode == SystemMode.DEGRADED:
                self.metrics['time_in_degraded'] += elapsed
            elif self.current_mode == SystemMode.OFFLINE:
                self.metrics['time_in_offline'] += elapsed
            elif self.current_mode == SystemMode.EMERGENCY:
                self.metrics['time_in_emergency'] += elapsed


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

_global_degradation_manager: Optional[DegradationManager] = None
_manager_lock = threading.Lock()


def get_degradation_manager(
    health_checker=None,
    mode_change_callback: Optional[Callable] = None,
    notification_callback: Optional[Callable] = None
) -> DegradationManager:
    """
    Получить глобальный degradation manager (singleton)
    
    Args:
        health_checker: HealthChecker instance
        mode_change_callback: Функция при смене режима
        notification_callback: Функция для уведомлений
    
    Returns:
        Глобальный экземпляр DegradationManager
    """
    global _global_degradation_manager
    
    if _global_degradation_manager is None:
        with _manager_lock:
            if _global_degradation_manager is None:
                if health_checker is None:
                    from shared.health import get_health_checker
                    health_checker = get_health_checker()
                
                _global_degradation_manager = DegradationManager(
                    health_checker=health_checker,
                    mode_change_callback=mode_change_callback,
                    notification_callback=notification_callback
                )
    
    return _global_degradation_manager


def stop_global_degradation_manager():
    """Остановить глобальный degradation manager"""
    global _global_degradation_manager
    
    if _global_degradation_manager:
        _global_degradation_manager.stop_auto_evaluation()
        _global_degradation_manager = None
