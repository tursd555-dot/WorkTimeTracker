
# admin_app/break_schedule_dialog.py
"""
Диалог создания/редактирования шаблона графика перерывов
"""
from __future__ import annotations
import logging
import re
from datetime import datetime
from typing import Optional, Dict, List
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QComboBox,
    QTimeEdit, QSpinBox, QMessageBox, QHeaderView
)
from PyQt5.QtCore import QTime

logger = logging.getLogger(__name__)


class BreakScheduleDialog(QDialog):
    """Диалог для создания/редактирования шаблона графика перерывов"""
    
    def __init__(self, parent=None, template_data: Optional[Dict] = None):
        super().__init__(parent)
        self.template_data = template_data or {}
        self.setWindowTitle("Шаблон графика перерывов")
        self.resize(800, 600)
        self._build_ui()
        self._load_data()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        
        # Основная информация
        info_layout = QVBoxLayout()
        
        # ID шаблона
        id_row = QHBoxLayout()
        id_row.addWidget(QLabel("ID шаблона:"))
        self.schedule_id_input = QLineEdit()
        self.schedule_id_input.setPlaceholderText("Уникальный идентификатор")
        id_row.addWidget(self.schedule_id_input)
        
        # NEW: Auto-generate ID button
        btn_generate_id = QPushButton("Generate ID")
        btn_generate_id.setToolTip("Auto-generate unique ID")
        btn_generate_id.clicked.connect(self._generate_schedule_id)
        btn_generate_id.setMaximumWidth(130)
        id_row.addWidget(btn_generate_id)
        info_layout.addLayout(id_row)
        
        # Название
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Название:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Например: График 5/2 (9-18)")
        name_row.addWidget(self.name_input)
        info_layout.addLayout(name_row)
        
        # Время смены
        shift_row = QHBoxLayout()
        shift_row.addWidget(QLabel("Начало смены:"))
        self.shift_start_input = QTimeEdit()
        self.shift_start_input.setDisplayFormat("HH:mm")
        self.shift_start_input.setTime(QTime(9, 0))
        shift_row.addWidget(self.shift_start_input)
        
        shift_row.addWidget(QLabel("Конец смены:"))
        self.shift_end_input = QTimeEdit()
        self.shift_end_input.setDisplayFormat("HH:mm")
        self.shift_end_input.setTime(QTime(18, 0))
        shift_row.addWidget(self.shift_end_input)
        shift_row.addStretch()
        info_layout.addLayout(shift_row)
        
        layout.addLayout(info_layout)
        
        # Таблица слотов перерывов
        layout.addWidget(QLabel("<b>Слоты перерывов:</b>"))
        
        # Кнопки управления слотами
        slot_btns = QHBoxLayout()
        btn_add_slot = QPushButton("Добавить слот")
        btn_add_slot.clicked.connect(self._add_slot)
        btn_remove_slot = QPushButton("Удалить выбранный")
        btn_remove_slot.clicked.connect(self._remove_slot)
        slot_btns.addWidget(btn_add_slot)
        slot_btns.addWidget(btn_remove_slot)
        slot_btns.addStretch()
        layout.addLayout(slot_btns)
        
        # Таблица
        self.slots_table = QTableWidget(0, 5)
        self.slots_table.setHorizontalHeaderLabels([
            "Порядок", "Тип", "Длительность (мин)", "Окно начала", "Окно конца"
        ])
        header = self.slots_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        layout.addWidget(self.slots_table)
        
        # Кнопки диалога
        buttons = QHBoxLayout()
        btn_save = QPushButton("Сохранить")
        btn_save.clicked.connect(self._on_save)
        btn_cancel = QPushButton("Отмена")
        btn_cancel.clicked.connect(self.reject)
        buttons.addStretch()
        buttons.addWidget(btn_save)
        buttons.addWidget(btn_cancel)
        layout.addLayout(buttons)
    

    
    def _generate_schedule_id(self):
        name = self.name_input.text().strip()
        if name:
            generated_id = self._generate_id_from_name(name)
        else:
            shift_start = self.shift_start_input.time().toString("HHmm")
            shift_end = self.shift_end_input.time().toString("HHmm")
            generated_id = f"SHIFT_{shift_start}_{shift_end}"
        self.schedule_id_input.setText(generated_id)
        self.schedule_id_input.setFocus()
        self.schedule_id_input.selectAll()
    
    def _generate_id_from_name(self, name: str) -> str:
        translit_map = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
            'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
            'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
            'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
            'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
        }
        result = []
        for char in name.lower():
            if char in translit_map:
                result.append(translit_map[char])
            elif char.isalnum():
                result.append(char)
            elif char in (' ', '-', '/', '(', ')'):
                result.append('_')
        generated = ''.join(result)
        generated = re.sub(r'_+', '_', generated)
        generated = generated.strip('_').upper()
        if len(generated) > 30:
            generated = generated[:30]
        return generated or "SCHEDULE"

    def _load_data(self):
        """Загружает данные для редактирования"""
        if not self.template_data:
            return
        
        self.schedule_id_input.setText(str(self.template_data.get("schedule_id", "")))
        self.name_input.setText(str(self.template_data.get("name", "")))
        
        # Время смены
        shift_start = self.template_data.get("shift_start", "09:00")
        shift_end = self.template_data.get("shift_end", "18:00")
        
        try:
            h, m = map(int, shift_start.split(":"))
            self.shift_start_input.setTime(QTime(h, m))
        except:
            pass
        
        try:
            h, m = map(int, shift_end.split(":"))
            self.shift_end_input.setTime(QTime(h, m))
        except:
            pass
        
        # Слоты
        slots = self.template_data.get("slots_data", [])
        for slot in slots:
            self._add_slot_row(
                order=slot.get("order", ""),
                slot_type=slot.get("type", "Перерыв"),
                duration=slot.get("duration", "15"),
                window_start=slot.get("window_start", "11:00"),
                window_end=slot.get("window_end", "12:00")
            )
    
    def _add_slot(self):
        """Добавляет новый слот"""
        order = self.slots_table.rowCount() + 1
        self._add_slot_row(order=str(order))
    
    def _add_slot_row(self, order="1", slot_type="Перерыв", duration="15", 
                      window_start="11:00", window_end="12:00"):
        """Добавляет строку в таблицу слотов"""
        row = self.slots_table.rowCount()
        self.slots_table.insertRow(row)
        
        # Порядок
        order_spin = QSpinBox()
        order_spin.setMinimum(1)
        order_spin.setMaximum(99)
        order_spin.setValue(int(order) if str(order).isdigit() else 1)
        self.slots_table.setCellWidget(row, 0, order_spin)
        
        # Тип
        type_combo = QComboBox()
        type_combo.addItems(["Перерыв", "Обед"])
        type_combo.setCurrentText(slot_type)
        self.slots_table.setCellWidget(row, 1, type_combo)
        
        # Длительность
        duration_spin = QSpinBox()
        duration_spin.setMinimum(5)
        duration_spin.setMaximum(120)
        duration_spin.setSuffix(" мин")
        duration_spin.setValue(int(duration) if str(duration).isdigit() else 15)
        self.slots_table.setCellWidget(row, 2, duration_spin)
        
        # Окно начала
        start_time = QTimeEdit()
        start_time.setDisplayFormat("HH:mm")
        try:
            h, m = map(int, window_start.split(":"))
            start_time.setTime(QTime(h, m))
        except:
            start_time.setTime(QTime(11, 0))
        self.slots_table.setCellWidget(row, 3, start_time)
        
        # Окно конца
        end_time = QTimeEdit()
        end_time.setDisplayFormat("HH:mm")
        try:
            h, m = map(int, window_end.split(":"))
            end_time.setTime(QTime(h, m))
        except:
            end_time.setTime(QTime(12, 0))
        self.slots_table.setCellWidget(row, 4, end_time)
    
    def _remove_slot(self):
        """Удаляет выбранный слот"""
        current_row = self.slots_table.currentRow()
        if current_row >= 0:
            self.slots_table.removeRow(current_row)
    
    def _validate(self) -> tuple[bool, str]:
        """Валидация данных"""
        if not self.schedule_id_input.text().strip():
            return False, "Укажите ID шаблона"
        
        if not self.name_input.text().strip():
            return False, "Укажите название шаблона"
        
        if self.slots_table.rowCount() == 0:
            return False, "Добавьте хотя бы один слот перерыва"
        
        return True, ""
    
    def _on_save(self):
        """Обработка сохранения"""
        valid, msg = self._validate()
        if not valid:
            QMessageBox.warning(self, "Ошибка валидации", msg)
            return
        
        self.accept()
    
    def get_template_data(self) -> Dict:
        """Возвращает данные шаблона"""
        slots_data = []
        
        for row in range(self.slots_table.rowCount()):
            order_widget = self.slots_table.cellWidget(row, 0)
            type_widget = self.slots_table.cellWidget(row, 1)
            duration_widget = self.slots_table.cellWidget(row, 2)
            start_widget = self.slots_table.cellWidget(row, 3)
            end_widget = self.slots_table.cellWidget(row, 4)
            
            slots_data.append({
                "order": str(order_widget.value()),
                "type": type_widget.currentText(),
                "duration": str(duration_widget.value()),
                "window_start": start_widget.time().toString("HH:mm"),
                "window_end": end_widget.time().toString("HH:mm")
            })
        
        return {
            "schedule_id": self.schedule_id_input.text().strip(),
            "name": self.name_input.text().strip(),
            "shift_start": self.shift_start_input.time().toString("HH:mm"),
            "shift_end": self.shift_end_input.time().toString("HH:mm"),
            "slots_data": slots_data
        }