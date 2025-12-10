
# admin_app/main_admin.py
from __future__ import annotations

import sys
import logging
import time
from pathlib import Path
from typing import Optional, Dict, List, Tuple

# --- ensure project root is on sys.path ---
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QCheckBox, QComboBox, QMessageBox,
    QTabWidget, QGroupBox, QDialog, QToolBar, QAction
)

# --- Единое логирование для админки ---
# импортируем модуль целиком, чтобы можно было диагностировать, какой именно файл подхватился
import importlib, inspect
import logging_setup as LS
importlib.reload(LS)  # на случай старого кэша
print("Using logging_setup from:", LS.__file__)
print("setup_logging signature:", inspect.signature(LS.setup_logging))
from config import LOG_DIR

# --- Доменная логика/репозиторий ---
from admin_app.repo import AdminRepo

# --- Панель оповещений ---
from admin_app.notifications_panel import open_panel as open_notifications_panel

# --- Менеджер перерывов ---
from api_adapter import get_break_manager
from admin_app.break_analytics_tab import BreakAnalyticsTab

# Инициализация логирования до запуска GUI (совместимо и со старой сигнатурой)
try:
    logger = LS.setup_logging("wtt-admin")
except TypeError:
    # fallback, если старая версия без параметров
    logger = LS.setup_logging()

# =================== Константы UI ===================
FIELDS = ["Email", "Name", "Phone", "Role", "Telegram", "Group", "NotifyTelegram"]
ROLES = ["специалист", "старший специалист", "ведущий специалист", "руководитель группы"]

# Загрузка GROUP_MAPPING с обработкой ошибок
try:
    # статическая карта групп, если определена в config.py
    from config import GROUP_MAPPING
except Exception:
    GROUP_MAPPING = {}

# =================== Диалог редактирования пользователя ===================
from PyQt5.QtWidgets import QDialog

class UserDialog(QDialog):
    def __init__(self, parent=None, user: Optional[Dict[str, str]] = None, groups: List[str] = None):
        super().__init__(parent)
        self.setWindowTitle("Карточка сотрудника")
        self.user = user or {}
        self.groups = groups or []
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)

        self.email_input = QLineEdit(str(self.user.get("Email", "")))
        self.fio_input = QLineEdit(str(self.user.get("Name", "")))
        self.phone_input = QLineEdit(str(self.user.get("Phone", "")))
        self.tg_input = QLineEdit(str(self.user.get("Telegram", "")))

        self.role_combo = QComboBox()
        self.role_combo.addItems(ROLES)
        role_val = str(self.user.get("Role", "")).strip()
        if role_val in ROLES:
            self.role_combo.setCurrentText(role_val)

        self.group_combo = QComboBox()
        self.group_combo.addItems(self.groups)
        group_val = str(self.user.get("Group", "")).strip()
        if group_val in self.groups:
            self.group_combo.setCurrentText(group_val)

        self.tg_notify_chk = QCheckBox("Отправлять уведомления в Telegram")
        chk = str(self.user.get("NotifyTelegram", "")).strip().lower()
        self.tg_notify_chk.setChecked(chk in ("yes", "true", "1", "да"))

        layout.addWidget(QLabel("Email:"))
        layout.addWidget(self.email_input)
        layout.addWidget(QLabel("ФИО:"))
        layout.addWidget(self.fio_input)
        layout.addWidget(QLabel("Телефон:"))
        layout.addWidget(self.phone_input)
        layout.addWidget(QLabel("Telegram:"))
        layout.addWidget(self.tg_input)
        layout.addWidget(QLabel("Должность:"))
        layout.addWidget(self.role_combo)
        layout.addWidget(QLabel("Группа:"))
        layout.addWidget(self.group_combo)
        layout.addWidget(self.tg_notify_chk)

        btns = QHBoxLayout()
        btn_save = QPushButton("Сохранить")
        btn_save.clicked.connect(self.accept)
        btn_cancel = QPushButton("Отмена")
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_save)
        btns.addWidget(btn_cancel)
        layout.addLayout(btns)

    def get_user(self) -> Dict[str, str]:
        return {
            "Email": self.email_input.text().strip().lower(),
            "Name": self.fio_input.text().strip(),
            "Phone": self.phone_input.text().strip(),
            "Role": self.role_combo.currentText().strip(),
            "Telegram": self.tg_input.text().strip(),
            "Group": self.group_combo.currentText().strip(),
            "NotifyTelegram": "Yes" if self.tg_notify_chk.isChecked() else "No",
        }

