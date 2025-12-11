# admin_app/realtime_monitor.py
"""
Отдельное приложение мониторинга статусов пользователей в реальном времени

Запускается как отдельное окно, независимо от админки.
Отображает статусы пользователей, время пребывания в статусах,
активные перерывы с предупреждениями о превышении лимитов.
"""
from __future__ import annotations
import sys
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import logging

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox,
    QComboBox, QCheckBox, QSpinBox, QFrame, QDialog,
    QFormLayout, QDialogButtonBox, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QFont, QIcon
from shared.time_utils import format_datetime_moscow, format_time_moscow, to_moscow

logger = logging.getLogger(__name__)


class MonitorSettingsDialog(QDialog):
    """Диалог настроек мониторинга"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки мониторинга")
        self.setMinimumWidth(450)
        self._build_ui()
    
    def _build_ui(self):
        layout = QFormLayout(self)
        
        # Интервал обновления
        self.update_interval = QSpinBox()
        self.update_interval.setRange(1, 300)
        self.update_interval.setValue(5)
        self.update_interval.setSuffix(" сек")
        layout.addRow("Интервал обновления:", self.update_interval)
        
        # Сортировка
        self.sort_by = QComboBox()
        self.sort_by.addItems([
            "По ФИО",
            "По статусу",
            "По группам",
            "По времени залогинивания"
        ])
        layout.addRow("Сортировка:", self.sort_by)
        
        # Показывать только активных
        self.show_active_only = QCheckBox("Показывать только активных пользователей")
        self.show_active_only.setChecked(False)
        layout.addRow("", self.show_active_only)
        
        # Кнопки
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
    
    def get_settings(self) -> Dict:
        return {
            'update_interval': self.update_interval.value(),
            'sort_by': self.sort_by.currentText(),
            'show_active_only': self.show_active_only.isChecked()
        }
    
    def set_settings(self, settings: Dict):
        """Устанавливает настройки в диалог"""
        self.update_interval.setValue(settings.get('update_interval', 5))
        sort_by = settings.get('sort_by', 'По ФИО')
        index = self.sort_by.findText(sort_by)
        if index >= 0:
            self.sort_by.setCurrentIndex(index)
        self.show_active_only.setChecked(settings.get('show_active_only', False))


class RealtimeMonitorWindow(QMainWindow):
    """
    Отдельное окно мониторинга статусов в реальном времени
    
    Запускается как независимое приложение.
    """
    
    def __init__(self, repo, break_manager, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.break_mgr = break_manager
        
        # Настройки
        self.settings = {
            'update_interval': 5,  # секунд
            'sort_by': 'По ФИО',
            'show_active_only': False
        }
        
        # Данные
        self.users_data: Dict[str, Dict] = {}
        self.active_breaks: Dict[str, Dict] = {}
        self.last_update_time: Optional[datetime] = None
        
        # Таймер обновления
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._refresh_data)
        
        self._setup_ui()
        self._refresh_data()
        self._start_monitoring()
    
    def _setup_ui(self):
        """Создает интерфейс"""
        self.setWindowTitle("📺 Мониторинг статусов - WorkTimeTracker")
        self.setMinimumSize(1400, 800)
        
        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # Заголовок и панель управления
        header_layout = QHBoxLayout()
        
        title = QLabel("📺 МОНИТОРИНГ СТАТУСОВ В РЕАЛЬНОМ ВРЕМЕНИ")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Статус обновления
        self.status_label = QLabel("🟢 Активен")
        self.status_label.setStyleSheet("color: #27ae60; font-weight: bold; font-size: 12px;")
        header_layout.addWidget(self.status_label)
        
        # Время последнего обновления (московское)
        self.last_update_label = QLabel("Обновлено: --:--:--")
        self.last_update_label.setStyleSheet("font-size: 11px; color: #7f8c8d;")
        header_layout.addWidget(self.last_update_label)
        
        # Текущее московское время
        self.current_time_label = QLabel("МСК: --:--:--")
        self.current_time_label.setStyleSheet("font-size: 11px; color: #34495e; font-weight: bold;")
        header_layout.addWidget(self.current_time_label)
        
        # Таймер для отображения текущего времени
        self.time_timer = QTimer(self)
        self.time_timer.timeout.connect(self._update_current_time)
        self.time_timer.start(1000)  # Обновляем каждую секунду
        self._update_current_time()
        
        # Кнопки управления
        btn_refresh = QPushButton("🔄 Обновить")
        btn_refresh.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
                border-radius: 4px;
                background-color: #3498db;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        btn_refresh.clicked.connect(self._refresh_data)
        header_layout.addWidget(btn_refresh)
        
        btn_settings = QPushButton("⚙️ Настройки")
        btn_settings.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
                border-radius: 4px;
                background-color: #95a5a6;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        btn_settings.clicked.connect(self._open_settings)
        header_layout.addWidget(btn_settings)
        
        main_layout.addLayout(header_layout)
        
        # Разделитель
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(line)
        
        # Дашборд (карточки статистики)
        dashboard_layout = QHBoxLayout()
        dashboard_layout.setSpacing(15)
        
        self.working_now_card = self._create_dashboard_card(
            "Сейчас работают", "0", "#27ae60"
        )
        dashboard_layout.addWidget(self.working_now_card)
        
        self.on_break_card = self._create_dashboard_card(
            "В перерыве", "0", "#f39c12"
        )
        dashboard_layout.addWidget(self.on_break_card)
        
        self.on_lunch_card = self._create_dashboard_card(
            "На обеде", "0", "#e67e22"
        )
        dashboard_layout.addWidget(self.on_lunch_card)
        
        self.over_limit_card = self._create_dashboard_card(
            "Превышают лимит", "0", "#e74c3c"
        )
        dashboard_layout.addWidget(self.over_limit_card)
        
        self.total_card = self._create_dashboard_card(
            "Всего активных", "0", "#3498db"
        )
        dashboard_layout.addWidget(self.total_card)
        
        main_layout.addLayout(dashboard_layout)
        
        # Разделитель
        line2 = QFrame()
        line2.setFrameShape(QFrame.HLine)
        line2.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(line2)
        
        # Фильтры
        filters_layout = QHBoxLayout()
        filters_layout.addWidget(QLabel("Группа:"))
        
        self.group_filter = QComboBox()
        self.group_filter.addItem("Все группы")
        self.group_filter.currentTextChanged.connect(self._apply_filters)
        filters_layout.addWidget(self.group_filter)
        
        filters_layout.addWidget(QLabel("Статус:"))
        
        self.status_filter = QComboBox()
        self.status_filter.addItem("Все статусы")
        self.status_filter.currentTextChanged.connect(self._apply_filters)
        filters_layout.addWidget(self.status_filter)
        
        filters_layout.addStretch()
        main_layout.addLayout(filters_layout)
        
        # Таблица мониторинга
        table_group = QGroupBox("Статусы пользователей")
        table_layout = QVBoxLayout()
        
        self.monitor_table = QTableWidget()
        self.monitor_table.setColumnCount(7)
        self.monitor_table.setHorizontalHeaderLabels([
            "Сотрудник", "Группа", "Статус", "Время в статусе", 
            "Перерыв/Обед", "Время перерыва", "Предупреждение"
        ])
        
        # Настройка таблицы
        header = self.monitor_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.Stretch)
        
        self.monitor_table.setAlternatingRowColors(True)
        self.monitor_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.monitor_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.monitor_table.setSortingEnabled(False)  # Сортировка через настройки
        
        table_layout.addWidget(self.monitor_table)
        table_group.setLayout(table_layout)
        main_layout.addWidget(table_group)
    
    def _create_dashboard_card(self, title: str, value: str, color: str) -> QGroupBox:
        """Создает карточку дашборда"""
        card = QGroupBox(title)
        card.setStyleSheet(f"""
            QGroupBox {{
                border: 2px solid {color};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
                font-weight: bold;
                background-color: #f8f9fa;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: {color};
                font-size: 13px;
            }}
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 5, 10, 10)
        
        value_label = QLabel(value)
        value_font = QFont()
        value_font.setPointSize(28)
        value_font.setBold(True)
        value_label.setFont(value_font)
        value_label.setAlignment(Qt.AlignCenter)
        value_label.setStyleSheet(f"color: {color};")
        layout.addWidget(value_label)
        
        card.setLayout(layout)
        card.setMinimumHeight(100)
        card.setMinimumWidth(200)
        
        # Сохраняем ссылку на label для обновления
        setattr(self, f"{title.lower().replace(' ', '_').replace('/', '_')}_value", value_label)
        
        return card
    
    def _update_current_time(self):
        """Обновляет отображение текущего московского времени"""
        try:
            from shared.time_utils import now_moscow
            moscow_now = now_moscow()
            time_str = moscow_now.strftime('%H:%M:%S')
            self.current_time_label.setText(f"МСК: {time_str}")
        except Exception as e:
            logger.debug(f"Failed to update current time: {e}")
    
    def _start_monitoring(self):
        """Запускает автоматическое обновление"""
        interval_ms = self.settings['update_interval'] * 1000
        self.update_timer.start(interval_ms)
        logger.info(f"Мониторинг запущен с интервалом {self.settings['update_interval']} сек")
    
    def _stop_monitoring(self):
        """Останавливает автоматическое обновление"""
        self.update_timer.stop()
        logger.info("Мониторинг остановлен")
    
    def _refresh_data(self):
        """Обновляет данные мониторинга"""
        try:
            # Получаем активные сессии
            sessions = self.repo.get_active_sessions()
            
            # Получаем активные перерывы
            try:
                active_breaks_list = self.break_mgr.get_all_active_breaks()
                self.active_breaks = {
                    break_data.get('Email', '').lower(): break_data
                    for break_data in active_breaks_list
                }
            except Exception as e:
                logger.warning(f"Failed to get active breaks: {e}")
                self.active_breaks = {}
            
            # Получаем список пользователей
            users = self.repo.list_users()
            users_dict = {u.get('Email', '').lower(): u for u in users}
            
            # Обновляем данные пользователей
            self.users_data = {}
            for session in sessions:
                email = session.get('Email', '').lower()
                if not email:
                    continue
                
                user = users_dict.get(email, {})
                status = session.get('Status', 'Неизвестно')
                login_time_str = session.get('LoginTime', '')
                
                # Вычисляем время в статусе
                time_in_status = self._calculate_time_in_status(login_time_str, status)
                
                # Получаем информацию о перерыве
                break_info = self.active_breaks.get(email, {})
                break_type = break_info.get('BreakType', '')
                break_start = break_info.get('StartTime', '')
                break_duration = break_info.get('Duration', 0)
                
                # Получаем лимит из графика пользователя
                break_limit = 15  # Default для перерыва
                if break_type == 'Обед':
                    break_limit = 60
                elif break_type == 'Перерыв':
                    break_limit = 15
                
                # Пытаемся получить лимит из графика пользователя
                try:
                    schedule = self.break_mgr.get_user_schedule(email)
                    if schedule and schedule.limits:
                        for limit in schedule.limits:
                            if limit.break_type == break_type:
                                break_limit = limit.time_minutes
                                break
                except Exception as e:
                    logger.debug(f"Failed to get schedule limit for {email}: {e}")
                
                is_over_limit = break_info.get('is_over_limit', False)
                
                self.users_data[email] = {
                    'email': email,
                    'name': user.get('Name', email),
                    'group': user.get('Group', 'Без группы'),
                    'status': status,
                    'login_time': login_time_str,
                    'time_in_status': time_in_status,
                    'break_type': break_type,
                    'break_start': break_start,
                    'break_duration': break_duration,
                    'break_limit': break_limit,
                    'is_over_limit': is_over_limit,
                    'session_id': session.get('SessionID', '')
                }
            
            # Обновляем интерфейс
            self._update_dashboard()
            self._update_table()
            self._update_filters()
            
            # Обновляем время последнего обновления (московское)
            self.last_update_time = datetime.now()
            moscow_time = format_time_moscow(self.last_update_time, '%H:%M:%S')
            self.last_update_label.setText(f"Обновлено: {moscow_time}")
            
        except Exception as e:
            logger.error(f"Error refreshing monitor data: {e}", exc_info=True)
            self.status_label.setText("🔴 Ошибка")
            self.status_label.setStyleSheet("color: #e74c3c; font-weight: bold; font-size: 12px;")
    
    def _calculate_time_in_status(self, login_time_str: str, status: str) -> str:
        """Вычисляет время пребывания в статусе (московское время)"""
        if not login_time_str:
            return "00:00:00"
        
        try:
            # Парсим время логина
            login_time = datetime.fromisoformat(login_time_str.replace('Z', '+00:00'))
            if login_time.tzinfo is None:
                login_time = login_time.replace(tzinfo=datetime.now().astimezone().tzinfo)
            
            # Конвертируем в московское время
            login_time_moscow = to_moscow(login_time)
            if not login_time_moscow:
                return "00:00:00"
            
            # Текущее время в московском
            from shared.time_utils import now_moscow
            now_moscow_dt = now_moscow()
            
            # Вычисляем разницу
            delta = now_moscow_dt - login_time_moscow
            
            hours = int(delta.total_seconds() // 3600)
            minutes = int((delta.total_seconds() % 3600) // 60)
            seconds = int(delta.total_seconds() % 60)
            
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            
        except Exception as e:
            logger.warning(f"Failed to calculate time in status: {e}")
            return "00:00:00"
    
    def _update_dashboard(self):
        """Обновляет карточки дашборда"""
        # Сейчас работают (активные сессии, не в перерыве/обеде)
        working_now = len([
            u for u in self.users_data.values() 
            if u['status'] not in ('finished', 'completed', 'kicked') 
            and not u['break_type']
        ])
        
        # В перерыве
        on_break = len([
            u for u in self.users_data.values() 
            if u['break_type'] == 'Перерыв'
        ])
        
        # На обеде
        on_lunch = len([
            u for u in self.users_data.values() 
            if u['break_type'] == 'Обед'
        ])
        
        # Превышают лимит
        over_limit = len([
            u for u in self.users_data.values() 
            if u['is_over_limit']
        ])
        
        # Всего активных
        total_active = len([
            u for u in self.users_data.values() 
            if u['status'] not in ('finished', 'completed', 'kicked')
        ])
        
        self.working_now_card.findChild(QLabel).setText(str(working_now))
        self.on_break_card.findChild(QLabel).setText(str(on_break))
        self.on_lunch_card.findChild(QLabel).setText(str(on_lunch))
        self.over_limit_card.findChild(QLabel).setText(str(over_limit))
        self.total_card.findChild(QLabel).setText(str(total_active))
    
    def _update_table(self):
        """Обновляет таблицу мониторинга"""
        # Фильтруем данные
        filtered_data = list(self.users_data.values())
        
        # Фильтр по группе
        selected_group = self.group_filter.currentText()
        if selected_group != "Все группы":
            filtered_data = [u for u in filtered_data if u['group'] == selected_group]
        
        # Фильтр по статусу
        selected_status = self.status_filter.currentText()
        if selected_status != "Все статусы":
            filtered_data = [u for u in filtered_data if u['status'] == selected_status]
        
        # Фильтр "только активные"
        if self.settings['show_active_only']:
            filtered_data = [u for u in filtered_data if u['status'] not in ('finished', 'completed', 'kicked')]
        
        # Сортировка согласно настройкам
        sort_by = self.settings.get('sort_by', 'По ФИО')
        if sort_by == 'По ФИО':
            filtered_data.sort(key=lambda x: x['name'])
        elif sort_by == 'По статусу':
            filtered_data.sort(key=lambda x: x['status'])
        elif sort_by == 'По группам':
            filtered_data.sort(key=lambda x: (x['group'], x['name']))
        elif sort_by == 'По времени залогинивания':
            filtered_data.sort(key=lambda x: x['login_time'] or '', reverse=True)
        
        # Заполняем таблицу
        self.monitor_table.setRowCount(len(filtered_data))
        
        for row, user_data in enumerate(filtered_data):
            # Сотрудник
            name_item = QTableWidgetItem(user_data['name'])
            name_item.setData(Qt.UserRole, user_data['email'])
            self.monitor_table.setItem(row, 0, name_item)
            
            # Группа
            group_item = QTableWidgetItem(user_data['group'])
            self.monitor_table.setItem(row, 1, group_item)
            
            # Статус с цветовой индикацией
            status = user_data['status']
            status_item = QTableWidgetItem(status)
            status_color = self._get_status_color(status)
            status_item.setForeground(QColor(status_color))
            status_item.setFont(QFont("Arial", 10, QFont.Bold))
            self.monitor_table.setItem(row, 2, status_item)
            
            # Время в статусе (московское)
            time_item = QTableWidgetItem(user_data['time_in_status'])
            self.monitor_table.setItem(row, 3, time_item)
            
            # Перерыв/Обед
            break_type = user_data['break_type']
            if break_type:
                break_item = QTableWidgetItem(break_type)
                break_item.setForeground(QColor("#f39c12"))
                break_item.setFont(QFont("Arial", 10, QFont.Bold))
            else:
                break_item = QTableWidgetItem("—")
            self.monitor_table.setItem(row, 4, break_item)
            
            # Время перерыва (московское)
            if break_type and user_data['break_start']:
                break_start_moscow = format_time_moscow(user_data['break_start'], '%H:%M')
                break_duration = user_data['break_duration']
                break_limit = user_data['break_limit']
                break_time_text = f"{break_start_moscow} ({break_duration}/{break_limit} мин)"
                
                break_time_item = QTableWidgetItem(break_time_text)
                if user_data['is_over_limit']:
                    break_time_item.setForeground(QColor("#e74c3c"))
                    break_time_item.setFont(QFont("Arial", 10, QFont.Bold))
                else:
                    break_time_item.setForeground(QColor("#f39c12"))
            else:
                break_time_item = QTableWidgetItem("—")
            self.monitor_table.setItem(row, 5, break_time_item)
            
            # Предупреждение
            warning_text = ""
            warning_color = None
            if user_data['is_over_limit']:
                overage = user_data['break_duration'] - user_data['break_limit']
                warning_text = f"⚠️ Превышен лимит на {overage} мин"
                warning_color = QColor("#e74c3c")
            elif break_type and user_data['break_duration'] >= user_data['break_limit'] - 2:
                warning_text = "⏰ Скоро закончится"
                warning_color = QColor("#f39c12")
            
            warning_item = QTableWidgetItem(warning_text)
            if warning_color:
                warning_item.setForeground(warning_color)
                warning_item.setFont(QFont("Arial", 9, QFont.Bold))
            self.monitor_table.setItem(row, 6, warning_item)
        
        # Обновляем статус
        self.status_label.setText("🟢 Активен")
        self.status_label.setStyleSheet("color: #27ae60; font-weight: bold; font-size: 12px;")
    
    def _get_status_color(self, status: str) -> str:
        """Возвращает цвет для статуса"""
        status_colors = {
            'В работе': '#27ae60',
            'На задаче': '#3498db',
            'Перерыв': '#f39c12',
            'Обед': '#e67e22',
            'Чат': '#9b59b6',
            'Запись': '#1abc9c',
            'finished': '#95a5a6',
            'completed': '#95a5a6',
            'kicked': '#e74c3c',
        }
        return status_colors.get(status, '#34495e')
    
    def _update_filters(self):
        """Обновляет списки фильтров"""
        # Группы
        current_group = self.group_filter.currentText()
        groups = set(u['group'] for u in self.users_data.values())
        self.group_filter.clear()
        self.group_filter.addItem("Все группы")
        for group in sorted(groups):
            self.group_filter.addItem(group)
        
        # Восстанавливаем выбор
        index = self.group_filter.findText(current_group)
        if index >= 0:
            self.group_filter.setCurrentIndex(index)
        
        # Статусы
        current_status = self.status_filter.currentText()
        statuses = set(u['status'] for u in self.users_data.values())
        self.status_filter.clear()
        self.status_filter.addItem("Все статусы")
        for status in sorted(statuses):
            self.status_filter.addItem(status)
        
        # Восстанавливаем выбор
        index = self.status_filter.findText(current_status)
        if index >= 0:
            self.status_filter.setCurrentIndex(index)
    
    def _apply_filters(self):
        """Применяет фильтры"""
        self._update_table()
    
    def _open_settings(self):
        """Открывает диалог настроек"""
        dialog = MonitorSettingsDialog(self)
        dialog.set_settings(self.settings)
        
        if dialog.exec_() == QDialog.Accepted:
            new_settings = dialog.get_settings()
            self.settings.update(new_settings)
            
            # Перезапускаем таймер с новым интервалом
            self._stop_monitoring()
            self._start_monitoring()
            
            # Обновляем таблицу с новыми настройками сортировки
            self._update_table()
            
            logger.info(f"Settings updated: {self.settings}")


def run_monitor(repo=None, break_manager=None):
    """
    Запускает отдельное окно мониторинга
    
    Args:
        repo: Экземпляр AdminRepo (если None, создается новый)
        break_manager: Экземпляр BreakManager (если None, создается новый)
    """
    import sys
    from pathlib import Path
    
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(PROJECT_ROOT))
    
    # Импорты
    if repo is None:
        from admin_app.repo import AdminRepo
        repo = AdminRepo()
    
    if break_manager is None:
        from admin_app.break_manager import BreakManager
        break_manager = BreakManager(repo.sheets)
    
    # Создаем приложение
    app = QApplication(sys.argv)
    
    # Создаем окно мониторинга
    window = RealtimeMonitorWindow(repo, break_manager)
    window.show()
    
    # Запускаем приложение
    sys.exit(app.exec_())


if __name__ == "__main__":
    run_monitor()
