# telegram_api.py
"""
Обёртка для telegram_bot.notifier.TelegramNotifier

Используется shared/break_notifications.py
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class TelegramAPI:
    """
    Упрощённый API для отправки уведомлений
    
    Обёртка для TelegramNotifier с методами:
    - send_to_user(email, message) - в личку пользователю
    - send_to_admin_group(message) - в группу админов
    - send_to_monitoring(message) - в группу мониторинга
    """
    
    def __init__(self):
        """Инициализирует TelegramNotifier"""
        try:
            from telegram_bot.notifier import TelegramNotifier
            self.notifier = TelegramNotifier()
            logger.info("TelegramAPI initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize TelegramNotifier: {e}")
            raise
    
    def send_to_user(self, email: str, message: str, silent: bool = False) -> bool:
        """
        Отправляет сообщение пользователю в личку
        
        Args:
            email: Email пользователя (используется для поиска chat_id в таблице Users)
            message: Текст сообщения (поддерживает HTML)
            silent: Тихое уведомление (по умолчанию False)
        
        Returns:
            True если отправка успешна
        """
        try:
            return self.notifier.send_personal(email, message, silent=silent)
        except Exception as e:
            logger.error(f"Error sending to user {email}: {e}")
            return False
    
    def send_to_admin_group(self, message: str, silent: bool = False) -> bool:
        """
        Отправляет сообщение в группу админов
        
        Args:
            message: Текст сообщения (HTML)
            silent: Тихое уведомление
        
        Returns:
            True если успешно
        """
        try:
            return self.notifier.send_monitoring(message, silent=silent)
        except Exception as e:
            logger.error(f"Error sending to admin group: {e}")
            return False
    
    def send_to_monitoring(self, message: str, silent: bool = False) -> bool:
        """
        Отправляет сообщение в группу мониторинга (превышения лимитов)
        
        Args:
            message: Текст сообщения (HTML)
            silent: Тихое уведомление (по умолчанию False для важных событий)
        
        Returns:
            True если успешно
        """
        try:
            return self.notifier.send_monitoring(message, silent=silent)
        except Exception as e:
            logger.error(f"Error sending to monitoring: {e}")
            return False
    
    def send_service(self, message: str, silent: bool = False) -> bool:
        """
        Отправляет служебное сообщение админу
        
        Args:
            message: Текст сообщения
            silent: Тихое уведомление
        
        Returns:
            True если успешно
        """
        try:
            return self.notifier.send_service(message, silent=silent)
        except Exception as e:
            logger.error(f"Error sending service message: {e}")
            return False


# Singleton instance
_api_instance = None


def get_telegram_api() -> TelegramAPI:
    """Возвращает singleton instance TelegramAPI"""
    global _api_instance
    if _api_instance is None:
        _api_instance = TelegramAPI()
    return _api_instance


if __name__ == "__main__":
    # Тест модуля
    print("telegram_api module")
    print("Testing TelegramAPI...")
    
    try:
        api = TelegramAPI()
        print("✓ TelegramAPI initialized")
        print(f"  - Notifier: {api.notifier}")
        print(f"  - Admin chat: {api.notifier.admin_chat}")
        print(f"  - Monitoring chat: {api.notifier.monitoring_chat}")
    except Exception as e:
        print(f"✗ Failed to initialize: {e}")