# =================== Главное окно ===================

class AdminWindow(QMainWindow):
    def __init__(self, groups: List[str]):
        super().__init__()
        self.setWindowTitle("Админка WorkTimeTracker")
        self.resize(1400, 780)
        
        # Группы
        self.groups = groups

        # Репозиторий
        self.repo = AdminRepo()

        # Менеджер перерывов
        self.break_mgr = get_break_manager()

        # Кэш пользователей и активных e-mail
        self.users: List[Dict[str, str]] = []
        self._active_cache: Tuple[float, set[str]] = (0.0, set())  # (ts, {emails})
        self._active_ttl_sec = 30.0

        self._build_ui()
        self.refresh_users()
        self.load_shift_calendar()

    # ---------- UI ----------
    def _build_ui(self):
        # Создаем тулбар с кнопками
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)
        
        # Кнопка "Оповещения"
        btn_notifications = QAction("Оповещения", self)
        btn_notifications.triggered.connect(lambda: open_notifications_panel(self))
        toolbar.addAction(btn_notifications)

        self.tabs = QTabWidget(self)

        # --- Вкладка "Сотрудники" ---
        self.tab_users = QWidget()
        users_layout = QVBoxLayout(self.tab_users)

        # Фильтры
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Группа:"))
        self.group_filter_combo = QComboBox()
        self.group_filter_combo.addItem("Все группы")
        self.group_filter_combo.addItems(self.groups)
        self.group_filter_combo.currentIndexChanged.connect(self.apply_user_search)
        filter_layout.addWidget(self.group_filter_combo)

        self.only_active_chk = QCheckBox("Только залогиненные")
        self.only_active_chk.stateChanged.connect(self.apply_user_search)
        filter_layout.addWidget(self.only_active_chk)

        filter_layout.addStretch()
        users_layout.addLayout(filter_layout)

        # Поиск и кнопки
        top_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск по ФИО или email")
        self.search_input.textChanged.connect(self.apply_user_search)
        top_layout.addWidget(self.search_input)

        btn_add = QPushButton("Добавить")
        btn_add.clicked.connect(self.add_user)
        btn_edit = QPushButton("Редактировать")
        btn_edit.clicked.connect(self.edit_user)
        btn_delete = QPushButton("Удалить")
        btn_delete.clicked.connect(self.on_delete_user_clicked)
        btn_kick = QPushButton("Разлогинить")
        btn_kick.clicked.connect(self.on_force_logout_clicked)

        for b in (btn_add, btn_edit, btn_delete, btn_kick):
            top_layout.addWidget(b)
        users_layout.addLayout(top_layout)

        # Таблица пользователей
        self.users_table = QTableWidget(0, len(FIELDS))
        self.users_table.setHorizontalHeaderLabels(
            ["Email", "ФИО", "Телефон", "Должность", "Telegram", "Группа", "Telegram уведомления"]
        )
        self.users_table.setSelectionBehavior(QTableWidget.SelectRows)
        users_layout.addWidget(self.users_table)

        self.tabs.addTab(self.tab_users, "Сотрудники")

        # --- Вкладка "График" ---
        self.tab_schedule = QWidget()
        schedule_layout = QVBoxLayout(self.tab_schedule)

        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Сотрудник:"))
        self.schedule_user_combo = QComboBox()
        self.schedule_user_combo.addItem("Выберите сотрудника")
        self.schedule_user_combo.currentIndexChanged.connect(self.on_schedule_user_change)
        header_layout.addWidget(self.schedule_user_combo)
        header_layout.addStretch()
        schedule_layout.addLayout(header_layout)

        self.info_group = QGroupBox("Информация о сотруднике")
        info_layout = QVBoxLayout()
        self.login_status_lbl = QLabel("Залогинен: Нет")
        self.btn_force_logout = QPushButton("Разлогинить")
        self.btn_force_logout.setEnabled(False)
        self.btn_force_logout.clicked.connect(self.force_logout_from_schedule)
        status_row = QHBoxLayout()
        status_row.addWidget(self.login_status_lbl)
        status_row.addWidget(self.btn_force_logout)
        status_row.addStretch()
        info_layout.addLayout(status_row)

        self.info_label = QLabel("")
        self.info_label.setWordWrap(True)
        info_layout.addWidget(self.info_label)
        self.info_group.setLayout(info_layout)
        schedule_layout.addWidget(self.info_group)

        self.schedule_table = QTableWidget()
        schedule_layout.addWidget(self.schedule_table)

        self.tabs.addTab(self.tab_schedule, "График")

        # --- Вкладка "Перерывы" ---
        self.tab_breaks = QWidget()
        breaks_layout = QVBoxLayout(self.tab_breaks)

        # Подвкладки для разных разделов
        self.breaks_tabs = QTabWidget()

        # 1. Шаблоны графиков
        self.templates_tab = self._build_templates_tab()
        self.breaks_tabs.addTab(self.templates_tab, "Шаблоны")

        # 2. Назначение сотрудникам
        self.assignments_tab = self._build_assignments_tab()
        self.breaks_tabs.addTab(self.assignments_tab, "Назначения")

        # 3. Нарушения
        self.violations_tab = self._build_violations_tab()
        self.breaks_tabs.addTab(self.violations_tab, "Нарушения")
        # 4. Аналитика
        self.analytics_tab = BreakAnalyticsTab(self.break_mgr)
        self.breaks_tabs.addTab(self.analytics_tab, "📊 Аналитика")


        breaks_layout.addWidget(self.breaks_tabs)
        self.tabs.addTab(self.tab_breaks, "Перерывы")

        # --- Вкладка "Дополнительно" (плейсхолдер) ---
        self.tab_extra = QWidget()
        extra_layout = QVBoxLayout(self.tab_extra)
        extra_layout.addWidget(QLabel("Тут будет что-то ещё"))
        self.tabs.addTab(self.tab_extra, "Дополнительно")

        self.setCentralWidget(self.tabs)

    def _build_templates_tab(self) -> QWidget:
        """Вкладка шаблонов графиков"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Кнопки управления
        btn_layout = QHBoxLayout()
        btn_new = QPushButton("Создать шаблон")
        btn_new.clicked.connect(self.on_create_template)
        btn_edit = QPushButton("Редактировать")
        btn_edit.clicked.connect(self.on_edit_template)
        btn_delete = QPushButton("Удалить")
        btn_delete.clicked.connect(self.on_delete_template)
        
        btn_layout.addWidget(btn_new)
        btn_layout.addWidget(btn_edit)
        btn_layout.addWidget(btn_delete)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # Таблица шаблонов
        self.templates_table = QTableWidget(0, 4)
        self.templates_table.setHorizontalHeaderLabels(
            ["ID шаблона", "Название", "Начало смены", "Конец смены"]
        )
        self.templates_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.templates_table)
        
        self.refresh_templates()
        return widget

    def _build_assignments_tab(self) -> QWidget:
        """Вкладка назначений графиков сотрудникам"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Управление назначениями
        form_layout = QHBoxLayout()
        form_layout.addWidget(QLabel("Сотрудник:"))
        
        self.assign_user_combo = QComboBox()
        self.assign_user_combo.addItem("Выберите сотрудника")
        for u in self.users:
            fio = u.get("Name", "")
            if fio:
                self.assign_user_combo.addItem(fio)
        form_layout.addWidget(self.assign_user_combo)
        
        form_layout.addWidget(QLabel("Шаблон:"))
        self.assign_template_combo = QComboBox()
        self._refresh_template_combo()
        form_layout.addWidget(self.assign_template_combo)
        
        btn_assign = QPushButton("Назначить")
        btn_assign.clicked.connect(self.on_assign_schedule)
        form_layout.addWidget(btn_assign)
        form_layout.addStretch()
        
        layout.addLayout(form_layout)
        
        # Таблица текущих назначений
        self.assignments_table = QTableWidget(0, 4)
        self.assignments_table.setHorizontalHeaderLabels(
            ["Email", "Шаблон", "Действует с", "Назначил"]
        )
        layout.addWidget(self.assignments_table)
        
        self.refresh_assignments()
        return widget

    def _build_violations_tab(self) -> QWidget:
        """Вкладка нарушений"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Фильтры
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Сотрудник:"))
        self.violations_user_combo = QComboBox()
        self.violations_user_combo.addItem("Все")
        for u in self.users:
            email = u.get("Email", "")
            if email:
                self.violations_user_combo.addItem(email)
        filter_layout.addWidget(self.violations_user_combo)
        
        filter_layout.addWidget(QLabel("Статус:"))
        self.violations_status_combo = QComboBox()
        self.violations_status_combo.addItems(["Все", "pending", "reviewed", "resolved"])
        filter_layout.addWidget(self.violations_status_combo)
        
        btn_refresh = QPushButton("Обновить")
        btn_refresh.clicked.connect(self.refresh_violations)
        filter_layout.addWidget(btn_refresh)
        filter_layout.addStretch()
        
        layout.addLayout(filter_layout)
        
        # Таблица нарушений
        self.violations_table = QTableWidget(0, 6)
        self.violations_table.setHorizontalHeaderLabels(
            ["Время", "Email", "Тип нарушения", "Детали", "Статус", "SessionID"]
        )
        self.violations_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.violations_table)
        
        self.refresh_violations()
        return widget

    # ---------- Helpers ----------
    def _selected_email(self) -> Optional[str]:
        items = self.users_table.selectedItems()
        if not items:
            return None
        val = items[0].text().strip()
        return val[2:] if val.startswith("🟢 ") else val

    def _confirm(self, msg: str) -> bool:
        return QMessageBox.question(self, "Подтверждение", msg, QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes

    def _info(self, msg: str):
        QMessageBox.information(self, "Информация", msg)

    def _warn(self, msg: str):
        QMessageBox.warning(self, "Ошибка", msg)

    # ---------- Активные сессии (кэш) ----------
    def _get_active_emails_cached(self) -> set[str]:
        ts, emails = self._active_cache
        if time.monotonic() - ts < self._active_ttl_sec:
            return emails
        try:
            sessions = self.repo.get_active_sessions()
            emails = {str(s.get("Email", "")).strip().lower() for s in sessions if str(s.get("Status", "")).strip().lower() == "active"}
            self._active_cache = (time.monotonic(), emails)
            return emails
        except Exception as e:
            logger.warning("Не удалось получить активные сессии: %s", e)
            return set()

    # =================== Таб "Сотрудники" ===================

    def refresh_users(self):
        try:
            rows = self.repo.list_users()
        except Exception as e:
            logger.exception("refresh_users failed: %s", e)
            rows = []

        self.users = []
        for r in rows:
            nt = str(r.get("NotifyTelegram", "")).strip().lower()
            nt_norm = "Yes" if nt in ("yes", "true", "1", "да") else "No"
            self.users.append({
                "Email": str(r.get("Email", "")),
                "Name": str(r.get("Name", "")),
                "Phone": str(r.get("Phone", "")),
                "Role": str(r.get("Role", "")),
                "Telegram": str(r.get("Telegram", "")),
                "Group": str(r.get("Group", "")),
                "NotifyTelegram": nt_norm,
            })

        # заполняем таблицу
        self.refresh_users_table()

        # и выпадающий список на вкладке "График"
        self.schedule_user_combo.blockSignals(True)
        self.schedule_user_combo.clear()
        self.schedule_user_combo.addItem("Выберите сотрудника")
        for u in self.users:
            fio = u.get("Name", "")
            if fio:
                self.schedule_user_combo.addItem(fio)
        self.schedule_user_combo.blockSignals(False)

        # обновляем список сотрудников на вкладке "Назначения"
        self._refresh_assign_user_combo()

    def _refresh_assign_user_combo(self):
        """Обновляет выпадающий список сотрудников на вкладке 'Назначения'"""
        if not hasattr(self, "assign_user_combo"):
            return
        self.assign_user_combo.blockSignals(True)
        self.assign_user_combo.clear()
        self.assign_user_combo.addItem("Выберите сотрудника")
        for u in self.users:
            fio = u.get("Name", "")
            if fio:
                self.assign_user_combo.addItem(fio)
        self.assign_user_combo.blockSignals(False)

    def refresh_users_table(self, filter_text: str = ""):
        self.users_table.setRowCount(0)
        selected_group = self.group_filter_combo.currentText()
        only_active = self.only_active_chk.isChecked()
        active_emails = self._get_active_emails_cached() if only_active else set()

        for u in self.users:
            email = u.get("Email", "").strip().lower()
            group = u.get("Group", "").strip()
            is_active = email in active_emails

            # поиск
            if filter_text:
                q = filter_text.lower()
                if q not in email and q not in u.get("Name", "").lower():
                    continue
            # фильтр по группе
            if selected_group != "Все группы" and group != selected_group:
                continue
            # фильтр активности
            if only_active and not is_active:
                continue

            row = self.users_table.rowCount()
            self.users_table.insertRow(row)
            for col, key in enumerate(FIELDS):
                val = u.get(key, "")
                if key == "Email" and is_active:
                    val = f"🟢 {val}"
                item = QTableWidgetItem(str(val))
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.users_table.setItem(row, col, item)

    def apply_user_search(self):
        self.refresh_users_table(self.search_input.text())

    # --- CRUD/Actions ---

    def add_user(self):
        dlg = UserDialog(self, groups=self.groups)
        if dlg.exec_():
            data = dlg.get_user()
            if self.repo.add_or_update_user(data):
                self._info("Пользователь добавлен")
                self.refresh_users()
            else:
                self._warn("Ошибка при добавлении пользователя")

    def edit_user(self):
        row = self.users_table.currentRow()
        if row < 0 or row >= len(self.users):
            self._warn("Сначала выберите строку для редактирования.")
            return
        user = self.users[row]
        dlg = UserDialog(self, user=user, groups=self.groups)
        if dlg.exec_():
            data = dlg.get_user()
            if self.repo.add_or_update_user(data):
                self._info("Пользователь обновлён")
                self.refresh_users()
            else:
                self._warn("Ошибка при обновлении пользователя")

    def on_delete_user_clicked(self):
        email = self._selected_email()
        if not email:
            self._warn("Выберите пользователя")
            return
        if not self._confirm(f"Удалить пользователя {email}?"):
            return
        if self.repo.delete_user(email):
            self._info("Пользователь удалён")
            self.refresh_users()
        else:
            self._warn("Пользователь не найден или не удалён")

    def on_force_logout_clicked(self):
        email = self._selected_email()
        if not email:
            self._warn("Выберите пользователя из списка.")
            return
        # отображаем ФИО для красоты
        fio = ""
        sel = self.users_table.selectedItems()
        if sel and len(sel) > 1:
            fio = sel[1].text()

        if not self._confirm(f"Разлогинить {fio or email}?"):
            return

        success, error_msg = self.repo.force_logout(email=email)
        if success:
            self._info(f"Пользователь {fio or email} был разлогинен.")
            # сбрасываем кэш активностей, чтобы таблица обновилась корректно
            self._active_cache = (0.0, set())
            self.refresh_users()
        else:
            self._warn(error_msg or "Активная сессия не найдена")

    # =================== Таб "График" ===================

    def load_shift_calendar(self):
        """Подтягиваем таблицу графика. Если её нет — отключаем элементы."""
        try:
            data = self.repo.get_shift_calendar()
        except Exception as e:
            logger.exception("Ошибка при загрузке графика: %s", e)
            data = []

        self.shift_calendar_data: List[List[str]] = data
        self.shift_headers: List[str] = data[0] if data else []

        if not data:
            self.info_label.setText("Лист графика не найден или пуст.")
            self.login_status_lbl.setText("Залогинен: Нет")
            self.btn_force_logout.setEnabled(False)
            self.schedule_table.setRowCount(0)
            self.schedule_table.setColumnCount(0)
            self.schedule_user_combo.setEnabled(bool(self.users))
            return

        self.schedule_user_combo.setEnabled(True)

    def on_schedule_user_change(self):
        idx = self.schedule_user_combo.currentIndex()
        if idx <= 0 or not self.shift_calendar_data:
            self.schedule_table.setRowCount(0)
            self.schedule_table.setColumnCount(0)
            self.info_label.setText("")
            self.login_status_lbl.setText("Залогинен: Нет")
            self.btn_force_logout.setEnabled(False)
            return

        fio = self.schedule_user_combo.currentText()
        email = ""
        for u in self.users:
            if u.get("Name", "") == fio:
                email = u.get("Email", "")
                break

        # статус логина
        active = self._get_active_emails_cached()
        is_logged_in = email.strip().lower() in active
        self.login_status_lbl.setText(f"Залогинен: {'Да' if is_logged_in else 'Нет'}")
        self.btn_force_logout.setEnabled(is_logged_in)
        self.btn_force_logout.setProperty("user_email", email)
        self.btn_force_logout.setProperty("user_fio", fio)

        # инфо по сотруднику
        info_parts = [f"<b>ФИО:</b> {fio}", f"<b>Email:</b> {email}"]
        self.info_label.setText("<br>".join(info_parts))

        # табель по дням (ищем первые числовые заголовки как дни месяца)
        headers = self.shift_headers
        row_for_user: Optional[List[str]] = None
        for r in self.shift_calendar_data[1:]:
            if r and r[0].strip() == fio:
                row_for_user = r
                break

        day_indices = [(i, h) for i, h in enumerate(headers) if str(h).isdigit()]
        self.schedule_table.setRowCount(0)
        self.schedule_table.setColumnCount(len(day_indices))
        self.schedule_table.setHorizontalHeaderLabels([str(h) for _, h in day_indices])

        if row_for_user:
            self.schedule_table.setRowCount(1)
            for col, (i, _) in enumerate(day_indices):
                val = row_for_user[i] if i < len(row_for_user) else ""
                self.schedule_table.setItem(0, col, QTableWidgetItem(str(val)))
            self.schedule_table.resizeColumnsToContents()

    def force_logout_from_schedule(self):
        email = self.btn_force_logout.property("user_email")
        fio = self.btn_force_logout.property("user_fio")
        if not email:
            self._warn("Не удалось определить Email пользователя.")
            return
        if not self._confirm(f"Разлогинить {fio or email}?"):
            return

        success, error_msg = self.repo.force_logout(email=email)
        if success:
            self._info(f"Пользователь {fio or email} разлогинен.")
            self.btn_force_logout.setEnabled(False)
            self.login_status_lbl.setText("Залогинен: Нет")
            # сбрасываем кэш активностей
            self._active_cache = (0.0, set())
            self.refresh_users()
        else:
            self._warn(error_msg or "Активная сессия не найдена")

    # =================== Таб "Перерывы" ===================

    def on_create_template(self):
        """Создание нового шаблона графика"""
        from admin_app.break_schedule_dialog import BreakScheduleDialog
        
        dlg = BreakScheduleDialog(self)
        if dlg.exec_():
            template_data = dlg.get_template_data()
            if self.break_mgr.create_schedule_template(**template_data):
                self._info("Шаблон создан успешно")
                self.refresh_templates()
                # Обновляем список шаблонов в выпадающем меню назначений
                self._refresh_template_combo()
            else:
                self._warn("Ошибка при создании шаблона")

    def on_edit_template(self):
        row = self.templates_table.currentRow()
        if row < 0:
            self._warn("Выберите шаблон для редактирования")
            return
        from admin_app.break_schedule_dialog import BreakScheduleDialog
        schedule_id = self.templates_table.item(row, 0).text()

        # Получаем текущие данные шаблона
        all_templates = self.break_mgr.list_schedule_templates()
        current = None
        for t in all_templates:
            if str(t.get("schedule_id")) == str(schedule_id):
                current = t
                break

        if not current:
            self._warn(f"Не удалось найти данные шаблона {schedule_id}.")
            return

        dlg = BreakScheduleDialog(self, template_data=current)

        if dlg.exec_():
            new_data = dlg.get_template_data()
            ok = self.break_mgr.update_schedule_template(
                schedule_id=new_data.get("schedule_id"),
                name=new_data.get("name"),
                shift_start=new_data.get("shift_start"),
                shift_end=new_data.get("shift_end"),
                slots_data=new_data.get("slots_data", []),
            )

            if ok:
                self._info("✅ Шаблон успешно обновлён.")
                self.refresh_templates()
                self._refresh_template_combo()  # ДОБАВИТЬ эту строку
            else:
                self._warn("❌ Ошибка при обновлении шаблона.")

    def on_delete_template(self):
        row = self.templates_table.currentRow()
        if row < 0:
            self._warn("Выберите шаблон для удаления")
            return
        schedule_id = self.templates_table.item(row, 0).text()
        name = self.templates_table.item(row, 1).text()

        if not self._confirm(f"Удалить шаблон '{name}' (ScheduleID={schedule_id})?"):
            return

        ok = self.break_mgr.delete_schedule_template(str(schedule_id))
        if ok:
            self._info("🗑 Шаблон удалён из Google Sheets.")
            self.refresh_templates()
        else:
            self._warn("❌ Ошибка при удалении шаблона из таблицы.")

    def on_assign_schedule(self):
        """Назначает график сотруднику"""
        user_text = self.assign_user_combo.currentText()
        template_text = self.assign_template_combo.currentText()
        
        if user_text == "Выберите сотрудника" or not template_text:
            self._warn("Выберите сотрудника и шаблон")
            return
        
        # Находим email по ФИО
        email = None
        for u in self.users:
            if u.get("Name") == user_text:
                email = u.get("Email")
                break
        
        if not email:
            self._warn("Email сотрудника не найден")
            return
        
        # Извлекаем ID шаблона
        schedule_id = template_text.split(" - ")[0]
        
        if self.break_mgr.assign_schedule_to_user(email, schedule_id):
            self._info(f"График назначен для {user_text}")
            self.refresh_assignments()
        else:
            self._warn("Ошибка при назначении графика")

    def refresh_templates(self):
        """Обновляет таблицу шаблонов"""
        self.templates_table.setRowCount(0)
        templates = self.break_mgr.list_schedule_templates()
        
        for t in templates:
            row = self.templates_table.rowCount()
            self.templates_table.insertRow(row)
            self.templates_table.setItem(row, 0, QTableWidgetItem(t["schedule_id"]))
            self.templates_table.setItem(row, 1, QTableWidgetItem(t["name"]))
            self.templates_table.setItem(row, 2, QTableWidgetItem(t["shift_start"]))
            self.templates_table.setItem(row, 3, QTableWidgetItem(t["shift_end"]))

    def refresh_assignments(self):
        """Обновляет таблицу назначений"""
        from config import USER_BREAK_ASSIGNMENTS_SHEET
        self.assignments_table.setRowCount(0)
        
        try:
            ws = self.repo.sheets.get_worksheet(USER_BREAK_ASSIGNMENTS_SHEET)
            rows = self.repo.sheets._read_table(ws)
            
            for r in rows:
                row = self.assignments_table.rowCount()
                self.assignments_table.insertRow(row)
                self.assignments_table.setItem(row, 0, QTableWidgetItem(r.get("Email", "")))
                self.assignments_table.setItem(row, 1, QTableWidgetItem(r.get("ScheduleID", "")))
                self.assignments_table.setItem(row, 2, QTableWidgetItem(r.get("EffectiveDate", "")))
                self.assignments_table.setItem(row, 3, QTableWidgetItem(r.get("AssignedBy", "")))
        except Exception as e:
            logger.error(f"Failed to refresh assignments: {e}")

    def refresh_violations(self):
        """Обновляет таблицу нарушений"""
        self.violations_table.setRowCount(0)
        
        email_filter = self.violations_user_combo.currentText()
        if email_filter == "Все":
            email_filter = None
        
        status_filter = self.violations_status_combo.currentText()
        if status_filter == "Все":
            status_filter = None
        
        violations = self.break_mgr.get_violations_report(email=email_filter)
        
        for v in violations:
            if status_filter and v.get("Status") != status_filter:
                continue
            
            row = self.violations_table.rowCount()
            self.violations_table.insertRow(row)
            self.violations_table.setItem(row, 0, QTableWidgetItem(v.get("Timestamp", "")))
            self.violations_table.setItem(row, 1, QTableWidgetItem(v.get("Email", "")))
            self.violations_table.setItem(row, 2, QTableWidgetItem(v.get("ViolationType", "")))
            self.violations_table.setItem(row, 3, QTableWidgetItem(v.get("Details", "")))
            self.violations_table.setItem(row, 4, QTableWidgetItem(v.get("Status", "")))
            self.violations_table.setItem(row, 5, QTableWidgetItem(v.get("SessionID", "")))

    def _refresh_template_combo(self):
        """Обновляет выпадающий список шаблонов"""
        if not hasattr(self, "assign_template_combo"):
            return
        self.assign_template_combo.blockSignals(True)
        self.assign_template_combo.clear()
        templates = self.break_mgr.list_schedule_templates()
        for t in templates:
            self.assign_template_combo.addItem(f"{t['schedule_id']} - {t['name']}")
        self.assign_template_combo.blockSignals(False)

# =================== Вспомогательные функции ===================

def get_available_groups(repo: AdminRepo) -> list[str]:
    """Получение списка доступных групп"""
    if GROUP_MAPPING:
        return sorted(set(GROUP_MAPPING.values()))
    return repo.list_groups_from_sheet()

# =================== Entrypoint ===================

def main():
    logger.info("Launching Admin UI...")
    
    # Получение списка групп
    repo = AdminRepo()
    groups = get_available_groups(repo)
    logger.info("Groups: %s", ", ".join(groups) if groups else "<none>")
    
    # Запуск GUI с передачей списка групп
    app = QApplication(sys.argv)
    win = AdminWindow(groups)
    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()