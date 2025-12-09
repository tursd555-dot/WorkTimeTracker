
# sync/network.py
import urllib.request
import socket
import logging

logger = logging.getLogger(__name__)

def is_internet_available(timeout: int = 3) -> bool:
    """
    Проверить доступность интернета с проверкой DNS.
    ВАЖНО: Проверяем именно sheets.googleapis.com, так как это критично для работы.
    """
    try:
        logger.debug("Проверка доступности интернета (DNS + HTTP)...")
        
        # Сначала проверяем DNS резолв для sheets.googleapis.com
        # Используем отдельный сокет с timeout (не влияет на другие потоки)
        try:
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.settimeout(timeout)
            # Проверяем что можем получить адрес и подключиться
            addr_info = socket.getaddrinfo('sheets.googleapis.com', 443, socket.AF_INET, socket.SOCK_STREAM)
            if addr_info:
                # Пытаемся подключиться к первому адресу
                addr = addr_info[0][4]
                test_socket.connect(addr)
                test_socket.close()
                logger.debug("✓ DNS резолв + connect sheets.googleapis.com: OK")
            else:
                logger.warning("❌ DNS резолв sheets.googleapis.com: NO ADDRESSES")
                return False
        except (socket.gaierror, OSError, socket.timeout) as dns_error:
            logger.warning(f"❌ DNS/Connect sheets.googleapis.com: FAILED - {dns_error}")
            try:
                test_socket.close()
            except:
                pass
            return False
        
        # Дополнительно проверяем HTTP доступность google.com
        try:
            response = urllib.request.urlopen("https://www.google.com", timeout=timeout)
            if response.status == 200:
                logger.debug("✓ HTTP google.com: OK - Интернет доступен")
                return True
            else:
                logger.warning(f"HTTP google.com: код {response.status}")
                return False
        except (urllib.error.URLError, socket.timeout) as http_error:
            logger.warning(f"❌ HTTP google.com: FAILED - {http_error}")
            return False
            
    except Exception as e:
        logger.error(f"Неожиданная ошибка при проверке интернета: {e}")
        return False


def is_internet_available_fast(timeout: float = 0.5) -> bool:
    """
    БЫСТРАЯ проверка доступности интернета (только DNS, без подключения).
    Используется в GUI для немедленной проверки без блокировки UI.
    
    Args:
        timeout: Таймаут в секундах (по умолчанию 0.5 сек)
    
    Returns:
        True если DNS работает
    """
    try:
        # Только DNS резолв, БЕЗ подключения - очень быстро!
        socket.setdefaulttimeout(timeout)
        addr_info = socket.getaddrinfo('sheets.googleapis.com', 443, socket.AF_INET, socket.SOCK_STREAM)
        socket.setdefaulttimeout(None)
        return bool(addr_info)
    except (socket.gaierror, OSError):
        socket.setdefaulttimeout(None)
        return False
    except Exception:
        socket.setdefaulttimeout(None)
        return False