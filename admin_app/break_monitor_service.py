# admin_app/break_monitor_service.py
"""
Сервис мониторинга перерывов в реальном времени для отправки уведомлений

Проверяет активные перерывы каждую минуту и отправляет уведомления
при превышении лимитов (на 1+ минуту).
"""
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class BreakMonitorService:
    """Сервис мониторинга перерывов для уведомлений"""
    
    def __init__(self, break_manager):
        self.break_mgr = break_manager
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._check_interval = 60  # Проверка каждую минуту
    
    def start(self):
        """Запускает мониторинг"""
        if self._running:
            logger.warning("Monitor service already running")
            return
        
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("Break monitor service started")
    
    def stop(self):
        """Останавливает мониторинг"""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("Break monitor service stopped")
    
    def _monitor_loop(self):
        """Основной цикл мониторинга"""
        while self._running:
            try:
                self._check_active_breaks()
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}", exc_info=True)
            
            # Ждем до следующей проверки
            import time
            for _ in range(self._check_interval):
                if not self._running:
                    break
                time.sleep(1)
    
    def _check_active_breaks(self):
        """Проверяет активные перерывы и отправляет уведомления"""
        try:
            active_breaks = self.break_mgr.get_all_active_breaks()
            
            for break_data in active_breaks:
                email = break_data.get('Email', '').lower()
                if not email:
                    continue
                
                # Пропускаем тестовых пользователей
                if 'test' in email or 'example.com' in email:
                    continue
                
                break_type = break_data.get('BreakType', '')
                duration = break_data.get('Duration', 0)
                start_time_str = break_data.get('StartTime', '')
                
                # Получаем лимит из графика
                try:
                    schedule = self.break_mgr.get_user_schedule(email)
                    limit_minutes = 15 if break_type == 'Перерыв' else 60 if break_type == 'Обед' else 0
                    
                    if schedule and schedule.limits:
                        for limit in schedule.limits:
                            if limit.break_type == break_type:
                                limit_minutes = limit.time_minutes
                                break
                    
                    # Проверяем превышение (на 1+ минуту)
                    if limit_minutes > 0 and duration > limit_minutes:
                        overtime = duration - limit_minutes
                        
                        # Отправляем уведомление (с дебаунсингом)
                        try:
                            from shared.break_notifications_v2 import send_overtime_notification
                            send_overtime_notification(
                                email=email,
                                break_type=break_type,
                                duration=duration,
                                limit=limit_minutes,
                                overtime=overtime
                            )
                        except Exception as e:
                            logger.error(f"Failed to send overtime notification: {e}")
                
                except Exception as e:
                    logger.debug(f"Failed to check break for {email}: {e}")
        
        except Exception as e:
            logger.error(f"Error checking active breaks: {e}", exc_info=True)
