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
from datetime import datetime, date
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
        
        # Фильтр по группе
        self.group_filter_combo = QComboBox()
        self.group_filter_combo.addItems([
            "Все",
            "Входящие",
            "Запись",
            "Стоматология",
            "Почта"
        ])
        layout.addRow("Фильтр по группе:", self.group_filter_combo)
        
        # Кнопки
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
    
    def get_settings(self) -> Dict:
        return {
            'update_interval': self.update_interval.value(),
            'sort_by': self.sort_by.currentText(),
            'group_filter': self.group_filter_combo.currentText()
        }
    
    def set_settings(self, settings: Dict):
        """Устанавливает настройки в диалог"""
        self.update_interval.setValue(settings.get('update_interval', 5))
        sort_by = settings.get('sort_by', 'По ФИО')
        index = self.sort_by.findText(sort_by)
        if index >= 0:
            self.sort_by.setCurrentIndex(index)
        group_filter = settings.get('group_filter', 'Все')
        index = self.group_filter_combo.findText(group_filter)
        if index >= 0:
            self.group_filter_combo.setCurrentIndex(index)


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
            'group_filter': 'Все'
        }
        
        # Продуктивные статусы (из config.py)
        self.productive_statuses = {
            'В работе', 'Чат', 'Аудио', 'Запись', 'Анкеты',
            'Стоматология', 'Входящие', 'Почта', 'На задаче'
        }
        
        # Непродуктивные статусы (отдых)
        self.rest_statuses = {'Перерыв', 'Обед'}
        
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
        dashboard_layout.setSpacing(20)
        
        self.total_online_card = self._create_dashboard_card(
            "Сейчас в системе", "0", "#3498db"
        )
        dashboard_layout.addWidget(self.total_online_card)
        
        self.working_now_card = self._create_dashboard_card(
            "Сейчас работают", "0", "#27ae60"
        )
        dashboard_layout.addWidget(self.working_now_card)
        
        self.resting_now_card = self._create_dashboard_card(
            "Сейчас отдыхают", "0", "#f39c12"
        )
        dashboard_layout.addWidget(self.resting_now_card)
        
        main_layout.addLayout(dashboard_layout)
        
        # Разделитель
        line2 = QFrame()
        line2.setFrameShape(QFrame.HLine)
        line2.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(line2)
        
        # Фильтры (убраны, теперь в настройках)
        
        # Таблица мониторинга
        table_group = QGroupBox("Статусы пользователей")
        table_layout = QVBoxLayout()
        
        self.monitor_table = QTableWidget()
        self.monitor_table.setColumnCount(5)
        self.monitor_table.setHorizontalHeaderLabels([
            "Сотрудник", "Группа", "Текущий статус", 
            "Время в системе", "Время в текущем статусе"
        ])
        
        # Увеличиваем размер шрифта для таблицы
        header_font = QFont()
        header_font.setPointSize(12)
        header_font.setBold(True)
        self.monitor_table.horizontalHeader().setFont(header_font)
        
        table_font = QFont()
        table_font.setPointSize(11)
        self.monitor_table.setFont(table_font)
        
        # Настройка таблицы
        header = self.monitor_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        
        # Увеличиваем высоту строк
        self.monitor_table.verticalHeader().setDefaultSectionSize(40)
        
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
        value_font.setPointSize(32)
        value_font.setBold(True)
        value_label.setFont(value_font)
        value_label.setAlignment(Qt.AlignCenter)
        value_label.setStyleSheet(f"color: {color};")
        layout.addWidget(value_label)
        
        # Подзаголовок
        subtitle_label = QLabel("чел.")
        subtitle_font = QFont()
        subtitle_font.setPointSize(10)
        subtitle_label.setFont(subtitle_font)
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setStyleSheet("color: #7f8c8d;")
        layout.addWidget(subtitle_label)
        
        card.setLayout(layout)
        card.setMinimumHeight(100)
        card.setMinimumWidth(200)
        
        # Не сохраняем ссылку, будем искать через findChildren
        
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

            # Получаем текущие рабочие статусы из work_log
            current_statuses = self._get_current_user_statuses()

            # Обновляем данные пользователей
            self.users_data = {}
            for session in sessions:
                email = session.get('Email', '').lower()
                if not email:
                    continue

                # Пропускаем тестовых пользователей
                if 'test' in email or 'example.com' in email:
                    logger.debug(f"Пропущен тестовый пользователь: {email}")
                    continue

                # Пропускаем пользователей, которых нет в списке Users
                user = users_dict.get(email, {})
                if not user:
                    logger.debug(f"Пропущен пользователь без записи в Users: {email}")
                    continue

                # ИСПРАВЛЕНО: Получаем РАБОЧИЙ статус из work_log, а не статус сессии
                status = current_statuses.get(email, {}).get('status', 'Неизвестно')
                status_timestamp = current_statuses.get(email, {}).get('timestamp', '')

                login_time_str = session.get('LoginTime', '')

                # Вычисляем время в системе (с момента залогинивания)
                time_in_system = self._calculate_time_since(login_time_str)

                # Вычисляем время в текущем статусе (с момента смены статуса или логина)
                time_in_current_status = self._calculate_time_since(status_timestamp or login_time_str)
                
                # Получаем информацию о перерыве
                break_info = self.active_breaks.get(email, {})
                break_type = break_info.get('BreakType', '')
                break_start = break_info.get('StartTime', '')
                break_duration = break_info.get('Duration', 0)
                
                # Лимиты: обед 60 мин, перерыв 15 мин
                break_limit = 60 if break_type == 'Обед' else 15 if break_type == 'Перерыв' else 0
                
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
                
                # Проверяем превышение лимита
                is_over_limit = break_duration > break_limit if break_limit > 0 else False
                
                self.users_data[email] = {
                    'email': email,
                    'name': user.get('Name', email),
                    'group': user.get('Group', 'Без группы'),
                    'status': status,
                    'login_time': login_time_str,
                    'time_in_system': time_in_system,
                    'time_in_current_status': time_in_current_status,
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
            
            # Обновляем время последнего обновления (московское)
            self.last_update_time = datetime.now()
            moscow_time = format_time_moscow(self.last_update_time, '%H:%M:%S')
            self.last_update_label.setText(f"Обновлено: {moscow_time}")
            
        except Exception as e:
            logger.error(f"Error refreshing monitor data: {e}", exc_info=True)
            self.status_label.setText("🔴 Ошибка")
            self.status_label.setStyleSheet("color: #e74c3c; font-weight: bold; font-size: 12px;")
    
    def _get_current_user_statuses(self) -> Dict[str, Dict]:
        """
        Получает текущие рабочие статусы всех пользователей из work_log.
        Возвращает словарь: {email: {'status': '...', 'timestamp': '...'}}
        """
        try:
            # Получаем записи work_log за сегодня
            today = datetime.now().date().isoformat()
            work_log_data = self.repo.get_work_log_data(
                date_from=today,
                date_to=today
            )

            # Группируем по email и находим последнюю запись со статусом
            user_statuses = {}
            for log_entry in work_log_data:
                email = (log_entry.get('email') or '').lower()
                action_type = log_entry.get('action_type', '')
                status = log_entry.get('status', '')
                timestamp = log_entry.get('timestamp', '')

                # Ищем записи LOGIN или STATUS_CHANGE
                if email and action_type in ('LOGIN', 'STATUS_CHANGE') and status:
                    # Обновляем, если это более поздняя запись
                    if email not in user_statuses or timestamp > user_statuses[email].get('timestamp', ''):
                        user_statuses[email] = {
                            'status': status,
                            'timestamp': timestamp
                        }

            return user_statuses
        except Exception as e:
            logger.error(f"Failed to get current user statuses: {e}")
            return {}

    def _calculate_time_since(self, time_str: str) -> str:
        """Вычисляет время с указанного момента (в московском времени)"""
        if not time_str:
            return "00:00:00"

        try:
            # Парсим время
            time_dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            # ИСПРАВЛЕНО: Если нет timezone, считаем что это UTC, а не локальное время
            if time_dt.tzinfo is None:
                from datetime import timezone
                time_dt = time_dt.replace(tzinfo=timezone.utc)

            # Конвертируем в московское время
            time_moscow = to_moscow(time_dt)
            if not time_moscow:
                return "00:00:00"

            # Текущее время в московском
            from shared.time_utils import now_moscow
            now_moscow_dt = now_moscow()

            # Вычисляем разницу
            delta = now_moscow_dt - time_moscow

            hours = int(delta.total_seconds() // 3600)
            minutes = int((delta.total_seconds() % 3600) // 60)
            seconds = int(delta.total_seconds() % 60)

            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        except Exception as e:
            logger.warning(f"Failed to calculate time since {time_str}: {e}")
            return "00:00:00"
    
    
    def _update_dashboard(self):
        """Обновляет карточки дашборда"""
        # Всего в системе (активные сессии)
        total_online = len([
            u for u in self.users_data.values() 
            if u['status'] not in ('finished', 'completed', 'kicked')
        ])
        
        # Сейчас работают (продуктивные статусы)
        working_now = len([
            u for u in self.users_data.values() 
            if u['status'] in self.productive_statuses
            and u['status'] not in ('finished', 'completed', 'kicked')
        ])
        
        # Сейчас отдыхают (перерыв или обед)
        resting_now = len([
            u for u in self.users_data.values() 
            if u['status'] in self.rest_statuses or u['break_type'] in self.rest_statuses
        ])
        
        # Обновляем карточки (берем первый QLabel - это значение)
        total_label = self.total_online_card.findChildren(QLabel)[0]
        total_label.setText(str(total_online))
        
        working_label = self.working_now_card.findChildren(QLabel)[0]
        working_label.setText(str(working_now))
        
        resting_label = self.resting_now_card.findChildren(QLabel)[0]
        resting_label.setText(str(resting_now))
    
    def _update_table(self):
        """Обновляет таблицу мониторинга"""
        # Фильтруем данные
        filtered_data = list(self.users_data.values())
        
        # Фильтр по группе из настроек
        selected_group = self.settings.get('group_filter', 'Все')
        if selected_group != "Все":
            filtered_data = [u for u in filtered_data if u['group'] == selected_group]
        
        # Только активные (исключаем завершенные сессии)
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
            # Сотрудник (крупный шрифт)
            name_item = QTableWidgetItem(user_data['name'])
            name_item.setData(Qt.UserRole, user_data['email'])
            name_font = QFont()
            name_font.setPointSize(11)
            name_font.setBold(True)
            name_item.setFont(name_font)
            self.monitor_table.setItem(row, 0, name_item)
            
            # Группа
            group_item = QTableWidgetItem(user_data['group'])
            group_font = QFont()
            group_font.setPointSize(11)
            group_item.setFont(group_font)
            self.monitor_table.setItem(row, 1, group_item)
            
            # Текущий статус с цветовой индикацией
            status = user_data['status']
            break_type = user_data['break_type']
            break_duration = user_data['break_duration']
            break_limit = user_data['break_limit']
            is_over_limit = user_data['is_over_limit']
            
            # Формируем текст статуса
            if break_type:
                status_text = f"{status} ({break_type})"
            else:
                status_text = status
            
            status_item = QTableWidgetItem(status_text)
            status_font = QFont()
            status_font.setPointSize(11)
            status_font.setBold(True)
            status_item.setFont(status_font)
            
            # Цветовая индикация: красный если превышен лимит перерыва/обеда
            if is_over_limit:
                status_item.setForeground(QColor("#e74c3c"))
                status_item.setBackground(QColor("#ffebee"))  # Светло-красный фон
            else:
                status_color = self._get_status_color(status)
                status_item.setForeground(QColor(status_color))
            
            self.monitor_table.setItem(row, 2, status_item)
            
            # Время в системе (московское)
            time_in_system_item = QTableWidgetItem(user_data['time_in_system'])
            time_font = QFont()
            time_font.setPointSize(11)
            time_font.setFamily("Courier")  # Моноширинный для времени
            time_in_system_item.setFont(time_font)
            self.monitor_table.setItem(row, 3, time_in_system_item)
            
            # Время в текущем статусе (московское)
            time_in_status_item = QTableWidgetItem(user_data['time_in_current_status'])
            time_in_status_item.setFont(time_font)
            
            # Если превышен лимит перерыва/обеда, подсвечиваем красным
            if is_over_limit:
                time_in_status_item.setForeground(QColor("#e74c3c"))
                time_in_status_item.setBackground(QColor("#ffebee"))
                time_in_status_item.setFont(QFont("Courier", 11, QFont.Bold))
            
            self.monitor_table.setItem(row, 4, time_in_status_item)
        
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
        """Обновляет списки фильтров (не используется, фильтры в настройках)"""
        pass
    
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
