# admin_app/reports_tab.py
"""
Вкладка отчетов системы учета рабочего времени

Реализует:
- Отчет по сотрудникам
- Отчет по группам
- Отчет по типам статусов
- Отчет по продуктивным статусам
- Отчет по нарушениям
- Отчет по перерывам
- Сравнительный отчет
- Отчет по сессиям работы
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox,
    QDateEdit, QComboBox, QLineEdit, QSplitter, QFrame,
    QMessageBox, QFileDialog, QTabWidget, QCheckBox, QSpinBox,
    QProgressBar, QTextEdit
)
from PyQt5.QtCore import Qt, QDate, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional
import logging
import json

logger = logging.getLogger(__name__)


class ReportsTab(QWidget):
    """Вкладка отчетов"""
    
    def __init__(self, repo, break_manager, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.break_mgr = break_manager
        self.current_data = []
        self._setup_ui()
        
        # Начальная загрузка
        self._load_initial_data()
    
    def _setup_ui(self):
        """Создаёт интерфейс"""
        layout = QVBoxLayout(self)
        
        # Заголовок
        header = QLabel("📊 Система отчетов")
        header_font = QFont()
        header_font.setPointSize(16)
        header_font.setBold(True)
        header.setFont(header_font)
        layout.addWidget(header)
        
        # Разделитель
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)
        
        # Панель фильтров
        filters_group = self._build_filters()
        layout.addWidget(filters_group)
        
        # Вкладки с отчетами
        self.reports_tabs = QTabWidget()
        self._build_report_tabs()
        layout.addWidget(self.reports_tabs)
        
        # Панель действий
        actions_group = self._build_actions()
        layout.addWidget(actions_group)
    
    def _build_filters(self) -> QGroupBox:
        """Создаёт панель фильтров"""
        group = QGroupBox("Фильтры")
        layout = QVBoxLayout()
        
        # Первая строка: период
        period_layout = QHBoxLayout()
        period_layout.addWidget(QLabel("Период:"))
        
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addDays(-7))  # По умолчанию последние 7 дней
        period_layout.addWidget(self.date_from)
        
        period_layout.addWidget(QLabel("—"))
        
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        period_layout.addWidget(self.date_to)
        
        # Быстрые периоды
        btn_today = QPushButton("Сегодня")
        btn_today.clicked.connect(lambda: self._set_period_today())
        period_layout.addWidget(btn_today)
        
        btn_week = QPushButton("Неделя")
        btn_week.clicked.connect(lambda: self._set_period_week())
        period_layout.addWidget(btn_week)
        
        btn_month = QPushButton("Месяц")
        btn_month.clicked.connect(lambda: self._set_period_month())
        period_layout.addWidget(btn_month)
        
        period_layout.addStretch()
        layout.addLayout(period_layout)
        
        # Вторая строка: сотрудники и группы
        users_groups_layout = QHBoxLayout()
        users_groups_layout.addWidget(QLabel("Сотрудники:"))
        
        self.users_combo = QComboBox()
        self.users_combo.setEditable(True)
        self.users_combo.addItem("Все сотрудники")
        self.users_combo.setInsertPolicy(QComboBox.NoInsert)
        users_groups_layout.addWidget(self.users_combo)
        
        users_groups_layout.addWidget(QLabel("Группы:"))
        
        self.groups_combo = QComboBox()
        self.groups_combo.setEditable(True)
        self.groups_combo.addItem("Все группы")
        self.groups_combo.setInsertPolicy(QComboBox.NoInsert)
        users_groups_layout.addWidget(self.groups_combo)
        
        users_groups_layout.addStretch()
        layout.addLayout(users_groups_layout)
        
        # Третья строка: кнопка применения фильтров
        apply_layout = QHBoxLayout()
        apply_layout.addStretch()
        
        btn_apply = QPushButton("Применить фильтры")
        btn_apply.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 5px 15px;")
        btn_apply.clicked.connect(self._apply_filters)
        apply_layout.addWidget(btn_apply)
        
        layout.addLayout(apply_layout)
        
        group.setLayout(layout)
        return group
    
    def _build_report_tabs(self):
        """Создаёт вкладки с отчетами"""
        # Отчет по сотрудникам
        self.employees_tab = self._build_employees_report()
        self.reports_tabs.addTab(self.employees_tab, "👤 По сотрудникам")
        
        # Отчет по группам
        self.groups_tab = self._build_groups_report()
        self.reports_tabs.addTab(self.groups_tab, "👥 По группам")
        
        # Отчет по типам статусов
        self.statuses_tab = self._build_statuses_report()
        self.reports_tabs.addTab(self.statuses_tab, "📋 По статусам")
        
        # Отчет по продуктивным статусам
        self.productivity_tab = self._build_productivity_report()
        self.reports_tabs.addTab(self.productivity_tab, "⚡ Продуктивность")
        
        # Отчет по нарушениям
        self.violations_tab = self._build_violations_report()
        self.reports_tabs.addTab(self.violations_tab, "⚠️ Нарушения")
        
        # Отчет по перерывам
        self.breaks_tab = self._build_breaks_report()
        self.reports_tabs.addTab(self.breaks_tab, "☕ Перерывы")
    
    def _build_employees_report(self) -> QWidget:
        """Создаёт отчет по сотрудникам"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Сводные карточки
        cards_layout = QHBoxLayout()
        
        self.emp_total_time_card = self._create_metric_card("Общее время", "0:00")
        cards_layout.addWidget(self.emp_total_time_card)
        
        self.emp_productive_card = self._create_metric_card("Продуктивное время", "0:00")
        cards_layout.addWidget(self.emp_productive_card)
        
        self.emp_productivity_card = self._create_metric_card("Продуктивность", "0%")
        cards_layout.addWidget(self.emp_productivity_card)
        
        self.emp_sessions_card = self._create_metric_card("Сессий", "0")
        cards_layout.addWidget(self.emp_sessions_card)
        
        layout.addLayout(cards_layout)
        
        # Таблица
        self.employees_table = QTableWidget()
        self.employees_table.setColumnCount(8)
        self.employees_table.setHorizontalHeaderLabels([
            "Сотрудник", "Группа", "Общее время", "Продуктивное время",
            "Продуктивность", "Сессий", "Нарушений", "Детали"
        ])
        self.employees_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.employees_table.setAlternatingRowColors(True)
        layout.addWidget(self.employees_table)
        
        return widget
    
    def _build_groups_report(self) -> QWidget:
        """Создаёт отчет по группам"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Сводные карточки
        cards_layout = QHBoxLayout()
        
        self.grp_total_time_card = self._create_metric_card("Общее время", "0:00")
        cards_layout.addWidget(self.grp_total_time_card)
        
        self.grp_avg_time_card = self._create_metric_card("Среднее время", "0:00")
        cards_layout.addWidget(self.grp_avg_time_card)
        
        self.grp_productivity_card = self._create_metric_card("Продуктивность", "0%")
        cards_layout.addWidget(self.grp_productivity_card)
        
        self.grp_violations_card = self._create_metric_card("Нарушений", "0")
        cards_layout.addWidget(self.grp_violations_card)
        
        layout.addLayout(cards_layout)
        
        # Таблица
        self.groups_table = QTableWidget()
        self.groups_table.setColumnCount(7)
        self.groups_table.setHorizontalHeaderLabels([
            "Группа", "Сотрудников", "Общее время", "Среднее время",
            "Продуктивность", "Нарушений", "Детали"
        ])
        self.groups_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.groups_table.setAlternatingRowColors(True)
        layout.addWidget(self.groups_table)
        
        return widget
    
    def _build_statuses_report(self) -> QWidget:
        """Создаёт отчет по типам статусов"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Таблица
        self.statuses_table = QTableWidget()
        self.statuses_table.setColumnCount(6)
        self.statuses_table.setHorizontalHeaderLabels([
            "Статус", "Время", "Процент", "Переходов", "Средняя длительность", "Сотрудников"
        ])
        self.statuses_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.statuses_table.setAlternatingRowColors(True)
        layout.addWidget(self.statuses_table)
        
        return widget
    
    def _build_productivity_report(self) -> QWidget:
        """Создаёт отчет по продуктивным статусам"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Сводные карточки
        cards_layout = QHBoxLayout()
        
        self.prod_total_card = self._create_metric_card("Продуктивное время", "0:00")
        cards_layout.addWidget(self.prod_total_card)
        
        self.prod_percent_card = self._create_metric_card("Процент", "0%")
        cards_layout.addWidget(self.prod_percent_card)
        
        self.prod_avg_card = self._create_metric_card("Среднее на сотрудника", "0:00")
        cards_layout.addWidget(self.prod_avg_card)
        
        self.prod_sessions_card = self._create_metric_card("Сессий", "0")
        cards_layout.addWidget(self.prod_sessions_card)
        
        layout.addLayout(cards_layout)
        
        # Таблица топ сотрудников
        top_label = QLabel("Топ-10 сотрудников по продуктивности:")
        top_label.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(top_label)
        
        self.productivity_table = QTableWidget()
        self.productivity_table.setColumnCount(5)
        self.productivity_table.setHorizontalHeaderLabels([
            "Сотрудник", "Группа", "Продуктивное время", "Процент", "Сессий"
        ])
        self.productivity_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.productivity_table.setAlternatingRowColors(True)
        layout.addWidget(self.productivity_table)
        
        return widget
    
    def _build_violations_report(self) -> QWidget:
        """Создаёт отчет по нарушениям"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Сводные карточки
        cards_layout = QHBoxLayout()
        
        self.viol_total_card = self._create_metric_card("Всего нарушений", "0")
        cards_layout.addWidget(self.viol_total_card)
        
        self.viol_out_window_card = self._create_metric_card("Вне окна", "0")
        cards_layout.addWidget(self.viol_out_window_card)
        
        self.viol_over_limit_card = self._create_metric_card("Превышение лимита", "0")
        cards_layout.addWidget(self.viol_over_limit_card)
        
        self.viol_quota_card = self._create_metric_card("Превышение квоты", "0")
        cards_layout.addWidget(self.viol_quota_card)
        
        layout.addLayout(cards_layout)
        
        # Таблица топ нарушителей
        top_label = QLabel("Топ-10 нарушителей:")
        top_label.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(top_label)
        
        self.violations_table = QTableWidget()
        self.violations_table.setColumnCount(5)
        self.violations_table.setHorizontalHeaderLabels([
            "Сотрудник", "Группа", "Всего нарушений", "Типы нарушений", "Детали"
        ])
        self.violations_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.violations_table.setAlternatingRowColors(True)
        layout.addWidget(self.violations_table)
        
        return widget
    
    def _build_breaks_report(self) -> QWidget:
        """Создаёт отчет по перерывам"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Сводные карточки
        cards_layout = QHBoxLayout()
        
        self.brk_total_card = self._create_metric_card("Всего перерывов", "0")
        cards_layout.addWidget(self.brk_total_card)
        
        self.brk_time_card = self._create_metric_card("Время в перерывах", "0:00")
        cards_layout.addWidget(self.brk_time_card)
        
        self.brk_avg_card = self._create_metric_card("Средняя длительность", "0:00")
        cards_layout.addWidget(self.brk_avg_card)
        
        self.brk_in_schedule_card = self._create_metric_card("В рамках графика", "0%")
        cards_layout.addWidget(self.brk_in_schedule_card)
        
        layout.addLayout(cards_layout)
        
        # Таблица
        self.breaks_table = QTableWidget()
        self.breaks_table.setColumnCount(6)
        self.breaks_table.setHorizontalHeaderLabels([
            "Сотрудник", "Группа", "Перерывов", "Время", "В рамках графика", "Детали"
        ])
        self.breaks_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.breaks_table.setAlternatingRowColors(True)
        layout.addWidget(self.breaks_table)
        
        return widget
    
    def _build_actions(self) -> QGroupBox:
        """Создаёт панель действий"""
        group = QGroupBox("Действия")
        layout = QHBoxLayout()
        
        btn_refresh = QPushButton("🔄 Обновить")
        btn_refresh.clicked.connect(self._apply_filters)
        layout.addWidget(btn_refresh)
        
        btn_export_excel = QPushButton("📥 Экспорт в Excel")
        btn_export_excel.clicked.connect(self._export_to_excel)
        layout.addWidget(btn_export_excel)
        
        btn_export_pdf = QPushButton("📄 Экспорт в PDF")
        btn_export_pdf.clicked.connect(self._export_to_pdf)
        layout.addWidget(btn_export_pdf)
        
        layout.addStretch()
        
        group.setLayout(layout)
        return group
    
    def _create_metric_card(self, title: str, value: str) -> QGroupBox:
        """Создаёт карточку с метрикой"""
        card = QGroupBox(title)
        card_layout = QVBoxLayout()
        
        value_label = QLabel(value)
        value_font = QFont()
        value_font.setPointSize(20)
        value_font.setBold(True)
        value_label.setFont(value_font)
        value_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(value_label)
        
        card.setLayout(card_layout)
        card.setMinimumHeight(80)
        return card
    
    def _load_initial_data(self):
        """Загружает начальные данные (списки сотрудников и групп)"""
        try:
            # Загружаем сотрудников
            users = self.repo.list_users()
            for user in users:
                email = user.get("Email", "")
                name = user.get("Name", "")
                if email:
                    display_text = f"{name} ({email})" if name else email
                    self.users_combo.addItem(display_text)
            
            # Загружаем группы
            groups = self.repo.list_groups_from_sheet()
            for group in groups:
                if group:
                    self.groups_combo.addItem(group)
        except Exception as e:
            logger.error(f"Failed to load initial data: {e}")
    
    def _set_period_today(self):
        """Устанавливает период на сегодня"""
        today = QDate.currentDate()
        self.date_from.setDate(today)
        self.date_to.setDate(today)
    
    def _set_period_week(self):
        """Устанавливает период на последние 7 дней"""
        today = QDate.currentDate()
        self.date_from.setDate(today.addDays(-7))
        self.date_to.setDate(today)
    
    def _set_period_month(self):
        """Устанавливает период на текущий месяц"""
        today = QDate.currentDate()
        self.date_from.setDate(QDate(today.year(), today.month(), 1))
        self.date_to.setDate(today)
    
    def _apply_filters(self):
        """Применяет фильтры и обновляет все отчеты"""
        try:
            date_from = self.date_from.date().toPyDate().isoformat()
            date_to = self.date_to.date().toPyDate().isoformat()
            
            selected_user = self.users_combo.currentText()
            selected_group = self.groups_combo.currentText()
            
            # Обновляем все отчеты
            self._update_employees_report(date_from, date_to, selected_user, selected_group)
            self._update_groups_report(date_from, date_to, selected_group)
            self._update_statuses_report(date_from, date_to, selected_user, selected_group)
            self._update_productivity_report(date_from, date_to, selected_user, selected_group)
            self._update_violations_report(date_from, date_to, selected_user, selected_group)
            self._update_breaks_report(date_from, date_to, selected_user, selected_group)
            
        except Exception as e:
            logger.error(f"Failed to apply filters: {e}")
            QMessageBox.warning(self, "Ошибка", f"Не удалось применить фильтры: {e}")
    
    def _update_employees_report(self, date_from: str, date_to: str, user_filter: str, group_filter: str):
        """Обновляет отчет по сотрудникам"""
        try:
            # Получаем данные из work_log
            work_log_data = self.repo.get_work_log_data(
                date_from=date_from,
                date_to=date_to,
                email=user_filter if user_filter and user_filter != "Все сотрудники" else None,
                group=group_filter if group_filter and group_filter != "Все группы" else None
            )
            
            # Получаем данные о нарушениях
            violations = self.break_mgr.get_violations_report(
                date_from=date_from,
                date_to=date_to
            )
            
            # Группируем данные по сотрудникам
            employees_data = {}
            users = self.repo.list_users()
            users_dict = {u.get("Email", "").lower(): u for u in users}
            
            for log_entry in work_log_data:
                email = log_entry.get('email', '').lower()
                if not email:
                    continue
                
                if email not in employees_data:
                    user = users_dict.get(email, {})
                    employees_data[email] = {
                        'email': email,
                        'name': user.get('Name', ''),
                        'group': user.get('Group', ''),
                        'sessions': set(),
                        'statuses': {},
                        'total_seconds': 0,
                        'productive_seconds': 0
                    }
                
                # Подсчитываем сессии
                session_id = log_entry.get('session_id', '')
                if session_id:
                    employees_data[email]['sessions'].add(session_id)
                
                # Подсчитываем время по статусам
                status = log_entry.get('status', '')
                if status:
                    if status not in employees_data[email]['statuses']:
                        employees_data[email]['statuses'][status] = 0
                    # Предполагаем, что каждая запись = 1 минута (нужно будет уточнить)
                    employees_data[email]['statuses'][status] += 60
                    employees_data[email]['total_seconds'] += 60
                    
                    # Продуктивные статусы
                    if status in ['В работе', 'На задаче']:
                        employees_data[email]['productive_seconds'] += 60
            
            # Подсчитываем нарушения для каждого сотрудника
            violations_by_email = {}
            for v in violations:
                email = v.get('Email', '').lower()
                if email:
                    violations_by_email[email] = violations_by_email.get(email, 0) + 1
            
            # Заполняем таблицу
            self.employees_table.setRowCount(len(employees_data))
            total_time = 0
            total_productive = 0
            total_sessions = 0
            
            for row, (email, data) in enumerate(sorted(employees_data.items())):
                total_hours = data['total_seconds'] // 3600
                total_mins = (data['total_seconds'] % 3600) // 60
                total_time_str = f"{total_hours}:{total_mins:02d}"
                
                productive_hours = data['productive_seconds'] // 3600
                productive_mins = (data['productive_seconds'] % 3600) // 60
                productive_time_str = f"{productive_hours}:{productive_mins:02d}"
                
                productivity_percent = (data['productive_seconds'] / data['total_seconds'] * 100) if data['total_seconds'] > 0 else 0
                sessions_count = len(data['sessions'])
                violations_count = violations_by_email.get(email, 0)
                
                total_time += data['total_seconds']
                total_productive += data['productive_seconds']
                total_sessions += sessions_count
                
                display_name = f"{data['name']} ({email})" if data['name'] else email
                
                self.employees_table.setItem(row, 0, QTableWidgetItem(display_name))
                self.employees_table.setItem(row, 1, QTableWidgetItem(data['group']))
                self.employees_table.setItem(row, 2, QTableWidgetItem(total_time_str))
                self.employees_table.setItem(row, 3, QTableWidgetItem(productive_time_str))
                self.employees_table.setItem(row, 4, QTableWidgetItem(f"{productivity_percent:.1f}%"))
                self.employees_table.setItem(row, 5, QTableWidgetItem(str(sessions_count)))
                self.employees_table.setItem(row, 6, QTableWidgetItem(str(violations_count)))
                
                details_btn = QPushButton("Детали")
                details_btn.clicked.connect(lambda checked, e=email: self._show_employee_details(e, date_from, date_to))
                self.employees_table.setCellWidget(row, 7, details_btn)
            
            # Обновляем карточки
            total_hours = total_time // 3600
            total_mins = (total_time % 3600) // 60
            self.emp_total_time_card.findChild(QLabel).setText(f"{total_hours}:{total_mins:02d}")
            
            prod_hours = total_productive // 3600
            prod_mins = (total_productive % 3600) // 60
            self.emp_productive_card.findChild(QLabel).setText(f"{prod_hours}:{prod_mins:02d}")
            
            avg_productivity = (total_productive / total_time * 100) if total_time > 0 else 0
            self.emp_productivity_card.findChild(QLabel).setText(f"{avg_productivity:.1f}%")
            
            self.emp_sessions_card.findChild(QLabel).setText(str(total_sessions))
            
        except Exception as e:
            logger.error(f"Failed to update employees report: {e}", exc_info=True)
            QMessageBox.warning(self, "Ошибка", f"Не удалось обновить отчет по сотрудникам: {e}")
    
    def _update_groups_report(self, date_from: str, date_to: str, group_filter: str):
        """Обновляет отчет по группам"""
        try:
            # Получаем данные из work_log
            work_log_data = self.repo.get_work_log_data(
                date_from=date_from,
                date_to=date_to,
                group=group_filter if group_filter and group_filter != "Все группы" else None
            )
            
            # Получаем данные о нарушениях
            violations = self.break_mgr.get_violations_report(
                date_from=date_from,
                date_to=date_to
            )
            
            # Группируем данные по группам
            groups_data = {}
            users = self.repo.list_users()
            users_dict = {u.get("Email", "").lower(): u for u in users}
            
            for log_entry in work_log_data:
                email = log_entry.get('email', '').lower()
                user = users_dict.get(email, {})
                group = user.get('Group', 'Без группы')
                
                if group not in groups_data:
                    groups_data[group] = {
                        'group': group,
                        'employees': set(),
                        'total_seconds': 0,
                        'productive_seconds': 0,
                        'sessions': set()
                    }
                
                groups_data[group]['employees'].add(email)
                session_id = log_entry.get('session_id', '')
                if session_id:
                    groups_data[group]['sessions'].add(session_id)
                
                status = log_entry.get('status', '')
                if status:
                    groups_data[group]['total_seconds'] += 60
                    if status in ['В работе', 'На задаче']:
                        groups_data[group]['productive_seconds'] += 60
            
            # Подсчитываем нарушения по группам
            violations_by_group = {}
            for v in violations:
                email = v.get('Email', '').lower()
                user = users_dict.get(email, {})
                group = user.get('Group', 'Без группы')
                violations_by_group[group] = violations_by_group.get(group, 0) + 1
            
            # Заполняем таблицу
            self.groups_table.setRowCount(len(groups_data))
            total_time = 0
            total_productive = 0
            
            for row, (group_name, data) in enumerate(sorted(groups_data.items())):
                employees_count = len(data['employees'])
                total_hours = data['total_seconds'] // 3600
                total_mins = (data['total_seconds'] % 3600) // 60
                total_time_str = f"{total_hours}:{total_mins:02d}"
                
                avg_seconds = data['total_seconds'] // employees_count if employees_count > 0 else 0
                avg_hours = avg_seconds // 3600
                avg_mins = (avg_seconds % 3600) // 60
                avg_time_str = f"{avg_hours}:{avg_mins:02d}"
                
                productivity_percent = (data['productive_seconds'] / data['total_seconds'] * 100) if data['total_seconds'] > 0 else 0
                violations_count = violations_by_group.get(group_name, 0)
                
                total_time += data['total_seconds']
                total_productive += data['productive_seconds']
                
                self.groups_table.setItem(row, 0, QTableWidgetItem(group_name))
                self.groups_table.setItem(row, 1, QTableWidgetItem(str(employees_count)))
                self.groups_table.setItem(row, 2, QTableWidgetItem(total_time_str))
                self.groups_table.setItem(row, 3, QTableWidgetItem(avg_time_str))
                self.groups_table.setItem(row, 4, QTableWidgetItem(f"{productivity_percent:.1f}%"))
                self.groups_table.setItem(row, 5, QTableWidgetItem(str(violations_count)))
                
                details_btn = QPushButton("Детали")
                details_btn.clicked.connect(lambda checked, g=group_name: self._show_group_details(g, date_from, date_to))
                self.groups_table.setCellWidget(row, 6, details_btn)
            
            # Обновляем карточки
            total_hours = total_time // 3600
            total_mins = (total_time % 3600) // 60
            self.grp_total_time_card.findChild(QLabel).setText(f"{total_hours}:{total_mins:02d}")
            
            avg_total = total_time // len(groups_data) if groups_data else 0
            avg_hours = avg_total // 3600
            avg_mins = (avg_total % 3600) // 60
            self.grp_avg_time_card.findChild(QLabel).setText(f"{avg_hours}:{avg_mins:02d}")
            
            avg_productivity = (total_productive / total_time * 100) if total_time > 0 else 0
            self.grp_productivity_card.findChild(QLabel).setText(f"{avg_productivity:.1f}%")
            
            total_violations = sum(violations_by_group.values())
            self.grp_violations_card.findChild(QLabel).setText(str(total_violations))
            
        except Exception as e:
            logger.error(f"Failed to update groups report: {e}", exc_info=True)
            QMessageBox.warning(self, "Ошибка", f"Не удалось обновить отчет по группам: {e}")
    
    def _update_statuses_report(self, date_from: str, date_to: str, user_filter: str, group_filter: str):
        """Обновляет отчет по типам статусов"""
        try:
            # Получаем данные из work_log
            work_log_data = self.repo.get_work_log_data(
                date_from=date_from,
                date_to=date_to,
                email=user_filter if user_filter and user_filter != "Все сотрудники" else None,
                group=group_filter if group_filter and group_filter != "Все группы" else None
            )
            
            # Группируем по статусам
            statuses_data = {}
            total_seconds = 0
            
            for log_entry in work_log_data:
                status = log_entry.get('status', '')
                if not status:
                    continue
                
                if status not in statuses_data:
                    statuses_data[status] = {
                        'status': status,
                        'seconds': 0,
                        'transitions': 0,
                        'employees': set()
                    }
                
                statuses_data[status]['seconds'] += 60  # Предполагаем 1 минута на запись
                statuses_data[status]['transitions'] += 1
                statuses_data[status]['employees'].add(log_entry.get('email', ''))
                total_seconds += 60
            
            # Заполняем таблицу
            self.statuses_table.setRowCount(len(statuses_data))
            
            for row, (status, data) in enumerate(sorted(statuses_data.items(), key=lambda x: x[1]['seconds'], reverse=True)):
                hours = data['seconds'] // 3600
                mins = (data['seconds'] % 3600) // 60
                time_str = f"{hours}:{mins:02d}"
                
                percent = (data['seconds'] / total_seconds * 100) if total_seconds > 0 else 0
                
                avg_duration = data['seconds'] / data['transitions'] if data['transitions'] > 0 else 0
                avg_mins = int(avg_duration // 60)
                avg_duration_str = f"{avg_mins} мин"
                
                employees_count = len(data['employees'])
                
                self.statuses_table.setItem(row, 0, QTableWidgetItem(status))
                self.statuses_table.setItem(row, 1, QTableWidgetItem(time_str))
                self.statuses_table.setItem(row, 2, QTableWidgetItem(f"{percent:.1f}%"))
                self.statuses_table.setItem(row, 3, QTableWidgetItem(str(data['transitions'])))
                self.statuses_table.setItem(row, 4, QTableWidgetItem(avg_duration_str))
                self.statuses_table.setItem(row, 5, QTableWidgetItem(str(employees_count)))
            
        except Exception as e:
            logger.error(f"Failed to update statuses report: {e}", exc_info=True)
            QMessageBox.warning(self, "Ошибка", f"Не удалось обновить отчет по статусам: {e}")
    
    def _update_productivity_report(self, date_from: str, date_to: str, user_filter: str, group_filter: str):
        """Обновляет отчет по продуктивным статусам"""
        try:
            # Получаем данные из work_log
            work_log_data = self.repo.get_work_log_data(
                date_from=date_from,
                date_to=date_to,
                email=user_filter if user_filter and user_filter != "Все сотрудники" else None,
                group=group_filter if group_filter and group_filter != "Все группы" else None
            )
            
            # Группируем по сотрудникам, считаем только продуктивные статусы
            employees_data = {}
            users = self.repo.list_users()
            users_dict = {u.get("Email", "").lower(): u for u in users}
            
            productive_statuses = ['В работе', 'На задаче']
            total_seconds = 0
            productive_seconds = 0
            
            for log_entry in work_log_data:
                email = log_entry.get('email', '').lower()
                status = log_entry.get('status', '')
                
                if not email or not status:
                    continue
                
                if email not in employees_data:
                    user = users_dict.get(email, {})
                    employees_data[email] = {
                        'email': email,
                        'name': user.get('Name', ''),
                        'group': user.get('Group', ''),
                        'productive_seconds': 0,
                        'total_seconds': 0,
                        'sessions': set()
                    }
                
                session_id = log_entry.get('session_id', '')
                if session_id:
                    employees_data[email]['sessions'].add(session_id)
                
                employees_data[email]['total_seconds'] += 60
                total_seconds += 60
                
                if status in productive_statuses:
                    employees_data[email]['productive_seconds'] += 60
                    productive_seconds += 60
            
            # Сортируем по продуктивному времени
            sorted_employees = sorted(
                employees_data.items(),
                key=lambda x: x[1]['productive_seconds'],
                reverse=True
            )[:10]
            
            # Заполняем таблицу
            self.productivity_table.setRowCount(len(sorted_employees))
            
            for row, (email, data) in enumerate(sorted_employees):
                prod_hours = data['productive_seconds'] // 3600
                prod_mins = (data['productive_seconds'] % 3600) // 60
                prod_time_str = f"{prod_hours}:{prod_mins:02d}"
                
                productivity_percent = (data['productive_seconds'] / data['total_seconds'] * 100) if data['total_seconds'] > 0 else 0
                sessions_count = len(data['sessions'])
                
                display_name = f"{data['name']} ({email})" if data['name'] else email
                
                self.productivity_table.setItem(row, 0, QTableWidgetItem(display_name))
                self.productivity_table.setItem(row, 1, QTableWidgetItem(data['group']))
                self.productivity_table.setItem(row, 2, QTableWidgetItem(prod_time_str))
                self.productivity_table.setItem(row, 3, QTableWidgetItem(f"{productivity_percent:.1f}%"))
                self.productivity_table.setItem(row, 4, QTableWidgetItem(str(sessions_count)))
            
            # Обновляем карточки
            prod_hours = productive_seconds // 3600
            prod_mins = (productive_seconds % 3600) // 60
            self.prod_total_card.findChild(QLabel).setText(f"{prod_hours}:{prod_mins:02d}")
            
            productivity_percent = (productive_seconds / total_seconds * 100) if total_seconds > 0 else 0
            self.prod_percent_card.findChild(QLabel).setText(f"{productivity_percent:.1f}%")
            
            avg_productive = productive_seconds // len(employees_data) if employees_data else 0
            avg_hours = avg_productive // 3600
            avg_mins = (avg_productive % 3600) // 60
            self.prod_avg_card.findChild(QLabel).setText(f"{avg_hours}:{avg_mins:02d}")
            
            total_sessions = sum(len(d['sessions']) for d in employees_data.values())
            self.prod_sessions_card.findChild(QLabel).setText(str(total_sessions))
            
        except Exception as e:
            logger.error(f"Failed to update productivity report: {e}", exc_info=True)
            QMessageBox.warning(self, "Ошибка", f"Не удалось обновить отчет по продуктивности: {e}")
    
    def _update_violations_report(self, date_from: str, date_to: str, user_filter: str, group_filter: str):
        """Обновляет отчет по нарушениям"""
        try:
            violations = self.break_mgr.get_violations_report(
                date_from=date_from,
                date_to=date_to
            )
            
            # Фильтруем по пользователю, если выбран
            if user_filter and user_filter != "Все сотрудники":
                # Извлекаем email из строки вида "Имя (email@example.com)"
                email = user_filter.split("(")[-1].rstrip(")")
                violations = [v for v in violations if v.get("Email", "").lower() == email.lower()]
            
            # Подсчитываем статистику
            total = len(violations)
            out_of_window = len([v for v in violations if v.get("ViolationType") == "OUT_OF_WINDOW"])
            over_limit = len([v for v in violations if v.get("ViolationType") == "OVER_LIMIT"])
            quota_exceeded = len([v for v in violations if v.get("ViolationType") == "QUOTA_EXCEEDED"])
            
            # Обновляем карточки
            self.viol_total_card.findChild(QLabel).setText(str(total))
            self.viol_out_window_card.findChild(QLabel).setText(str(out_of_window))
            self.viol_over_limit_card.findChild(QLabel).setText(str(over_limit))
            self.viol_quota_card.findChild(QLabel).setText(str(quota_exceeded))
            
            # Группируем по сотрудникам
            violators = {}
            for v in violations:
                email = v.get("Email", "")
                if email not in violators:
                    violators[email] = {
                        "email": email,
                        "count": 0,
                        "types": {}
                    }
                violators[email]["count"] += 1
                v_type = v.get("ViolationType", "")
                violators[email]["types"][v_type] = violators[email]["types"].get(v_type, 0) + 1
            
            # Сортируем по количеству нарушений
            sorted_violators = sorted(violators.items(), key=lambda x: x[1]["count"], reverse=True)[:10]
            
            # Заполняем таблицу
            self.violations_table.setRowCount(len(sorted_violators))
            for row, (email, data) in enumerate(sorted_violators):
                # Получаем имя пользователя
                user = next((u for u in self.repo.list_users() if u.get("Email", "").lower() == email.lower()), None)
                name = user.get("Name", "") if user else ""
                group = user.get("Group", "") if user else ""
                
                types_str = ", ".join([f"{k}: {v}" for k, v in data["types"].items()])
                
                self.violations_table.setItem(row, 0, QTableWidgetItem(f"{name} ({email})" if name else email))
                self.violations_table.setItem(row, 1, QTableWidgetItem(group))
                self.violations_table.setItem(row, 2, QTableWidgetItem(str(data["count"])))
                self.violations_table.setItem(row, 3, QTableWidgetItem(types_str))
                
                details_btn = QPushButton("Детали")
                details_btn.clicked.connect(lambda checked, e=email: self._show_violations_details(e, date_from, date_to))
                self.violations_table.setCellWidget(row, 4, details_btn)
            
        except Exception as e:
            logger.error(f"Failed to update violations report: {e}")
            QMessageBox.warning(self, "Ошибка", f"Не удалось обновить отчет по нарушениям: {e}")
    
    def _update_breaks_report(self, date_from: str, date_to: str, user_filter: str, group_filter: str):
        """Обновляет отчет по перерывам"""
        try:
            # Получаем данные из break_log
            break_log_data = self.repo.get_break_log_data(
                date_from=date_from,
                date_to=date_to,
                email=user_filter if user_filter and user_filter != "Все сотрудники" else None,
                group=group_filter if group_filter and group_filter != "Все группы" else None
            )
            
            # Группируем по сотрудникам
            employees_data = {}
            users = self.repo.list_users()
            users_dict = {u.get("Email", "").lower(): u for u in users}
            
            total_breaks = 0
            total_break_seconds = 0
            
            for break_entry in break_log_data:
                email = break_entry.get('email', '').lower()
                if not email:
                    continue
                
                if email not in employees_data:
                    user = users_dict.get(email, {})
                    employees_data[email] = {
                        'email': email,
                        'name': user.get('Name', ''),
                        'group': user.get('Group', ''),
                        'breaks_count': 0,
                        'break_seconds': 0
                    }
                
                employees_data[email]['breaks_count'] += 1
                total_breaks += 1
                
                # Подсчитываем время перерыва
                duration = break_entry.get('duration_minutes', 0)
                if duration:
                    employees_data[email]['break_seconds'] += duration * 60
                    total_break_seconds += duration * 60
            
            # Заполняем таблицу
            self.breaks_table.setRowCount(len(employees_data))
            
            for row, (email, data) in enumerate(sorted(employees_data.items(), key=lambda x: x[1]['breaks_count'], reverse=True)):
                break_hours = data['break_seconds'] // 3600
                break_mins = (data['break_seconds'] % 3600) // 60
                break_time_str = f"{break_hours}:{break_mins:02d}"
                
                avg_break_seconds = data['break_seconds'] // data['breaks_count'] if data['breaks_count'] > 0 else 0
                avg_mins = avg_break_seconds // 60
                avg_time_str = f"{avg_mins} мин"
                
                display_name = f"{data['name']} ({email})" if data['name'] else email
                
                self.breaks_table.setItem(row, 0, QTableWidgetItem(display_name))
                self.breaks_table.setItem(row, 1, QTableWidgetItem(data['group']))
                self.breaks_table.setItem(row, 2, QTableWidgetItem(str(data['breaks_count'])))
                self.breaks_table.setItem(row, 3, QTableWidgetItem(break_time_str))
                self.breaks_table.setItem(row, 4, QTableWidgetItem("N/A"))  # В рамках графика - TODO
                
                details_btn = QPushButton("Детали")
                details_btn.clicked.connect(lambda checked, e=email: self._show_breaks_details(e, date_from, date_to))
                self.breaks_table.setCellWidget(row, 5, details_btn)
            
            # Обновляем карточки
            self.brk_total_card.findChild(QLabel).setText(str(total_breaks))
            
            total_hours = total_break_seconds // 3600
            total_mins = (total_break_seconds % 3600) // 60
            self.brk_time_card.findChild(QLabel).setText(f"{total_hours}:{total_mins:02d}")
            
            avg_break_seconds = total_break_seconds // total_breaks if total_breaks > 0 else 0
            avg_mins = avg_break_seconds // 60
            self.brk_avg_card.findChild(QLabel).setText(f"{avg_mins} мин")
            
            self.brk_in_schedule_card.findChild(QLabel).setText("N/A")  # TODO
            
        except Exception as e:
            logger.error(f"Failed to update breaks report: {e}", exc_info=True)
            QMessageBox.warning(self, "Ошибка", f"Не удалось обновить отчет по перерывам: {e}")
    
    def _show_violations_details(self, email: str, date_from: str, date_to: str):
        """Показывает детали нарушений для сотрудника"""
        try:
            violations = self.break_mgr.get_violations_report(
                email=email,
                date_from=date_from,
                date_to=date_to
            )
            
            dialog = QMessageBox(self)
            dialog.setWindowTitle(f"Нарушения: {email}")
            dialog.setText(f"Найдено нарушений: {len(violations)}")
            
            details_text = "\n".join([
                f"{v.get('Timestamp', '')[:19]}: {v.get('ViolationType', '')} - {v.get('Details', '')}"
                for v in violations[:20]  # Показываем первые 20
            ])
            
            if len(violations) > 20:
                details_text += f"\n... и еще {len(violations) - 20} нарушений"
            
            dialog.setDetailedText(details_text)
            dialog.exec_()
        except Exception as e:
            logger.error(f"Failed to show violations details: {e}")
    
    def _show_employee_details(self, email: str, date_from: str, date_to: str):
        """Показывает детали работы сотрудника"""
        try:
            work_log_data = self.repo.get_work_log_data(
                email=email,
                date_from=date_from,
                date_to=date_to
            )
            
            dialog = QMessageBox(self)
            dialog.setWindowTitle(f"Детали работы: {email}")
            dialog.setText(f"Найдено записей: {len(work_log_data)}")
            
            # Группируем по статусам
            statuses = {}
            for entry in work_log_data:
                status = entry.get('status', '')
                if status:
                    statuses[status] = statuses.get(status, 0) + 1
            
            details_text = "Распределение по статусам:\n"
            for status, count in sorted(statuses.items(), key=lambda x: x[1], reverse=True):
                details_text += f"{status}: {count} записей\n"
            
            dialog.setDetailedText(details_text)
            dialog.exec_()
        except Exception as e:
            logger.error(f"Failed to show employee details: {e}")
    
    def _show_group_details(self, group: str, date_from: str, date_to: str):
        """Показывает детали работы группы"""
        try:
            work_log_data = self.repo.get_work_log_data(
                group=group,
                date_from=date_from,
                date_to=date_to
            )
            
            users = self.repo.list_users()
            group_users = [u for u in users if u.get('Group', '') == group]
            
            dialog = QMessageBox(self)
            dialog.setWindowTitle(f"Детали группы: {group}")
            dialog.setText(f"Сотрудников: {len(group_users)}, Записей: {len(work_log_data)}")
            
            details_text = f"Сотрудники в группе:\n"
            for user in group_users:
                details_text += f"- {user.get('Name', '')} ({user.get('Email', '')})\n"
            
            dialog.setDetailedText(details_text)
            dialog.exec_()
        except Exception as e:
            logger.error(f"Failed to show group details: {e}")
    
    def _show_breaks_details(self, email: str, date_from: str, date_to: str):
        """Показывает детали перерывов сотрудника"""
        try:
            break_log_data = self.repo.get_break_log_data(
                email=email,
                date_from=date_from,
                date_to=date_to
            )
            
            dialog = QMessageBox(self)
            dialog.setWindowTitle(f"Перерывы: {email}")
            dialog.setText(f"Найдено перерывов: {len(break_log_data)}")
            
            details_text = "\n".join([
                f"{entry.get('date', '')} {entry.get('break_type', '')}: {entry.get('duration_minutes', 0)} мин"
                for entry in break_log_data[:20]
            ])
            
            if len(break_log_data) > 20:
                details_text += f"\n... и еще {len(break_log_data) - 20} перерывов"
            
            dialog.setDetailedText(details_text)
            dialog.exec_()
        except Exception as e:
            logger.error(f"Failed to show breaks details: {e}")
    
    def _export_to_excel(self):
        """Экспортирует текущий отчет в Excel"""
        try:
            current_tab = self.reports_tabs.currentIndex()
            tab_name = self.reports_tabs.tabText(current_tab)
            
            filename, _ = QFileDialog.getSaveFileName(
                self,
                f"Экспорт отчета '{tab_name}'",
                f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                "Excel Files (*.xlsx)"
            )
            
            if filename:
                QMessageBox.information(self, "Экспорт", f"Экспорт в Excel будет реализован в следующей версии.\nФайл: {filename}")
        except Exception as e:
            logger.error(f"Failed to export to Excel: {e}")
            QMessageBox.warning(self, "Ошибка", f"Не удалось экспортировать: {e}")
    
    def _export_to_pdf(self):
        """Экспортирует текущий отчет в PDF"""
        try:
            current_tab = self.reports_tabs.currentIndex()
            tab_name = self.reports_tabs.tabText(current_tab)
            
            filename, _ = QFileDialog.getSaveFileName(
                self,
                f"Экспорт отчета '{tab_name}'",
                f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                "PDF Files (*.pdf)"
            )
            
            if filename:
                QMessageBox.information(self, "Экспорт", f"Экспорт в PDF будет реализован в следующей версии.\nФайл: {filename}")
        except Exception as e:
            logger.error(f"Failed to export to PDF: {e}")
            QMessageBox.warning(self, "Ошибка", f"Не удалось экспортировать: {e}")
