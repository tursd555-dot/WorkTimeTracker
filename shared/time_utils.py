"""
Утилиты для работы с московским временем (UTC+3)

Все функции для отображения времени в интерфейсе должны использовать
московское время. Для технических нужд (сохранение в БД) можно использовать UTC.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, Union
import logging

logger = logging.getLogger(__name__)

# Московский часовой пояс (UTC+3)
MOSCOW_TZ = timezone(timedelta(hours=3))


def now_moscow() -> datetime:
    """
    Возвращает текущее время в московском часовом поясе
    
    Returns:
        datetime: Текущее время в UTC+3
    """
    return datetime.now(MOSCOW_TZ)


def to_moscow(dt: Union[datetime, str, None]) -> Optional[datetime]:
    """
    Конвертирует datetime в московское время (UTC+3)
    
    Args:
        dt: datetime объект или ISO строка, или None
        
    Returns:
        datetime в московском часовом поясе или None
    """
    if dt is None:
        return None
    
    # Если строка, парсим её
    if isinstance(dt, str):
        try:
            # Пробуем ISO формат
            if 'T' in dt:
                dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
            else:
                # Старый формат без T
                dt = datetime.strptime(dt[:19], '%Y-%m-%d %H:%M:%S')
        except Exception as e:
            logger.warning(f"Failed to parse datetime string '{dt}': {e}")
            return None
    
    # Если datetime без timezone, считаем что это UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    # Конвертируем в московское время
    return dt.astimezone(MOSCOW_TZ)


def format_datetime_moscow(dt: Union[datetime, str, None], format_str: str = '%Y-%m-%d %H:%M:%S') -> str:
    """
    Форматирует datetime в московское время и возвращает строку
    
    Args:
        dt: datetime объект или ISO строка, или None
        format_str: формат строки (по умолчанию '%Y-%m-%d %H:%M:%S')
        
    Returns:
        Отформатированная строка времени в московском часовом поясе
        или пустая строка, если dt is None
    """
    moscow_dt = to_moscow(dt)
    if moscow_dt is None:
        return ""
    
    return moscow_dt.strftime(format_str)


def format_time_moscow(dt: Union[datetime, str, None], format_str: str = '%H:%M:%S') -> str:
    """
    Форматирует только время (без даты) в московском часовом поясе
    
    Args:
        dt: datetime объект или ISO строка, или None
        format_str: формат строки (по умолчанию '%H:%M:%S')
        
    Returns:
        Отформатированная строка времени в московском часовом поясе
        или пустая строка, если dt is None
    """
    return format_datetime_moscow(dt, format_str)


def format_date_moscow(dt: Union[datetime, str, None], format_str: str = '%Y-%m-%d') -> str:
    """
    Форматирует только дату (без времени) в московском часовом поясе
    
    Args:
        dt: datetime объект или ISO строка, или None
        format_str: формат строки (по умолчанию '%Y-%m-%d')
        
    Returns:
        Отформатированная строка даты в московском часовом поясе
        или пустая строка, если dt is None
    """
    return format_datetime_moscow(dt, format_str)
