import logging
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import Qt, QTimer

logger = logging.getLogger(__name__)

class Notifier:
    _active_messages = []  # Хранить ссылки на активные окна
    
    @staticmethod
    def show(title: str, message: str, parent=None):
        """Показывает системное уведомление или Qt-сообщение"""
        try:
            # Сначала пробуем показать системное уведомление
            try:
                from plyer import notification
                notification.notify(
                    title=title,
                    message=message,
                    app_name='WorkLog',
                    timeout=5
                )
                return
            except ImportError:
                logger.debug("Plyer не установлен, используем Qt-уведомления")
            except Exception as e:
                logger.warning(f"Ошибка системного уведомления: {e}")

            # Fallback на Qt-сообщения (неблокирующие с автозакрытием)
            msg = QMessageBox(parent)
            msg.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Tool)
            msg.setWindowTitle(title)
            msg.setText(message)
            msg.setIcon(QMessageBox.Information)
            msg.setStandardButtons(QMessageBox.Ok)
            
            # Сохраняем ссылку чтобы окно не удалилось
            Notifier._active_messages.append(msg)
            
            # Автозакрытие через 5 секунд
            def auto_close():
                msg.close()
                if msg in Notifier._active_messages:
                    Notifier._active_messages.remove(msg)
            
            QTimer.singleShot(5000, auto_close)
            msg.show()  # Неблокирующий показ

        except Exception as e:
            logger.error(f"Ошибка показа уведомления: {e}")
            # Последний резервный вариант - вывод в консоль
            print(f"Уведомление: {title} - {message}")

    @staticmethod
    def show_warning(title: str, message: str, parent=None):
        """Показывает предупреждающее уведомление (неблокирующее)"""
        try:
            msg = QMessageBox(parent)
            msg.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Tool)
            msg.setWindowTitle(title)
            msg.setText(message)
            msg.setIcon(QMessageBox.Warning)
            
            # Сохраняем ссылку
            Notifier._active_messages.append(msg)
            
            # Автозакрытие через 5 секунд
            def auto_close():
                msg.close()
                if msg in Notifier._active_messages:
                    Notifier._active_messages.remove(msg)
            
            QTimer.singleShot(5000, auto_close)
            msg.show()
        except Exception as e:
            logger.error(f"Ошибка показа предупреждения: {e}")
            print(f"Предупреждение: {title} - {message}")

    @staticmethod
    def show_error(title: str, message: str, parent=None):
        """Показывает уведомление об ошибке (неблокирующее)"""
        try:
            msg = QMessageBox(parent)
            msg.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Tool)
            msg.setWindowTitle(title)
            msg.setText(message)
            msg.setIcon(QMessageBox.Critical)
            
            # Сохраняем ссылку
            Notifier._active_messages.append(msg)
            
            # Автозакрытие через 8 секунд (ошибки показываем дольше)
            def auto_close():
                msg.close()
                if msg in Notifier._active_messages:
                    Notifier._active_messages.remove(msg)
            
            QTimer.singleShot(8000, auto_close)
            msg.show()
        except Exception as e:
            logger.error(f"Ошибка показа ошибки: {e}")
            print(f"Ошибка: {title} - {message}")