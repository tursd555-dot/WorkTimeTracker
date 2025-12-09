
import logging
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import Qt, QTimer, QObject, pyqtSignal

logger = logging.getLogger(__name__)


class NotificationManager(QObject):
    """
    Менеджер уведомлений с поддержкой вызова из любых потоков
    Использует Qt сигналы для безопасного вызова из non-GUI потоков
    """
    # Сигналы для вызова из любого потока
    show_info_signal = pyqtSignal(str, str)
    show_warning_signal = pyqtSignal(str, str)
    show_error_signal = pyqtSignal(str, str)
    
    def __init__(self):
        super().__init__()
        self._active_messages = []
        
        # Подключаем сигналы к слотам
        self.show_info_signal.connect(self._show_info_slot)
        self.show_warning_signal.connect(self._show_warning_slot)
        self.show_error_signal.connect(self._show_error_slot)
    
    def _show_info_slot(self, title: str, message: str):
        """Слот для показа info уведомления (вызывается в главном потоке)"""
        try:
            # Сначала пробуем системное уведомление
            try:
                from plyer import notification
                notification.notify(
                    title=title,
                    message=message,
                    app_name='WorkLog',
                    timeout=5
                )
                return
            except (ImportError, Exception) as e:
                if isinstance(e, ImportError):
                    logger.debug("Plyer не установлен, используем Qt-уведомления")
                else:
                    logger.warning(f"Ошибка системного уведомления: {e}")
            
            # Fallback на Qt (неблокирующее)
            self._show_qt_message(title, message, QMessageBox.Information, timeout=5000)
        except Exception as e:
            logger.error(f"Ошибка показа уведомления: {e}")
            print(f"Уведомление: {title} - {message}")
    
    def _show_warning_slot(self, title: str, message: str):
        """Слот для показа warning (вызывается в главном потоке)"""
        try:
            self._show_qt_message(title, message, QMessageBox.Warning, timeout=5000)
        except Exception as e:
            logger.error(f"Ошибка показа предупреждения: {e}")
            print(f"Предупреждение: {title} - {message}")
    
    def _show_error_slot(self, title: str, message: str):
        """Слот для показа error (вызывается в главном потоке)"""
        try:
            self._show_qt_message(title, message, QMessageBox.Critical, timeout=8000)
        except Exception as e:
            logger.error(f"Ошибка показа ошибки: {e}")
            print(f"Ошибка: {title} - {message}")
    
    def _show_qt_message(self, title: str, message: str, icon: QMessageBox.Icon, timeout: int):
        """Показывает Qt уведомление с автозакрытием"""
        msg = QMessageBox()
        msg.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Tool)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.setIcon(icon)
        msg.setStandardButtons(QMessageBox.Ok)
        
        # Сохраняем ссылку
        self._active_messages.append(msg)
        
        # Автозакрытие через timeout миллисекунд
        def auto_close():
            try:
                msg.close()
                if msg in self._active_messages:
                    self._active_messages.remove(msg)
            except Exception as e:
                logger.debug(f"Error closing message: {e}")
        
        QTimer.singleShot(timeout, auto_close)
        msg.show()


# Глобальный экземпляр (создается при первом использовании)
_manager = None


def _get_manager():
    """Получить глобальный экземпляр менеджера"""
    global _manager
    if _manager is None:
        _manager = NotificationManager()
    return _manager


class Notifier:
    """
    Обертка для удобного использования уведомлений
    Безопасна для вызова из любых потоков благодаря Qt сигналам
    """
    
    @staticmethod
    def show(title: str, message: str, parent=None):
        """
        Показывает информационное уведомление
        Безопасно для вызова из любого потока
        """
        manager = _get_manager()
        manager.show_info_signal.emit(title, message)
    
    @staticmethod
    def show_warning(title: str, message: str, parent=None):
        """
        Показывает предупреждающее уведомление
        Безопасно для вызова из любого потока
        """
        manager = _get_manager()
        manager.show_warning_signal.emit(title, message)
    
    @staticmethod
    def show_error(title: str, message: str, parent=None):
        """
        Показывает уведомление об ошибке
        Безопасно для вызова из любого потока
        """
        manager = _get_manager()
        manager.show_error_signal.emit(title, message)


if __name__ == "__main__":
    print("Notification system with Qt signals")
    print("Thread-safe notifications for PyQt5 applications")
