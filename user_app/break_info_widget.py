# user_app/break_info_widget.py
"""
Информационный виджет о доступных перерывах и обедах v2.1

Показывает:
- Название назначенного графика (или "Дефолтный график")
- Использованные и оставшиеся перерывы
- Использованные и оставшиеся обеды
- Текущий активный перерыв (если есть)

Изменения v2.1:
- Поддержка дефолтных лимитов если нет назначенного графика
- Более частое обновление при активном перерыве (каждые 10 сек)
- Улучшенное отображение состояния
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, QGroupBox, QProgressBar
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
import logging

logger = logging.getLogger(__name__)


class BreakInfoWidget(QWidget):
    """Виджет отображения информации о перерывах v2.1"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.email = None
        self.break_manager = None
        self._has_active_break = False
        self._setup_ui()

        # Таймер автообновления (каждую минуту в обычном режиме)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_timer)
        self.timer.start(60000)  # 60 секунд

        # Быстрый таймер для активного перерыва (каждые 10 сек)
        self.fast_timer = QTimer(self)
        self.fast_timer.timeout.connect(self.refresh)
        self.fast_timer.setInterval(10000)  # 10 секунд

    def _setup_ui(self):
        """Создаёт интерфейс"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Группа с информацией
        group = QGroupBox("Доступные перерывы и обеды")
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
        self.breaks_label = QLabel("Перерывы: загрузка...")
        self.breaks_label.setWordWrap(True)
        group_layout.addWidget(self.breaks_label)

        # Прогресс-бар перерывов
        self.breaks_progress = QProgressBar()
        self.breaks_progress.setTextVisible(True)
        self.breaks_progress.setMaximumHeight(20)
        group_layout.addWidget(self.breaks_progress)

        # Информация об обедах
        self.lunch_label = QLabel("Обеды: загрузка...")
        self.lunch_label.setWordWrap(True)
        group_layout.addWidget(self.lunch_label)

        # Прогресс-бар обедов
        self.lunch_progress = QProgressBar()
        self.lunch_progress.setTextVisible(True)
        self.lunch_progress.setMaximumHeight(20)
        group_layout.addWidget(self.lunch_progress)

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

        # Прогресс активного перерыва
        self.active_progress = QProgressBar()
        self.active_progress.setTextVisible(True)
        self.active_progress.setMaximumHeight(25)
        self.active_progress.hide()
        group_layout.addWidget(self.active_progress)

        group.setLayout(group_layout)
        layout.addWidget(group)

        # Растягиваем
        layout.addStretch()

        # Установить минимальную ширину
        self.setMinimumWidth(280)

    def set_manager(self, break_manager, email: str):
        """
        Устанавливает менеджер перерывов и email

        Args:
            break_manager: Экземпляр BreakManager или BreakManagerSupabase
            email: Email пользователя
        """
        self.break_manager = break_manager
        self.email = email
        self.refresh()

    def _on_timer(self):
        """Обработчик основного таймера"""
        self.refresh()

    def refresh(self):
        """Обновляет информацию"""
        if not self.break_manager or not self.email:
            self.title_label.setText("Не инициализирован")
            self.breaks_label.setText("")
            self.lunch_label.setText("")
            self.active_label.setText("")
            self.breaks_progress.hide()
            self.lunch_progress.hide()
            self.active_progress.hide()
            return

        try:
            # Получить статус перерывов от BreakManager
            status = self.break_manager.get_break_status(self.email)

            if not status:
                self._show_default_status()
                return

            schedule = status.get('schedule')
            limits = status.get('limits', {})
            used_today = status.get('used_today', {})

            # Если нет лимитов - показываем дефолтные
            if not limits:
                limits = {
                    'Перерыв': {'count': 3, 'time': 15},
                    'Обед': {'count': 1, 'time': 60}
                }

            # Заголовок с названием графика
            if schedule:
                schedule_name = schedule.get('name', 'Дефолтный график')
            else:
                schedule_name = 'Дефолтный график'
            self.title_label.setText(f"График: {schedule_name}")

            # ПЕРЕРЫВЫ
            break_limit = limits.get('Перерыв', {})
            break_count = break_limit.get('count', 3)
            break_time = break_limit.get('time', 15)
            breaks_used = used_today.get('Перерыв', 0)
            breaks_remaining = max(0, break_count - breaks_used)

            self.breaks_label.setText(
                f"ПЕРЕРЫВЫ: {breaks_used}/{break_count} "
                f"(осталось: {breaks_remaining}, по {break_time} мин)"
            )

            # Прогресс-бар перерывов
            self.breaks_progress.setMaximum(break_count)
            self.breaks_progress.setValue(breaks_used)
            self.breaks_progress.setFormat(f"{breaks_used}/{break_count}")
            self._style_progress_bar(self.breaks_progress, breaks_used, break_count)
            self.breaks_progress.show()

            # ОБЕДЫ
            lunch_limit = limits.get('Обед', {})
            lunch_count = lunch_limit.get('count', 1)
            lunch_time = lunch_limit.get('time', 60)
            lunch_used = used_today.get('Обед', 0)
            lunch_remaining = max(0, lunch_count - lunch_used)

            self.lunch_label.setText(
                f"ОБЕДЫ: {lunch_used}/{lunch_count} "
                f"(осталось: {lunch_remaining}, по {lunch_time} мин)"
            )

            # Прогресс-бар обедов
            self.lunch_progress.setMaximum(lunch_count)
            self.lunch_progress.setValue(lunch_used)
            self.lunch_progress.setFormat(f"{lunch_used}/{lunch_count}")
            self._style_progress_bar(self.lunch_progress, lunch_used, lunch_count)
            self.lunch_progress.show()

            # АКТИВНЫЙ ПЕРЕРЫВ
            active = status.get('active_break')
            if active:
                self._has_active_break = True
                self.fast_timer.start()  # Включаем быстрое обновление

                break_type = active.get('break_type', 'Перерыв')
                start_time = active.get('start_time', '')
                duration = active.get('duration', 0)
                limit = active.get('limit', 15)

                # Определяем цвет и состояние
                if duration > limit:
                    color = "#e74c3c"  # Красный
                    status_text = "ПРЕВЫШЕН ЛИМИТ!"
                    progress_style = "QProgressBar::chunk { background-color: #e74c3c; }"
                elif duration >= limit - 2:
                    color = "#f39c12"  # Оранжевый
                    status_text = "Скоро закончится"
                    progress_style = "QProgressBar::chunk { background-color: #f39c12; }"
                else:
                    color = "#27ae60"  # Зелёный
                    status_text = "В норме"
                    progress_style = "QProgressBar::chunk { background-color: #27ae60; }"

                self.active_label.setText(
                    f"СЕЙЧАС: {break_type.upper()}\n"
                    f"Начало: {start_time} | {status_text}"
                )
                self.active_label.setStyleSheet(f"color: {color}; font-weight: bold;")

                # Прогресс-бар активного перерыва
                self.active_progress.setMaximum(max(limit, duration))
                self.active_progress.setValue(duration)
                self.active_progress.setFormat(f"{duration}/{limit} мин")
                self.active_progress.setStyleSheet(progress_style)
                self.active_progress.show()
            else:
                self._has_active_break = False
                self.fast_timer.stop()  # Выключаем быстрое обновление

                self.active_label.setText("")
                self.active_label.setStyleSheet("")
                self.active_progress.hide()

        except Exception as e:
            logger.error(f"Error refreshing break info: {e}", exc_info=True)
            self._show_error(str(e))

    def _show_default_status(self):
        """Показывает дефолтный статус"""
        self.title_label.setText("График: Дефолтный")
        self.breaks_label.setText("ПЕРЕРЫВЫ: 0/3 (осталось: 3, по 15 мин)")
        self.lunch_label.setText("ОБЕДЫ: 0/1 (осталось: 1, по 60 мин)")

        self.breaks_progress.setMaximum(3)
        self.breaks_progress.setValue(0)
        self.breaks_progress.setFormat("0/3")
        self._style_progress_bar(self.breaks_progress, 0, 3)
        self.breaks_progress.show()

        self.lunch_progress.setMaximum(1)
        self.lunch_progress.setValue(0)
        self.lunch_progress.setFormat("0/1")
        self._style_progress_bar(self.lunch_progress, 0, 1)
        self.lunch_progress.show()

        self.active_label.setText("")
        self.active_progress.hide()

    def _show_error(self, error_msg: str):
        """Показывает сообщение об ошибке"""
        self.title_label.setText("Ошибка загрузки")
        self.breaks_label.setText(f"Ошибка: {error_msg[:50]}")
        self.lunch_label.setText("")
        self.active_label.setText("")
        self.breaks_progress.hide()
        self.lunch_progress.hide()
        self.active_progress.hide()

    def _style_progress_bar(self, progress_bar: QProgressBar, value: int, maximum: int):
        """Стилизует прогресс-бар в зависимости от заполненности"""
        if maximum == 0:
            return

        ratio = value / maximum
        if ratio >= 1.0:
            # Все использованы - красный
            style = "QProgressBar::chunk { background-color: #e74c3c; }"
        elif ratio >= 0.66:
            # Большая часть - оранжевый
            style = "QProgressBar::chunk { background-color: #f39c12; }"
        else:
            # В норме - зелёный
            style = "QProgressBar::chunk { background-color: #27ae60; }"

        progress_bar.setStyleSheet(style)

    def force_refresh(self):
        """Принудительное обновление (вызывается извне)"""
        self.refresh()


# Тестирование виджета
if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)

    # Создаём виджет
    widget = BreakInfoWidget()
    widget.setWindowTitle("Break Info Widget Test")
    widget.resize(320, 400)

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
                    'Перерыв': 2,
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
