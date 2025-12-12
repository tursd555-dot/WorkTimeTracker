# shared/break_notifications_v2.py
"""
Улучшенная система Telegram уведомлений для системы перерывов v2.2

Требования:
1. В личку: превышение на 1 минуту, раз в 5 минут, до изменения статуса
2. В группу: одно сообщение за нарушение (превышение, вне окна, превышение количества)
"""
import logging
import threading
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict
from functools import wraps
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shared.time_utils import format_datetime_moscow

logger = logging.getLogger(__name__)

# Дебаунсинг для личных уведомлений: {email: {break_type: last_sent_time}}
_user_notification_times: Dict[str, Dict[str, datetime]] = defaultdict(dict)
_notification_lock = threading.Lock()

# Отслеживание отправленных групповых уведомлений: {email: {violation_key: True}}
_group_notifications_sent: Dict[str, Dict[str, bool]] = defaultdict(dict)


def check_internet_available() -> bool:
    """Быстрая проверка доступности интернета"""
    try:
        import socket
        socket.setdefaulttimeout(0.5)
        addr_info = socket.getaddrinfo('sheets.googleapis.com', 443, socket.AF_INET, socket.SOCK_STREAM)
        socket.setdefaulttimeout(None)
        return bool(addr_info)
    except Exception:
        socket.setdefaulttimeout(None)
        return False


def async_notification(func):
    """Декоратор для асинхронной отправки уведомлений"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not check_internet_available():
            logger.warning(f"{func.__name__}: No internet connection, notification skipped")
            return False
        
        def run():
            try:
                result = func(*args, **kwargs)
                logger.debug(f"{func.__name__}: completed with result={result}")
            except Exception as e:
                logger.error(f"{func.__name__}: failed with error: {e}")
        
        thread = threading.Thread(target=run, daemon=True, name=f"Notif-{func.__name__}")
        thread.start()
        return True
    
    return wrapper


def _should_send_user_notification(email: str, break_type: str) -> bool:
    """
    Проверяет, нужно ли отправлять личное уведомление пользователю
    (раз в 5 минут, до изменения статуса)
    """
    with _notification_lock:
        key = f"{email}_{break_type}"
        last_sent = _user_notification_times[email].get(break_type)
        
        if last_sent is None:
            # Первое уведомление
            _user_notification_times[email][break_type] = datetime.now()
            return True
        
        # Проверяем, прошло ли 5 минут
        time_since_last = datetime.now() - last_sent
        if time_since_last >= timedelta(minutes=5):
            _user_notification_times[email][break_type] = datetime.now()
            return True
        
        return False


def _mark_user_status_changed(email: str, break_type: str):
    """Отмечает, что пользователь изменил статус (сброс дебаунсинга)"""
    with _notification_lock:
        if break_type in _user_notification_times[email]:
            del _user_notification_times[email][break_type]
            logger.debug(f"Reset notification debounce for {email}, {break_type}")


def _should_send_group_notification(email: str, violation_key: str) -> bool:
    """
    Проверяет, было ли уже отправлено групповое уведомление для этого нарушения
    (одно сообщение за нарушение)
    """
    with _notification_lock:
        if violation_key not in _group_notifications_sent[email]:
            _group_notifications_sent[email][violation_key] = True
            return True
        return False


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
    
    Требования:
    - В личку: раз в 5 минут, до изменения статуса
    - В группу: одно сообщение за нарушение
    """
    try:
        from telegram_api import TelegramAPI
        telegram = TelegramAPI()
        
        # Проверка настроек
        try:
            from config import BREAK_NOTIFY_USER_ON_VIOLATION, BREAK_NOTIFY_ADMIN_ON_VIOLATION
        except ImportError:
            BREAK_NOTIFY_USER_ON_VIOLATION = True
            BREAK_NOTIFY_ADMIN_ON_VIOLATION = True
        
        user_sent = False
        admin_sent = False
        
        # Сообщение пользователю (в личку) - с дебаунсингом
        if BREAK_NOTIFY_USER_ON_VIOLATION and overtime >= 1:  # Превышение на 1+ минуту
            if _should_send_user_notification(email, break_type):
                user_message = (
                    f"⚠️ ПРЕВЫШЕН ЛИМИТ {break_type.upper()}А\n"
                    f"\n"
                    f"Ваш {break_type.lower()}: {duration} минут\n"
                    f"Лимит: {limit} минут\n"
                    f"Превышение: +{overtime} минут\n"
                    f"\n"
                    f"Пожалуйста, вернитесь к работе."
                )
                
                try:
                    user_sent = telegram.send_to_user(email, user_message)
                    if user_sent:
                        logger.info(f"Sent overtime notification to user: {email} ({break_type}, +{overtime} мин)")
                except Exception as e:
                    logger.error(f"Error sending to user: {e}")
            else:
                logger.debug(f"Skipping user notification for {email} ({break_type}) - debounce active")
        
        # Сообщение админу (в группу) - одно за нарушение
        if BREAK_NOTIFY_ADMIN_ON_VIOLATION and overtime >= 1:
            violation_key = f"overtime_{break_type}_{limit}"
            if _should_send_group_notification(email, violation_key):
                from shared.time_utils import format_time_moscow
                current_time = format_time_moscow(datetime.now(), '%H:%M:%S')
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
                        logger.info(f"Sent overtime notification to admin group ({email}, {break_type})")
                except Exception as e:
                    logger.error(f"Error sending to admin: {e}")
            else:
                logger.debug(f"Group notification already sent for {email} ({violation_key})")
        
        return user_sent or admin_sent
        
    except Exception as e:
        logger.error(f"Error sending overtime notification: {e}", exc_info=True)
        return False


