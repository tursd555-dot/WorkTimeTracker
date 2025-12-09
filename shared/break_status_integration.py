# shared/break_status_integration.py
"""
Интеграция системы перерывов со статусами пользователя

Автоматически вызывает break_manager когда пользователь меняет статус
"""
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Специальные статусы для перерывов
BREAK_STATUS = "Перерыв"
LUNCH_STATUS = "Обед"


class BreakStatusIntegration:
    """Интеграция перерывов со статусами"""
    
    def __init__(self, break_manager):
        self.break_mgr = break_manager
        self.active_breaks = {}  # email -> {status, start_time}
        logger.info("Break-Status integration initialized")
    
    def is_break_status(self, status: str) -> bool:
        """Проверяет, является ли статус перерывом"""
        return status in [BREAK_STATUS, LUNCH_STATUS]
    
    def on_status_change(
        self,
        email: str,
        old_status: str,
        new_status: str,
        session_id: Optional[str] = None
    ) -> bool:
        """
        Обрабатывает смену статуса
        
        Вызывается при каждой смене статуса пользователя
        """
        try:
            # Переход НА перерыв
            if self.is_break_status(new_status) and not self.is_break_status(old_status):
                return self._start_break(email, new_status, session_id)
            
            # Переход С перерыва
            elif self.is_break_status(old_status) and not self.is_break_status(new_status):
                return self._end_break(email, old_status)
            
            return True
            
        except Exception as e:
            logger.error(f"Error in status change handler: {e}", exc_info=True)
            return False
    
    def _start_break(self, email: str, status: str, session_id: Optional[str]) -> bool:
        """Начинает перерыв через BreakManager"""
        break_type = status  # "Перерыв" или "Обед"
        
        logger.info(f"Starting break for {email}: {break_type}")
        
        success, error = self.break_mgr.start_break(
            email=email,
            break_type=break_type,
            session_id=session_id
        )
        
        if not success:
            logger.warning(f"Failed to start break for {email}: {error}")
            # Можно показать уведомление пользователю
            return False
        
        # Сохраняем информацию об активном перерыве
        self.active_breaks[email] = {
            'break_type': break_type,
            'start_time': datetime.now()
        }
        
        logger.info(f"Break started successfully for {email}")
        return True
    
    def _end_break(self, email: str, status: str) -> bool:
        """Завершает перерыв через BreakManager"""
        break_type = status  # "Перерыв" или "Обед"
        
        logger.info(f"Ending break for {email}: {break_type}")
        
        success, error, duration = self.break_mgr.end_break(
            email=email,
            break_type=break_type
        )
        
        if not success:
            logger.warning(f"Failed to end break for {email}: {error}")
            return False
        
        # Удаляем из активных
        self.active_breaks.pop(email, None)
        
        logger.info(f"Break ended successfully for {email}: {duration} minutes")
        return True
    
    def get_active_break(self, email: str) -> Optional[dict]:
        """Получает информацию об активном перерыве"""
        return self.active_breaks.get(email)
    
    def on_logout(self, email: str) -> bool:
        """
        Завершает активный перерыв при logout пользователя
        
        Вызывается при:
        - Принудительном logout из админки
        - Завершении смены пользователем
        - Автоматическом logout
        """
        try:
            # Проверяем есть ли активный перерыв
            if email not in self.active_breaks:
                logger.debug(f"No active break for {email} on logout")
                return True
            
            break_info = self.active_breaks[email]
            break_type = break_info['break_type']
            
            logger.info(f"Auto-ending break on logout for {email}: {break_type}")
            
            # Завершаем перерыв
            success, error, duration = self.break_mgr.end_break(
                email=email,
                break_type=break_type
            )
            
            if not success:
                logger.error(f"Failed to end break on logout for {email}: {error}")
                # Принудительно удаляем из активных (чтобы не "зависнуть")
                self.active_breaks.pop(email, None)
                return False
            
            # Удаляем из активных
            self.active_breaks.pop(email, None)
            
            logger.info(f"Break auto-ended on logout for {email}: {duration} minutes")
            return True
            
        except Exception as e:
            logger.error(f"Error in logout handler for {email}: {e}", exc_info=True)
            # Принудительно удаляем из активных
            self.active_breaks.pop(email, None)
            return False


# Глобальный экземпляр (инициализируется в main)
_integration = None


def init_integration(break_manager):
    """Инициализирует интеграцию"""
    global _integration
    _integration = BreakStatusIntegration(break_manager)
    logger.info("Global break integration initialized")
    return _integration


def get_integration() -> Optional[BreakStatusIntegration]:
    """Получает глобальный экземпляр"""
    return _integration


def on_status_change(email: str, old_status: str, new_status: str, session_id: Optional[str] = None) -> bool:
    """
    Хук для обработки смены статуса
    
    Вызывается из user_app при каждой смене статуса
    """
    if _integration:
        return _integration.on_status_change(email, old_status, new_status, session_id)
    else:
        logger.warning("Break integration not initialized, status change ignored")
        return True


def on_logout(email: str) -> bool:
    """
    Хук для обработки logout пользователя
    
    Завершает активный перерыв если он есть
    Вызывается из user_app при logout/завершении смены
    """
    if _integration:
        return _integration.on_logout(email)
    else:
        logger.warning("Break integration not initialized, logout ignored")
        return True


if __name__ == "__main__":
    print("Break-Status Integration module")
    print("Usage: import in user_app and call on_status_change() on every status change")