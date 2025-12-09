# shared/break_notifications.py
"""
Telegram уведомления для системы перерывов v2.1 (FIXED: WiFi freeze)

Отправляет уведомления:
- Пользователю в личку при превышении лимита
- Админу в группу при критических нарушениях
- Напоминания о доступных перерывах (опционально)

ИСПРАВЛЕНИЕ: Все сетевые вызовы обернуты в async + проверку интернета
"""
import logging
import threading
from datetime import datetime
from typing import Optional
from functools import wraps

logger = logging.getLogger(__name__)


def check_internet_available() -> bool:
    """
    Быстрая проверка доступности интернета
    
    Returns:
        True если интернет доступен
    """
    try:
        import socket
        # Быстрая проверка доступности Google DNS
        socket.create_connection(("8.8.8.8", 53), timeout=2)
        return True
    except OSError:
        return False


def async_notification(func):
    """
    Декоратор для асинхронной отправки уведомлений
    
    Преимущества:
    - Не блокирует UI поток
    - Проверяет интернет перед отправкой
    - Безопасно обрабатывает ошибки
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Быстрая проверка интернета
        if not check_internet_available():
            logger.warning(f"{func.__name__}: No internet connection, notification skipped")
            return False
        
        # Запуск в фоновом потоке
        def run():
            try:
                result = func(*args, **kwargs)
                logger.debug(f"{func.__name__}: completed with result={result}")
            except Exception as e:
                logger.error(f"{func.__name__}: failed with error: {e}")
        
        thread = threading.Thread(target=run, daemon=True, name=f"Notif-{func.__name__}")
        thread.start()
        
        # Возвращаем True сразу (не ждем результата)
        return True
    
    return wrapper


@async_notification
def send_overtime_notification(
    email: str,
    break_type: str,
    duration: int,
    limit: int,
    overtime: int
) -> bool:
    """
    Отправляет уведомление о превышении лимита времени
    
    Args:
        email: Email пользователя
        break_type: "Перерыв" или "Обед"
        duration: Фактическая длительность (минуты)
        limit: Лимит времени (минуты)
        overtime: Превышение (минуты)
    
    Returns:
        True если уведомления отправлены успешно
    """
    try:
        # Проверка настроек
        try:
            from config import BREAK_NOTIFY_USER_ON_VIOLATION, BREAK_NOTIFY_ADMIN_ON_VIOLATION
        except ImportError:
            logger.warning("Config settings not found, using defaults")
            BREAK_NOTIFY_USER_ON_VIOLATION = True
            BREAK_NOTIFY_ADMIN_ON_VIOLATION = True
        
        # Импорт Telegram API
        try:
            from telegram_api import TelegramAPI
            telegram = TelegramAPI()
        except ImportError:
            logger.warning("telegram_api module not found, notifications disabled")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize TelegramAPI: {e}")
            return False
        
        user_sent = False
        admin_sent = False
        
        # Сообщение пользователю (в личку)
        if BREAK_NOTIFY_USER_ON_VIOLATION:
            user_message = (
                f"⚠️ ПРЕВЫШЕН ЛИМИТ {break_type.upper()}А\n"
                f"\n"
                f"Ваш {break_type.lower()}: {duration} минут\n"
                f"Лимит: {limit} минут\n"
                f"Превышение: +{overtime} минут\n"
                f"\n"
                f"Пожалуйста, придерживайтесь установленных лимитов."
            )
            
            try:
                user_sent = telegram.send_to_user(email, user_message)
                if user_sent:
                    logger.info(f"Sent overtime notification to user: {email}")
                else:
                    logger.warning(f"Failed to send notification to user: {email}")
            except Exception as e:
                logger.error(f"Error sending to user: {e}")
        
        # Сообщение админу (в группу)
        if BREAK_NOTIFY_ADMIN_ON_VIOLATION:
            current_time = datetime.now().strftime("%H:%M:%S")
            admin_message = (
                f"⚠️ НАРУШЕНИЕ ЛИМИТА\n"
                f"\n"
                f"Сотрудник: {email}\n"
                f"Тип: {break_type}\n"
                f"Длительность: {duration} мин (лимит {limit} мин)\n"
                f"Превышение: +{overtime} мин\n"
                f"Время: {current_time}"
            )
            
            try:
                admin_sent = telegram.send_to_admin_group(admin_message)
                if admin_sent:
                    logger.info("Sent overtime notification to admin group")
                else:
                    logger.warning("Failed to send notification to admin group")
            except Exception as e:
                logger.error(f"Error sending to admin: {e}")
        
        return user_sent or admin_sent
        
    except Exception as e:
        logger.error(f"Error sending overtime notification: {e}", exc_info=True)
        return False


@async_notification
def send_quota_exceeded_notification(
    email: str,
    break_type: str,
    used_count: int,
    limit_count: int
) -> bool:
    """
    Отправляет уведомление о превышении количества перерывов
    
    Args:
        email: Email пользователя
        break_type: "Перерыв" или "Обед"
        used_count: Использовано перерывов
        limit_count: Лимит перерывов
    
    Returns:
        True если успешно
    """
    try:
        from telegram_api import TelegramAPI
        telegram = TelegramAPI()
        
        # Сообщение пользователю
        user_message = (
            f"🚫 ПРЕВЫШЕН ЛИМИТ {break_type.upper()}ОВ\n"
            f"\n"
            f"Использовано: {used_count}\n"
            f"Дневной лимит: {limit_count}\n"
            f"\n"
            f"Вы не можете взять больше {break_type.lower()}ов сегодня."
        )
        
        telegram.send_to_user(email, user_message)
        logger.info(f"Sent quota notification to user: {email}")
        
        # Сообщение админу
        admin_message = (
            f"🚫 ПРЕВЫШЕН ДНЕВНОЙ ЛИМИТ\n"
            f"\n"
            f"Сотрудник: {email}\n"
            f"Тип: {break_type}\n"
            f"Использовано: {used_count}/{limit_count}\n"
            f"Время: {datetime.now().strftime('%H:%M:%S')}"
        )
        
        telegram.send_to_admin_group(admin_message)
        logger.info("Sent quota notification to admin")
        
        return True
        
    except Exception as e:
        logger.error(f"Error sending quota notification: {e}")
        return False


@async_notification
def send_reminder_notification(
    email: str,
    break_type: str,
    window_start: str,
    window_end: str
) -> bool:
    """
    Отправляет напоминание о доступном перерыве
    
    Args:
        email: Email пользователя
        break_type: "Перерыв" или "Обед"
        window_start: Начало окна (HH:MM)
        window_end: Конец окна (HH:MM)
    
    Returns:
        True если успешно
    """
    try:
        from telegram_api import TelegramAPI
        telegram = TelegramAPI()
        
        message = (
            f"🔔 НАПОМИНАНИЕ\n"
            f"\n"
            f"Доступен {break_type.lower()}: {window_start} - {window_end}\n"
            f"Рекомендуем воспользоваться."
        )
        
        telegram.send_to_user(email, message)
        logger.info(f"Sent reminder to: {email}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error sending reminder: {e}")
        return False


@async_notification
def send_return_reminder(
    email: str,
    break_type: str,
    duration: int,
    limit: int
) -> bool:
    """
    Отправляет напоминание о необходимости вернуться
    
    Args:
        email: Email пользователя
        break_type: "Перерыв" или "Обед"
        duration: Текущая длительность
        limit: Лимит
    
    Returns:
        True если успешно
    """
    try:
        from telegram_api import TelegramAPI
        telegram = TelegramAPI()
        
        remaining = limit - duration
        if remaining <= 0:
            message = (
                f"⏰ ВРЕМЯ ИСТЕКЛО\n"
                f"\n"
                f"Ваш {break_type.lower()} ({limit} мин) завершился.\n"
                f"Пожалуйста, вернитесь к работе."
            )
        else:
            message = (
                f"⏰ НАПОМИНАНИЕ\n"
                f"\n"
                f"Ваш {break_type.lower()} скоро закончится.\n"
                f"Осталось: {remaining} минут"
            )
        
        telegram.send_to_user(email, message)
        logger.info(f"Sent return reminder to: {email}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error sending return reminder: {e}")
        return False


# Экспорт функций
__all__ = [
    'send_overtime_notification',
    'send_quota_exceeded_notification',
    'send_reminder_notification',
    'send_return_reminder',
    'check_internet_available'  # Добавлен для тестирования
]


if __name__ == "__main__":
    # Тест модуля
    print("break_notifications module v2.1 (FIXED)")
    print("Available functions:")
    for func_name in __all__:
        print(f"  - {func_name}")
    
    # Тест проверки интернета
    print(f"\nInternet available: {check_internet_available()}")