@async_notification
def send_out_of_window_notification(
    email: str,
    break_type: str,
    current_time: str
) -> bool:
    """
    Отправляет уведомление о перерыве вне временного окна
    
    Требования:
    - В группу: одно сообщение за нарушение
    """
    try:
        from telegram_api import TelegramAPI
        telegram = TelegramAPI()
        
        try:
            from config import BREAK_NOTIFY_ADMIN_ON_VIOLATION
        except ImportError:
            BREAK_NOTIFY_ADMIN_ON_VIOLATION = True
        
        if not BREAK_NOTIFY_ADMIN_ON_VIOLATION:
            return False
        
        # Проверяем, было ли уже отправлено уведомление для этого нарушения
        violation_key = f"out_of_window_{break_type}_{current_time[:5]}"  # Используем час:минуту
        if not _should_send_group_notification(email, violation_key):
            logger.debug(f"Group notification already sent for {email} ({violation_key})")
            return False
        
        from shared.time_utils import format_time_moscow
        moscow_time = format_time_moscow(datetime.now(), '%H:%M:%S')
        admin_message = (
            f"⚠️ ПЕРЕРЫВ ВНЕ ВРЕМЕННОГО ОКНА\n"
            f"\n"
            f"Сотрудник: {email}\n"
            f"Тип: {break_type}\n"
            f"Время начала: {current_time}\n"
            f"Время уведомления: {moscow_time}"
        )
        
        try:
            admin_sent = telegram.send_to_admin_group(admin_message)
            if admin_sent:
                logger.info(f"Sent out-of-window notification to admin group ({email}, {break_type})")
            return admin_sent
        except Exception as e:
            logger.error(f"Error sending out-of-window notification: {e}")
            return False
        
    except Exception as e:
        logger.error(f"Error sending out-of-window notification: {e}", exc_info=True)
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
    
    Требования:
    - В группу: одно сообщение за нарушение
    """
    try:
        from telegram_api import TelegramAPI
        telegram = TelegramAPI()
        
        try:
            from config import BREAK_NOTIFY_ADMIN_ON_VIOLATION
        except ImportError:
            BREAK_NOTIFY_ADMIN_ON_VIOLATION = True
        
        if not BREAK_NOTIFY_ADMIN_ON_VIOLATION:
            return False
        
        # Проверяем, было ли уже отправлено уведомление
        violation_key = f"quota_{break_type}_{limit_count}"
        if not _should_send_group_notification(email, violation_key):
            logger.debug(f"Group notification already sent for {email} ({violation_key})")
            return False
        
        from shared.time_utils import format_time_moscow
        moscow_time = format_time_moscow(datetime.now(), '%H:%M:%S')
        admin_message = (
            f"🚫 ПРЕВЫШЕН ДНЕВНОЙ ЛИМИТ\n"
            f"\n"
            f"Сотрудник: {email}\n"
            f"Тип: {break_type}\n"
            f"Использовано: {used_count}/{limit_count}\n"
            f"Время: {moscow_time}"
        )
        
        try:
            admin_sent = telegram.send_to_admin_group(admin_message)
            if admin_sent:
                logger.info(f"Sent quota notification to admin group ({email}, {break_type})")
            return admin_sent
        except Exception as e:
            logger.error(f"Error sending quota notification: {e}")
            return False
        
    except Exception as e:
        logger.error(f"Error sending quota notification: {e}", exc_info=True)
        return False


def reset_user_notifications(email: str, break_type: Optional[str] = None):
    """
    Сбрасывает дебаунсинг уведомлений для пользователя
    Вызывается при изменении статуса на продуктивный или завершении сессии
    """
    with _notification_lock:
        if break_type:
            if break_type in _user_notification_times[email]:
                del _user_notification_times[email][break_type]
        else:
            # Сбрасываем все уведомления для пользователя
            if email in _user_notification_times:
                del _user_notification_times[email]
        
        logger.debug(f"Reset notifications for {email}, break_type={break_type}")
