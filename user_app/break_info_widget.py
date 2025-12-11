# user_app/break_info_widget.py
"""
Информационный виджет о доступных перерывах и обедах

Показывает:
- Название назначенного графика
- Использованные и оставшиеся перерывы
- Использованные и оставшиеся обеды
- Текущий активный перерыв (если есть)
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, QGroupBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
import logging
import sys
from pathlib import Path

# Добавляем путь к shared модулям
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from shared.time_utils import format_datetime_moscow, format_time_moscow

logger = logging.getLogger(__name__)


class BreakInfoWidget(QWidget):
    """Виджет отображения информации о перерывах"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.email = None
        self.break_manager = None
        self._setup_ui()
        
        # Таймер автообновления (каждую минуту)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(60000)  # 60 секунд
    
    def _setup_ui(self):
        """Создаёт интерфейс"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Группа с информацией
        group = QGroupBox("📋 Доступные перерывы и обеды")
        group_layout = QVBoxLayout()
        group_layout.setSpacing(8)
        
        # Заголовок (название графика)
        self.title_label = QLabel("Загрузка...")
        self.title_label.setAlignment(Qt.AlignCenter)
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(10)
        self.title_label.setFont(title_font)
        group_layout.addWidget(self.title_label)
        
        # Разделитель
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        group_layout.addWidget(line)
        
        # Информация о перерывах
        self.breaks_label = QLabel("☕ Перерывы: загрузка...")
        self.breaks_label.setWordWrap(True)
        group_layout.addWidget(self.breaks_label)
        
        # Информация об обедах
        self.lunch_label = QLabel("🍽️ Обеды: загрузка...")
        self.lunch_label.setWordWrap(True)
        group_layout.addWidget(self.lunch_label)
        
        # Разделитель
        line2 = QFrame()
        line2.setFrameShape(QFrame.HLine)
        line2.setFrameShadow(QFrame.Sunken)
        group_layout.addWidget(line2)
        
        # Активный перерыв
        self.active_label = QLabel("")
        self.active_label.setWordWrap(True)
        active_font = QFont()
        active_font.setBold(True)
        self.active_label.setFont(active_font)
        group_layout.addWidget(self.active_label)
        
        group.setLayout(group_layout)
        layout.addWidget(group)
        
        # Растягиваем
        layout.addStretch()
        
        # Установить минимальную ширину
        self.setMinimumWidth(250)
    
    def set_manager(self, break_manager, email: str):
        """
        Устанавливает менеджер перерывов и email
        
        Args:
            break_manager: Экземпляр BreakManager
            email: Email пользователя
        """
        self.break_manager = break_manager
        self.email = email
        self.refresh()
    
    def refresh(self):
        """Обновляет информацию"""
        if not self.break_manager or not self.email:
            self.title_label.setText("Не инициализирован")
            self.breaks_label.setText("")
            self.lunch_label.setText("")
            self.active_label.setText("")
            return
        
        try:
            # Получить статус перерывов от BreakManager
            status = self.break_manager.get_break_status(self.email)
            
            if not status:
                self._show_no_schedule()
                return
            
            schedule = status.get('schedule')
            if not schedule:
                self._show_no_schedule()
                return
            
            # Заголовок с названием графика
            schedule_name = schedule.get('name', 'Неизвестно')
            self.title_label.setText(f"График: {schedule_name}")
            
            # Лимиты и использование
            limits = status.get('limits', {})
            used_today = status.get('used_today', {})
            
            # ПЕРЕРЫВЫ
            break_limit = limits.get('Перерыв', {})
            break_count = break_limit.get('count', 0)
            break_time = break_limit.get('time', 0)
            breaks_used = used_today.get('Перерыв', 0)
            breaks_remaining = max(0, break_count - breaks_used)
            
            self.breaks_label.setText(
                f"☕ ПЕРЕРЫВЫ:\n"
                f"   Использовано: {breaks_used} из {break_count}\n"
                f"   Осталось: {breaks_remaining}\n"
                f"   Длительность: {break_time} мин"
            )
            
            # ОБЕДЫ
            lunch_limit = limits.get('Обед', {})
            lunch_count = lunch_limit.get('count', 0)
            lunch_time = lunch_limit.get('time', 0)
            lunch_used = used_today.get('Обед', 0)
            lunch_remaining = max(0, lunch_count - lunch_used)
            
            self.lunch_label.setText(
                f"🍽️ ОБЕДЫ:\n"
                f"   Использовано: {lunch_used} из {lunch_count}\n"
                f"   Осталось: {lunch_remaining}\n"
                f"   Длительность: {lunch_time} мин"
            )
            
            # АКТИВНЫЙ ПЕРЕРЫВ
            active = status.get('active_break')
            if active:
                break_type = active.get('break_type', 'Перерыв')
                start_time_raw = active.get('start_time', '')
                # Форматируем время начала в московское (UTC+3)
                # Если start_time уже в формате "HH:MM", оставляем как есть
                # Если это ISO строка или datetime, конвертируем в московское время
                if start_time_raw and len(start_time_raw) > 5 and ('T' in start_time_raw or '-' in start_time_raw[:10]):
                    # Это полный datetime, конвертируем в московское время
                    start_time = format_time_moscow(start_time_raw, '%H:%M')
                else:
                    # Это уже время в формате "HH:MM" или пусто
                    start_time = start_time_raw
                duration = active.get('duration', 0)
                limit = active.get('limit', 0)
                
                # Определяем цвет в зависимости от превышения
                if duration > limit:
                    # Превышен лимит - красный
                    color = "#e74c3c"
                    warning = " ⚠️ ПРЕВЫШЕН ЛИМИТ"
                elif duration >= limit - 2:
                    # Почти закончился - оранжевый
                    color = "#f39c12"
                    warning = " ⏰ Скоро закончится"
                else:
                    # Всё в порядке - зелёный
                    color = "#27ae60"
                    warning = ""
                
                self.active_label.setText(
                    f"⏱️ СЕЙЧАС В {break_type.upper()}Е{warning}\n"
                    f"   Начало: {start_time}\n"
                    f"   Прошло: {duration}/{limit} мин"
                )
                self.active_label.setStyleSheet(f"color: {color}; font-weight: bold;")
            else:
                self.active_label.setText("")
                self.active_label.setStyleSheet("")
            
        except Exception as e:
            logger.error(f"Error refreshing break info: {e}", exc_info=True)
            self.title_label.setText("Ошибка загрузки")
            self.breaks_label.setText(f"❌ Ошибка: {str(e)[:50]}")
            self.lunch_label.setText("")
            self.active_label.setText("")
    
    def _show_no_schedule(self):
        """Показывает сообщение об отсутствии графика"""
        self.title_label.setText("График не назначен")
        self.breaks_label.setText(
            "❌ У вас нет назначенного графика перерывов\n"
            "   Обратитесь к администратору"
        )
        self.lunch_label.setText("")
        self.active_label.setText("")


# Тестирование виджета
if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    
    # Создаём виджет
    widget = BreakInfoWidget()
    widget.setWindowTitle("Break Info Widget Test")
    widget.resize(300, 400)
    
    # Симуляция данных для теста
    class MockBreakManager:
        def get_break_status(self, email):
            return {
                'schedule': {
                    'name': 'График 5/2 (9-18)'
                },
                'limits': {
                    'Перерыв': {'count': 3, 'time': 15},
                    'Обед': {'count': 1, 'time': 60}
                },
                'used_today': {
                    'Перерыв': 1,
                    'Обед': 0
                },
                'active_break': {
                    'break_type': 'Перерыв',
                    'start_time': '10:30',
                    'duration': 12,
                    'limit': 15
                }
            }
    
    # Устанавливаем mock manager
    widget.set_manager(MockBreakManager(), "test@example.com")
    
    widget.show()
    sys.exit(app.exec_())