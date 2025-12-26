# admin_app/break_manager.py
"""
Менеджер системы перерывов v2.0

КЛЮЧЕВЫЕ ИЗМЕНЕНИЯ:
- Убраны слоты (slot_order) - теперь общие лимиты
- Отдельные временные окна для каждого типа перерыва
- Градация нарушений (INFO, WARNING, CRITICAL)
- Интеграция с Telegram уведомлениями
- Простая логика: взял перерыв когда хочешь, главное не превысить лимит

НОВАЯ ЛОГИКА:
- Лимиты: 3 перерыва по 15 мин, 1 обед по 60 мин (настраивается)
- Временные окна: рекомендуемые, НЕ обязательные
- Нарушения:
  * OUT_OF_WINDOW - вне окна (INFO, только логируем)
  * OVER_LIMIT - превышен лимит времени (CRITICAL, уведомление)
  * QUOTA_EXCEEDED - превышено количество (CRITICAL, уведомление)
"""
from __future__ import annotations
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, time, date
from dataclasses import dataclass
import sys
from pathlib import Path

# Добавляем путь к shared модулям
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from shared.time_utils import format_time_moscow, to_moscow

logger = logging.getLogger(__name__)


def parse_time(time_str: str, default: str = "09:00") -> time:
    """
    Парсит строку времени, поддерживая форматы HH:MM и HH:MM:SS
    
    Args:
        time_str: Строка времени (например, "09:00" или "09:00:00")
        default: Значение по умолчанию, если парсинг не удался
    
    Returns:
        time объект
    """
    if not time_str:
        time_str = default
    
    # Пробуем разные форматы
    for fmt in ["%H:%M:%S", "%H:%M"]:
        try:
            return datetime.strptime(time_str, fmt).time()
        except ValueError:
            continue
    
    # Если ничего не подошло, используем значение по умолчанию
    try:
        return datetime.strptime(default, "%H:%M").time()
    except:
        return time(9, 0)  # Fallback


@dataclass
class BreakLimit:
    """Лимит на перерывы/обеды"""
    break_type: str      # "Перерыв" или "Обед"
    daily_count: int     # Количество в день (например, 3)
    time_minutes: int    # Лимит времени каждого (например, 15)


@dataclass
class BreakWindow:
    """Временное окно для перерыва"""
    break_type: str
    start_time: time
    end_time: time
    priority: int = 1    # Приоритет (1 - основное, 2 - альтернативное)
    
    def is_within(self, check_time: time) -> bool:
        """Проверяет попадание времени в окно"""
        return self.start_time <= check_time <= self.end_time


@dataclass
class BreakSchedule:
    """Шаблон графика перерывов"""
    schedule_id: str
    name: str
    shift_start: time
    shift_end: time
    limits: List[BreakLimit]
    windows: List[BreakWindow]


class BreakManager:
    """Менеджер системы перерывов v2.0"""
    
    def __init__(self, sheets_api):
        self.sheets = sheets_api
        self._cache: Dict[str, BreakSchedule] = {}
        
        # Импорт настроек ПЕРЕД использованием
        try:
            from config import (
                BREAK_SCHEDULES_SHEET,
                USER_BREAK_ASSIGNMENTS_SHEET,
                BREAK_USAGE_LOG_SHEET,
                BREAK_VIOLATIONS_SHEET,
                BREAK_OVERTIME_THRESHOLD,
                VIOLATION_TYPE_OUT_OF_WINDOW,
                VIOLATION_TYPE_OVER_LIMIT,
                VIOLATION_TYPE_QUOTA_EXCEEDED,
                SEVERITY_INFO,
                SEVERITY_WARNING,
                SEVERITY_CRITICAL
            )
            self.SCHEDULES_SHEET = BREAK_SCHEDULES_SHEET
            self.ASSIGNMENTS_SHEET = USER_BREAK_ASSIGNMENTS_SHEET
            self.USAGE_LOG_SHEET = BREAK_USAGE_LOG_SHEET
            self.VIOLATIONS_SHEET = BREAK_VIOLATIONS_SHEET
            self.OVERTIME_THRESHOLD = BREAK_OVERTIME_THRESHOLD
            self.VIOLATION_OUT_OF_WINDOW = VIOLATION_TYPE_OUT_OF_WINDOW
            self.VIOLATION_OVER_LIMIT = VIOLATION_TYPE_OVER_LIMIT
            self.VIOLATION_QUOTA_EXCEEDED = VIOLATION_TYPE_QUOTA_EXCEEDED
            self.SEVERITY_INFO = SEVERITY_INFO
            self.SEVERITY_WARNING = SEVERITY_WARNING
            self.SEVERITY_CRITICAL = SEVERITY_CRITICAL
        except ImportError as e:
            logger.warning(f"Failed to import config: {e}, using defaults")
            self.SCHEDULES_SHEET = "BreakSchedules"
            self.ASSIGNMENTS_SHEET = "UserBreakAssignments"
            self.USAGE_LOG_SHEET = "BreakUsageLog"
            self.VIOLATIONS_SHEET = "BreakViolations"
            self.OVERTIME_THRESHOLD = 2
            self.VIOLATION_OUT_OF_WINDOW = "OUT_OF_WINDOW"
            self.VIOLATION_OVER_LIMIT = "OVER_LIMIT"
            self.VIOLATION_QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
            self.SEVERITY_INFO = "INFO"
            self.SEVERITY_WARNING = "WARNING"
            self.SEVERITY_CRITICAL = "CRITICAL"
        
        # Автоматическая очистка старых зависших перерывов при инициализации
        try:
            self._cleanup_old_active_breaks()
        except Exception as e:
            logger.warning(f"Failed to cleanup old breaks on init: {e}")
        
        # Импорт настроек
        try:
            from config import (
                BREAK_SCHEDULES_SHEET,
                USER_BREAK_ASSIGNMENTS_SHEET,
                BREAK_USAGE_LOG_SHEET,
                BREAK_VIOLATIONS_SHEET,
                BREAK_OVERTIME_THRESHOLD,
                VIOLATION_TYPE_OUT_OF_WINDOW,
                VIOLATION_TYPE_OVER_LIMIT,
                VIOLATION_TYPE_QUOTA_EXCEEDED,
                SEVERITY_INFO,
                SEVERITY_WARNING,
                SEVERITY_CRITICAL
            )
            self.SCHEDULES_SHEET = BREAK_SCHEDULES_SHEET
            self.ASSIGNMENTS_SHEET = USER_BREAK_ASSIGNMENTS_SHEET
            self.USAGE_LOG_SHEET = BREAK_USAGE_LOG_SHEET
            self.VIOLATIONS_SHEET = BREAK_VIOLATIONS_SHEET
            self.OVERTIME_THRESHOLD = BREAK_OVERTIME_THRESHOLD
            self.VIOLATION_OUT_OF_WINDOW = VIOLATION_TYPE_OUT_OF_WINDOW
            self.VIOLATION_OVER_LIMIT = VIOLATION_TYPE_OVER_LIMIT
            self.VIOLATION_QUOTA_EXCEEDED = VIOLATION_TYPE_QUOTA_EXCEEDED
            self.SEVERITY_INFO = SEVERITY_INFO
            self.SEVERITY_WARNING = SEVERITY_WARNING
            self.SEVERITY_CRITICAL = SEVERITY_CRITICAL
        except ImportError as e:
            logger.warning(f"Failed to import config: {e}, using defaults")
            self.SCHEDULES_SHEET = "BreakSchedules"
            self.ASSIGNMENTS_SHEET = "UserBreakAssignments"
            self.USAGE_LOG_SHEET = "BreakUsageLog"
            self.VIOLATIONS_SHEET = "BreakViolations"
            self.OVERTIME_THRESHOLD = 2
            self.VIOLATION_OUT_OF_WINDOW = "OUT_OF_WINDOW"
            self.VIOLATION_OVER_LIMIT = "OVER_LIMIT"
            self.VIOLATION_QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
            self.SEVERITY_INFO = "INFO"
            self.SEVERITY_WARNING = "WARNING"
            self.SEVERITY_CRITICAL = "CRITICAL"
    
    # =================== УПРАВЛЕНИЕ ШАБЛОНАМИ ===================
    
    def create_schedule(
        self,
        schedule_id: str,
        name: str,
        shift_start: str,
        shift_end: str,
        limits: List[Dict],
        windows: List[Dict]
    ) -> bool:
        """
        Создаёт новый шаблон графика
        
        Args:
            schedule_id: ID графика (например, "SHIFT_8H")
            name: Название (например, "График 5/2 (9-18)")
            shift_start: Начало смены "09:00"
            shift_end: Конец смены "17:00"
            limits: [{"break_type": "Перерыв", "daily_count": 3, "time_minutes": 15}, ...]
            windows: [{"break_type": "Перерыв", "start": "10:00", "end": "12:00", "priority": 1}, ...]
        
        Returns:
            True если успешно
        """
        try:
            ws = self.sheets.get_worksheet(self.SCHEDULES_SHEET)
            
            # Проверяем, является ли это Supabase API
            if hasattr(self.sheets, 'client') and hasattr(self.sheets.client, 'table'):
                # Для Supabase: сначала создаем основную запись (если её нет), затем слоты
                # Проверяем, существует ли уже шаблон с таким именем
                existing = self.sheets.client.table('break_schedules')\
                    .select('id, name, description')\
                    .eq('name', name)\
                    .execute()
                
                # Проверяем, есть ли основная запись (без description или с пустым description)
                main_record = None
                for record in existing.data:
                    desc = record.get('description')
                    if not desc or desc.strip() == '':
                        main_record = record
                        break
                
                # Если основной записи нет, создаем её
                if not main_record:
                    schedule_data = {
                        'name': name,
                        'shift_start': shift_start,
                        'shift_end': shift_end,
                        'is_active': True,
                        'description': None  # Основная запись без description
                    }
                    schedule_response = self.sheets.client.table('break_schedules').insert(schedule_data).execute()
                    if schedule_response.data:
                        main_record = schedule_response.data[0]
                        logger.info(f"Created main schedule record: {main_record['id']} for name '{name}'")
                else:
                    # Обновляем shift_start и shift_end основной записи, если они изменились
                    update_data = {}
                    if shift_start and main_record.get('shift_start') != shift_start:
                        update_data['shift_start'] = shift_start
                    if shift_end and main_record.get('shift_end') != shift_end:
                        update_data['shift_end'] = shift_end
                    if update_data:
                        self.sheets.client.table('break_schedules')\
                            .update(update_data)\
                            .eq('id', main_record['id'])\
                            .execute()
                        logger.debug(f"Updated main schedule record: {update_data}")
            
            # Формируем строки для записи
            rows = []
            
            # Для каждого лимита создаём строку
            for limit in limits:
                # Находим окна для этого типа перерыва
                break_windows = [w for w in windows if w.get('break_type') == limit['break_type']]
                
                if break_windows:
                    for window in break_windows:
                        rows.append([
                            schedule_id,
                            name,
                            shift_start,
                            shift_end,
                            limit['break_type'],
                            str(limit['time_minutes']),
                            window.get('start', ''),
                            window.get('end', ''),
                            str(window.get('priority', 1))
                        ])
                else:
                    # Если нет окон, всё равно создаём строку (окно = весь день)
                    rows.append([
                        schedule_id,
                        name,
                        shift_start,
                        shift_end,
                        limit['break_type'],
                        str(limit['time_minutes']),
                        shift_start,  # Окно = вся смена
                        shift_end,
                        "1"
                    ])
            
            # Записываем все строки
            for row in rows:
                self.sheets._request_with_retry(lambda: ws.append_row(row))
            
            logger.info(f"Created schedule {schedule_id} with {len(rows)} rows")
            
            # Сбрасываем кэш
            self._cache.pop(schedule_id, None)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to create schedule: {e}", exc_info=True)
            return False
    
    def get_schedule(self, schedule_id: str) -> Optional[BreakSchedule]:
        """Получает шаблон графика по ID или имени"""
        # Проверяем кэш
        if schedule_id in self._cache:
            return self._cache[schedule_id]
        
        try:
            ws = self.sheets.get_worksheet(self.SCHEDULES_SHEET)
            rows = self.sheets._read_table(ws)
            
            # Фильтруем строки для данного графика
            # Пробуем найти по ScheduleID (UUID) или по Name (имя шаблона)
            schedule_rows = [
                r for r in rows 
                if (r.get("ScheduleID") == schedule_id or 
                    r.get("Name") == schedule_id or
                    r.get("ScheduleUUID") == schedule_id)  # Также проверяем ScheduleUUID если есть
            ]
            if not schedule_rows:
                return None
            
            first = schedule_rows[0]
            
            # Собираем лимиты (уникальные по типу)
            limits_dict = {}
            for row in schedule_rows:
                break_type = row.get("SlotType", "")
                if break_type and break_type not in limits_dict:
                    limits_dict[break_type] = BreakLimit(
                        break_type=break_type,
                        daily_count=3 if break_type == "Перерыв" else 1,  # По умолчанию
                        time_minutes=int(row.get("Duration", "15"))
                    )
            
            # Собираем окна
            windows = []
            for row in schedule_rows:
                try:
                    window_start = parse_time(row.get("WindowStart", "09:00"), "09:00")
                    window_end = parse_time(row.get("WindowEnd", "17:00"), "17:00")
                    windows.append(BreakWindow(
                        break_type=row.get("SlotType", ""),
                        start_time=window_start,
                        end_time=window_end,
                        priority=int(row.get("Order", "1"))
                    ))
                except Exception as e:
                    logger.debug(f"Failed to parse window for row: {e}")
                    pass
            
            # Создаём объект графика
            schedule = BreakSchedule(
                schedule_id=schedule_id,
                name=first.get("Name", ""),
                shift_start=parse_time(first.get("ShiftStart", "09:00"), "09:00"),
                shift_end=parse_time(first.get("ShiftEnd", "17:00"), "17:00"),
                limits=list(limits_dict.values()),
                windows=windows
            )
            
            # Кэшируем
            self._cache[schedule_id] = schedule
            
            return schedule
            
        except Exception as e:
            logger.error(f"Failed to get schedule {schedule_id}: {e}", exc_info=True)
            return None
    
    def list_schedules(self) -> List[Dict]:
        """Возвращает список всех шаблонов"""
        try:
            ws = self.sheets.get_worksheet(self.SCHEDULES_SHEET)
            rows = self.sheets._read_table(ws)
            
            # Группируем по name для Supabase (где name используется как идентификатор шаблона)
            # В Supabase каждая запись имеет свой UUID, но шаблоны группируются по name
            schedules = {}
            for row in rows:
                name = row.get("Name", "").strip()
                if not name:
                    continue
                
                # Используем name как ключ для группировки
                # Для schedule_id используем первый найденный UUID или name
                if name not in schedules:
                    # Ищем первый UUID для этого шаблона (из основной записи или первого слота)
                    sid = row.get("ScheduleID") or row.get("Id") or row.get("id") or name
                    schedules[name] = {
                        "schedule_id": str(sid).strip(),
                        "name": name,
                        "shift_start": row.get("ShiftStart", "") or "",
                        "shift_end": row.get("ShiftEnd", "") or "",
                        "slots_data": []  # Инициализируем список слотов
                    }
                
                # Добавляем слот в список слотов шаблона
                slot_type = row.get("SlotType") or row.get("slot_type") or ""
                duration = row.get("Duration") or row.get("duration") or "15"
                window_start = row.get("WindowStart") or row.get("window_start") or ""
                window_end = row.get("WindowEnd") or row.get("window_end") or ""
                order = row.get("Order") or row.get("priority") or row.get("order") or "1"
                
                # Проверяем, есть ли данные слота (либо в полях, либо в description как JSON)
                description = row.get("Description") or row.get("description") or ""
                # Пропускаем основную запись (без description или с пустым description)
                if not description or description.strip() == '':
                    continue  # Это основная запись шаблона, не слот
                
                if description and not slot_type:
                    # Пробуем извлечь данные из JSON в description
                    try:
                        import json
                        slot_info = json.loads(description)
                        slot_type = slot_info.get('slot_type', '')
                        duration = str(slot_info.get('duration', '15'))
                        window_start = slot_info.get('window_start', '')
                        window_end = slot_info.get('window_end', '')
                        order = str(slot_info.get('priority', '1'))
                    except (json.JSONDecodeError, KeyError, TypeError):
                        pass
                
                if slot_type:  # Добавляем только если есть тип слота
                    schedules[name]["slots_data"].append({
                        "order": str(order),
                        "type": slot_type,
                        "duration": str(duration),
                        "window_start": window_start or "09:00",
                        "window_end": window_end or "17:00"
                    })
            
            return list(schedules.values())
            
        except Exception as e:
            logger.error(f"Failed to list schedules: {e}")
            return []
    
    def delete_schedule(self, schedule_id: str) -> bool:
        """Удаляет шаблон графика"""
        try:
            # Проверяем, является ли это Supabase API
            if hasattr(self.sheets, 'client') and hasattr(self.sheets.client, 'table'):
                # Используем прямой метод удаления для Supabase
                result = self.sheets._delete_rows_by_schedule_id("break_schedules", schedule_id)
                if result:
                    # Сбрасываем кэш шаблонов
                    self._cache.pop(schedule_id, None)
                    # Очищаем весь кэш назначений (так как назначения могли ссылаться на удалённый шаблон)
                    # Находим все email, у которых был назначен этот шаблон, и очищаем их кэш
                    try:
                        ws = self.sheets.get_worksheet(self.ASSIGNMENTS_SHEET)
                        assignments = self.sheets._read_table(ws)
                        for assignment in assignments:
                            assigned_schedule_id = assignment.get("ScheduleID") or assignment.get("ScheduleId") or assignment.get("Id")
                            if assigned_schedule_id and str(assigned_schedule_id) == str(schedule_id):
                                email = assignment.get("Email", "")
                                if email:
                                    # Очищаем кэш для этого пользователя (если есть метод для этого)
                                    logger.debug(f"Clearing cache for user {email} after schedule deletion")
                    except Exception as e:
                        logger.debug(f"Could not clear assignment cache: {e}")
                    
                    logger.info(f"Deleted schedule: {schedule_id}")
                return result
            
            # Старый код для Google Sheets
            ws = self.sheets.get_worksheet(self.SCHEDULES_SHEET)
            values = self.sheets._request_with_retry(ws.get_all_values)
            
            if not values or len(values) < 2:
                return False
            
            header = values[0]
            body = values[1:]
            
            # Находим индекс колонки ScheduleID
            try:
                sid_idx = header.index("ScheduleID")
            except ValueError:
                logger.error("Column ScheduleID not found")
                return False
            
            # Фильтруем строки (удаляем те, где ScheduleID совпадает)
            filtered = [r for r in body if not r or len(r) <= sid_idx or r[sid_idx] != schedule_id]
            
            # Очищаем лист и записываем заново
            ws.clear()
            ws.append_row(header)
            for row in filtered:
                ws.append_row(row)
            
            # Сбрасываем кэш
            self._cache.pop(schedule_id, None)
            
            logger.info(f"Deleted schedule: {schedule_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete schedule {schedule_id}: {e}", exc_info=True)
            return False
    
    # =================== НАЗНАЧЕНИЕ ГРАФИКОВ ===================
    
    def assign_schedule(
        self,
        email: str,
        schedule_id: str,
        admin_email: str
    ) -> bool:
        """Назначает график пользователю"""
        try:
            # Проверяем существование графика
            schedule = self.get_schedule(schedule_id)
            if not schedule:
                logger.error(f"Schedule {schedule_id} not found")
                return False
            
            ws = self.sheets.get_worksheet(self.ASSIGNMENTS_SHEET)
            
            # Проверяем, есть ли уже назначение
            rows = self.sheets._read_table(ws)
            existing = next((r for r in rows if r.get("Email", "").lower() == email.lower()), None)
            
            # Проверяем, является ли это Supabase API
            if hasattr(self.sheets, 'client') and hasattr(self.sheets.client, 'table'):
                # Для Supabase API используем прямое обновление/вставку
                if existing:
                    # Обновляем существующее назначение
                    try:
                        # Находим id записи по email (пробуем разные варианты полей)
                        assignment_id = None
                        for email_field in ['email', 'user_email']:
                            try:
                                find_response = self.sheets.client.table('user_break_assignments')\
                                    .select('id')\
                                    .eq(email_field, email.lower())\
                                    .execute()
                                
                                if find_response.data:
                                    assignment_id = find_response.data[0]['id']
                                    break
                            except Exception:
                                continue
                        
                        if assignment_id:
                            # Нужно найти UUID шаблона по его имени или ID
                            schedule_uuid = None
                            try:
                                import re
                                uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
                                is_uuid = uuid_pattern.match(str(schedule_id).strip())
                                
                                if is_uuid:
                                    # Это уже UUID, проверяем что шаблон существует
                                    find_schedule = self.sheets.client.table('break_schedules')\
                                        .select('id')\
                                        .eq('id', schedule_id)\
                                        .execute()
                                    if find_schedule.data:
                                        schedule_uuid = find_schedule.data[0]['id']
                                    else:
                                        logger.error(f"Schedule UUID not found: {schedule_id}")
                                        return False
                                else:
                                    # Это не UUID, ищем по имени
                                    find_schedule = self.sheets.client.table('break_schedules')\
                                        .select('id')\
                                        .eq('name', schedule_id)\
                                        .execute()
                                    if find_schedule.data:
                                        schedule_uuid = find_schedule.data[0]['id']
                                    else:
                                        logger.error(f"Schedule not found by name: {schedule_id}")
                                        return False
                            except Exception as e:
                                logger.error(f"Failed to find schedule UUID: {e}", exc_info=True)
                                return False
                            
                            # Обновляем назначение с UUID шаблона
                            try:
                                self.sheets.client.table('user_break_assignments')\
                                    .update({'schedule_id': schedule_uuid})\
                                    .eq('id', assignment_id)\
                                    .execute()
                                logger.info(f"Updated schedule assignment for {email}")
                                return True
                            except Exception as update_error:
                                logger.error(f"Failed to update assignment: {update_error}", exc_info=True)
                                return False
                        else:
                            logger.error(f"Assignment not found for {email}")
                            return False
                    except Exception as e:
                        logger.error(f"Failed to update assignment: {e}", exc_info=True)
                        return False
                else:
                    # Создаём новое назначение через append_row (который теперь поддерживает user_break_assignments)
                    # Передаём только обязательные поля (email и schedule_id)
                    result = ws.append_row([
                        email,
                        schedule_id,
                        datetime.now().strftime("%Y-%m-%d"),  # Может быть проигнорировано если поле отсутствует
                        admin_email  # Может быть проигнорировано если поле отсутствует
                    ])
                    if result:
                        logger.info(f"Created schedule assignment for {email}")
                        return True
                    else:
                        logger.error(f"Failed to create assignment for {email}")
                        return False
            else:
                # Старый код для Google Sheets
                if existing:
                    # Обновляем существующее назначение
                    # Находим номер строки
                    all_values = ws.get_all_values()
                    for idx, row in enumerate(all_values[1:], start=2):
                        if row and row[0].lower() == email.lower():
                            # Обновляем строку
                            ws.update(f"A{idx}:D{idx}", [[
                                email,
                                schedule_id,
                                datetime.now().strftime("%Y-%m-%d"),
                                admin_email
                            ]])
                            logger.info(f"Updated schedule assignment for {email}")
                            return True
                else:
                    # Создаём новое назначение
                    ws.append_row([
                        email,
                        schedule_id,
                        datetime.now().strftime("%Y-%m-%d"),
                        admin_email
                    ])
                    logger.info(f"Created schedule assignment for {email}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to assign schedule: {e}", exc_info=True)
            return False
    
    def get_user_schedule(self, email: str) -> Optional[BreakSchedule]:
        """Получает назначенный график пользователя"""
        try:
            ws = self.sheets.get_worksheet(self.ASSIGNMENTS_SHEET)
            rows = self.sheets._read_table(ws)
            
            # Ищем назначение
            assignment = next((r for r in rows if r.get("Email", "").lower() == email.lower()), None)
            
            if not assignment:
                return None
            
            schedule_id = assignment.get("ScheduleID", "")
            if not schedule_id:
                return None
            
            return self.get_schedule(schedule_id)
            
        except Exception as e:
            logger.error(f"Failed to get user schedule: {e}")
            return None
    
    def unassign_schedule(self, email: str) -> bool:
        """Удаляет назначение графика"""
        try:
            ws = self.sheets.get_worksheet(self.ASSIGNMENTS_SHEET)
            all_values = ws.get_all_values()
            
            if len(all_values) < 2:
                return False
            
            # Находим и удаляем строку
            for idx, row in enumerate(all_values[1:], start=2):
                if row and row[0].lower() == email.lower():
                    ws.delete_rows(idx)
                    logger.info(f"Unassigned schedule from {email}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to unassign schedule: {e}")
            return False
    
    # =================== ИСПОЛЬЗОВАНИЕ ПЕРЕРЫВОВ ===================
    
    def start_break(
        self,
        email: str,
        break_type: str,
        session_id: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Начинает перерыв/обед
        
        Args:
            email: Email пользователя
            break_type: "Перерыв" или "Обед"
            session_id: ID текущей сессии (опционально)
        
        Returns:
            (success, error_message)
        """
        try:
            # 1. Получить график пользователя
            schedule = self.get_user_schedule(email)
            if not schedule:
                # v20.3.4: Используем дефолтные лимиты если графика нет
                logger.warning(f"No schedule for {email}, using default limits")
                from dataclasses import dataclass
                @dataclass
                class DefaultLimit:
                    break_type: str
                    time_minutes: int
                    daily_count: int
                @dataclass
                class DefaultSchedule:
                    limits: list
                    windows: list = None
                # Дефолтные лимиты: 3 перерыва по 15 мин, 1 обед 60 мин
                schedule = DefaultSchedule(limits=[
                    DefaultLimit("Перерыв", 15, 3),
                    DefaultLimit("Обед", 60, 1)
                ])
                return False, "У вас нет назначенного графика перерывов"
            
            # 2. Найти лимит для этого типа
            limit = next((l for l in schedule.limits if l.break_type == break_type), None)
            if not limit:
                # Если лимита нет в графике, используем дефолтные значения и разрешаем перерыв
                # Но фиксируем нарушение - перерыв вне разрешенного времени
                logger.warning(f"No limit found for {break_type} in schedule, using defaults and allowing break")
                
                # Дефолтные лимиты
                from dataclasses import dataclass
                @dataclass
                class DefaultLimit:
                    break_type: str
                    time_minutes: int
                    daily_count: int
                
                if break_type == "Перерыв":
                    limit = DefaultLimit("Перерыв", 15, 3)
                elif break_type == "Обед":
                    limit = DefaultLimit("Обед", 60, 1)
                else:
                    limit = DefaultLimit(break_type, 15, 1)
                
                # Фиксируем нарушение - перерыв вне разрешенного времени
                self._log_violation(
                    email=email,
                    session_id=session_id,
                    violation_type=self.VIOLATION_OUT_OF_WINDOW,
                    severity=self.SEVERITY_WARNING,
                    details=f"{break_type} начат вне разрешенного времени (нет слота в графике)"
                )
            
            # 3. Проверить дневной лимит
            today_count = self._count_breaks_today(email, break_type)
            # today_count - это количество УЖЕ существующих перерывов до начала нового
            # Новый перерыв будет (today_count + 1)-м
            new_total_count = today_count + 1
            quota_exceeded = new_total_count > limit.daily_count
            
            logger.info(
                f"Quota check for {email} ({break_type}): "
                f"existing={today_count}, new_total={new_total_count}, "
                f"limit={limit.daily_count}, exceeded={quota_exceeded}"
            )
            
            if quota_exceeded:
                # Превышение квоты - критическое нарушение
                # НО разрешаем перерыв (не блокируем пользователя)
                self._log_violation(
                    email=email,
                    session_id=session_id,
                    violation_type=self.VIOLATION_QUOTA_EXCEEDED,
                    severity=self.SEVERITY_CRITICAL,
                    details=f"Превышен дневной лимит {break_type}: {new_total_count}/{limit.daily_count}"
                )
                
                # Отправить уведомление в группу (одно за нарушение)
                try:
                    from shared.break_notifications_v2 import send_quota_exceeded_notification
                    send_quota_exceeded_notification(
                        email=email,
                        break_type=break_type,
                        used_count=new_total_count,  # Используем правильное количество
                        limit_count=limit.daily_count
                    )
                except Exception as e:
                    logger.error(f"Failed to send quota notification: {e}")
                
                # НЕ блокируем - продолжаем начинать перерыв
                logger.warning(f"Quota exceeded for {email}, but allowing break (violation logged)")
            
            # 4. Проверить временное окно
            now = datetime.now()
            current_time = now.time()
            in_window = False
            
            # Проверяем окна только если они есть в графике
            if schedule.windows:
                for window in schedule.windows:
                    if window.break_type == break_type and window.is_within(current_time):
                        in_window = True
                        break
            else:
                # Если окон нет в графике, считаем что перерыв вне окна
                in_window = False
            
            # 5. Логировать начало
            self._log_break_start(
                email=email,
                session_id=session_id,
                break_type=break_type,
                start_time=now,
                limit_minutes=limit.time_minutes,
                in_window=in_window
            )
            
            # 6. Если вне окна - фиксируем нарушение и отправляем уведомление в группу
            if not in_window:
                self._log_violation(
                    email=email,
                    session_id=session_id,
                    violation_type=self.VIOLATION_OUT_OF_WINDOW,
                    severity=self.SEVERITY_WARNING,  # Изменено с INFO на WARNING
                    details=f"{break_type} начат вне временного окна ({current_time.strftime('%H:%M')})"
                )
            
            logger.info(f"Break started: {email}, {break_type}, in_window={in_window}")
            return True, None
            
        except Exception as e:
            logger.error(f"Failed to start break: {e}", exc_info=True)
            return False, f"Ошибка: {str(e)}"
    
    def end_break(
        self,
        email: str,
        break_type: str
    ) -> Tuple[bool, Optional[str], Optional[int]]:
        """
        Завершает перерыв/обед
        
        Args:
            email: Email пользователя
            break_type: "Перерыв" или "Обед"
        
        Returns:
            (success, error_message, actual_duration)
        """
        try:
            # 1. Найти активный перерыв
            active = self._get_active_break(email, break_type)
            if not active:
                return False, "Активный перерыв не найден", None
            
            # 2. Вычислить длительность
            now = datetime.now()
            start_time_str = active.get("StartTime") or active.get("start_time") or ""
            
            # Поддерживаем разные форматы времени
            try:
                if isinstance(start_time_str, str):
                    # Убираем timezone если есть (для совместимости)
                    start_time_clean = start_time_str.replace('Z', '').split('+')[0].split('.')[0]
                    # Пробуем разные форматы
                    try:
                        start_time = datetime.strptime(start_time_clean, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        try:
                            start_time = datetime.strptime(start_time_clean, "%Y-%m-%dT%H:%M:%S")
                        except ValueError:
                            # Используем fromisoformat как fallback
                            start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                else:
                    start_time = datetime.fromisoformat(str(start_time_str))
            except Exception as e:
                logger.error(f"Failed to parse start_time: {start_time_str}, error: {e}")
                return False, f"Ошибка парсинга времени начала перерыва", None
            
            duration = int((now - start_time).total_seconds() / 60)
            limit = int(active.get("ExpectedDuration") or active.get("Duration") or "15")
            
            # 3. Обновить запись об окончании
            self._update_break_end(
                email=email,
                break_type=break_type,
                end_time=now,
                duration=duration
            )
            
            # 4. Проверить превышение
            overtime = duration - limit
            # Уведомление при превышении на 1+ минуту (изменено с OVERTIME_THRESHOLD)
            if overtime >= 1:
                # Критическое нарушение
                self._log_violation(
                    email=email,
                    session_id=active.get("SessionID"),
                    violation_type=self.VIOLATION_OVER_LIMIT,
                    severity=self.SEVERITY_CRITICAL,
                    details=f"Превышен лимит на {overtime} мин ({duration}/{limit})"
                )
                
                # Отправить уведомления (новая система с дебаунсингом)
                try:
                    from shared.break_notifications_v2 import send_overtime_notification
                    send_overtime_notification(
                        email=email,
                        break_type=break_type,
                        duration=duration,
                        limit=limit,
                        overtime=overtime
                    )
                except Exception as e:
                    logger.error(f"Failed to send notification: {e}")
            
            logger.info(f"Break ended: {email}, {break_type}, duration={duration}")
            return True, None, duration
            
        except Exception as e:
            logger.error(f"Failed to end break: {e}", exc_info=True)
            return False, f"Ошибка: {str(e)}", None
    
    def get_break_status(self, email: str) -> Dict:
        """
        Получает текущий статус перерывов пользователя
        
        Returns:
            {
                "schedule": {"name": "...", ...},
                "limits": {"Перерыв": {"count": 3, "time": 15}, ...},
                "used_today": {"Перерыв": 2, "Обед": 0},
                "active_break": {...} or None
            }
        """
        try:
            schedule = self.get_user_schedule(email)
            if not schedule:
                # v20.3.4: Используем дефолтные лимиты если графика нет
                logger.warning(f"No schedule for {email}, using default limits")
                from dataclasses import dataclass
                @dataclass
                class DefaultLimit:
                    break_type: str
                    time_minutes: int
                    daily_count: int
                @dataclass
                class DefaultSchedule:
                    limits: list
                    windows: list = None
                # Дефолтные лимиты: 3 перерыва по 15 мин, 1 обед 60 мин
                schedule = DefaultSchedule(limits=[
                    DefaultLimit("Перерыв", 15, 3),
                    DefaultLimit("Обед", 60, 1)
                ])
                return {}
            
            # Лимиты
            limits = {}
            for limit in schedule.limits:
                limits[limit.break_type] = {
                    "count": limit.daily_count,
                    "time": limit.time_minutes
                }
            
            # Использование сегодня
            used_today = {}
            for break_type in ["Перерыв", "Обед"]:
                used_today[break_type] = self._count_breaks_today(email, break_type)
            
            # Активный перерыв
            active_break = None
            for break_type in ["Перерыв", "Обед"]:
                active = self._get_active_break(email, break_type)
                if active:
                    start_time = datetime.fromisoformat(active["StartTime"])
                    duration = int((datetime.now() - start_time).total_seconds() / 60)
                    # Конвертируем время начала в московское для отображения в интерфейсе
                    start_time_moscow = to_moscow(start_time)
                    start_time_formatted = start_time_moscow.strftime("%H:%M") if start_time_moscow else start_time.strftime("%H:%M")
                    active_break = {
                        "break_type": break_type,
                        "start_time": start_time_formatted,
                        "duration": duration,
                        "limit": int(active.get("ExpectedDuration", "15"))
                    }
                    break
            
            return {
                "schedule": {
                    "name": schedule.name,
                    "schedule_id": schedule.schedule_id
                },
                "limits": limits,
                "used_today": used_today,
                "active_break": active_break
            }
            
        except Exception as e:
            logger.error(f"Failed to get break status: {e}")
            return {}
    
    # =================== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ===================
    
    def _count_breaks_today(self, email: str, break_type: str) -> int:
        """Подсчитывает количество перерывов сегодня (в московском времени)"""
        try:
            # Проверяем, используем ли мы Supabase
            if hasattr(self.sheets, 'client') and hasattr(self.sheets.client, 'table'):
                # Используем Supabase напрямую
                # Важно: используем московское время для определения "сегодня"
                from shared.time_utils import now_moscow, to_moscow
                from datetime import timezone, timedelta
                
                moscow_now = now_moscow()
                today = moscow_now.date()
                
                # Получаем все перерывы за сегодня для данного пользователя и типа
                # Сначала получаем все перерывы пользователя за последние 2 дня (на случай перехода через UTC)
                result = self.sheets.client.table('break_log').select(
                    'id,email,break_type,start_time,end_time'
                ).eq('email', email.lower()).eq('break_type', break_type).execute()
                
                breaks_data = result.data if hasattr(result, 'data') else []
                
                # Фильтруем перерывы по московской дате
                count = 0
                for entry in breaks_data:
                    start_time_str = entry.get('start_time')
                    if not start_time_str:
                        continue
                    
                    # Конвертируем start_time в московское время
                    start_time_moscow = to_moscow(start_time_str)
                    if start_time_moscow and start_time_moscow.date() == today:
                        count += 1
                
                # Логируем детали для отладки
                logger.info(
                    f"Counted breaks for {email} ({break_type}): {count} "
                    f"(from Supabase break_log, date={today.isoformat()} Moscow time, "
                    f"total entries checked: {len(breaks_data)})"
                )
                
                # Детальное логирование первых нескольких перерывов
                if breaks_data:
                    logger.debug(f"Break entries found for {email} ({break_type}):")
                    for i, entry in enumerate(breaks_data[:10], 1):
                        start_time_str = entry.get('start_time')
                        start_time_moscow = to_moscow(start_time_str) if start_time_str else None
                        logger.debug(
                            f"  {i}. id={entry.get('id')}, "
                            f"start_time={start_time_str}, "
                            f"start_time_moscow={start_time_moscow}, "
                            f"date_match={start_time_moscow.date() == today if start_time_moscow else False}"
                        )
                
                return count
            else:
                # Используем Google Sheets через совместимый интерфейс
                ws = self.sheets.get_worksheet(self.USAGE_LOG_SHEET)
                rows = self.sheets._read_table(ws)
                
                today = date.today().isoformat()
                
                count = 0
                for row in rows:
                    row_email = row.get("Email") or row.get("email") or ""
                    row_break_type = row.get("BreakType") or row.get("break_type") or ""
                    start_time_str = row.get("StartTime") or row.get("start_time") or ""
                    
                    if (row_email.lower() == email.lower() and
                        row_break_type == break_type and
                        start_time_str.startswith(today)):
                        count += 1
                
                logger.debug(
                    f"Counted breaks for {email} ({break_type}): {count} "
                    f"(from Google Sheets {self.USAGE_LOG_SHEET}, date={today})"
                )
                
                return count
            
        except Exception as e:
            logger.error(f"Failed to count breaks for {email} ({break_type}): {e}", exc_info=True)
            return 0
    
    def _get_active_break(self, email: str, break_type: str) -> Optional[Dict]:
        """Получает активный перерыв (без EndTime) за сегодня"""
        try:
            ws = self.sheets.get_worksheet(self.USAGE_LOG_SHEET)
            rows = self.sheets._read_table(ws)
            
            today = date.today().isoformat()
            
            # Ищем с конца (самый последний активный перерыв)
            for row in reversed(rows):
                row_email = row.get("Email") or row.get("email") or ""
                row_break_type = row.get("BreakType") or row.get("break_type") or ""
                end_time = row.get("EndTime") or row.get("end_time") or None
                status = row.get("Status") or row.get("status") or ""
                start_time_str = row.get("StartTime") or row.get("start_time") or ""
                
                # Перерыв активен если: нет EndTime (None или пустая строка) И Status = 'Active' (или пустой/None)
                has_end_time = end_time is not None and str(end_time).strip() != ''
                is_active_status = status == 'Active' or status == '' or status is None or not status
                is_active = not has_end_time and is_active_status
                
                # Ищем активный перерыв только за сегодня
                is_today = start_time_str.startswith(today)
                
                if (row_email.lower() == email.lower() and
                    row_break_type == break_type and
                    is_active and
                    is_today):  # Только сегодня!
                    return row
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get active break: {e}")
            return None
    
    def _log_break_start(
        self,
        email: str,
        session_id: Optional[str],
        break_type: str,
        start_time: datetime,
        limit_minutes: int,
        in_window: bool
    ):
        """Логирует начало перерыва в BreakLog (v20.3 format)"""
        try:
            ws = self.sheets.get_worksheet(self.USAGE_LOG_SHEET)
            
            # Получаем имя пользователя
            try:
                users = self.sheets.get_users()
                user = next((u for u in users if u.get('Email', '').lower() == email.lower()), None)
                name = user.get('Name', '') if user else ''
            except:
                name = ''
            
            # Формат BreakLog (v20.3): Email, Name, BreakType, StartTime, EndTime, Duration, Date, Status
            row = [
                email,
                name,
                break_type,
                start_time.strftime("%Y-%m-%d %H:%M:%S"),
                "",  # EndTime (заполнится при завершении)
                "",  # Duration (заполнится при завершении)
                start_time.strftime("%Y-%m-%d"),  # Date
                "Active"  # Status
            ]
            
            logger.debug(f"Logging break start: email={email}, break_type={break_type}, start_time={start_time}, row={row}")
            result = self.sheets._request_with_retry(lambda: ws.append_row(row))
            logger.info(f"✅ Break logged to BreakLog: {email}, {break_type}, result={result}")
            
        except Exception as e:
            logger.error(f"❌ Failed to log break start: {e}")
    
    def _update_break_end(
        self,
        email: str,
        break_type: str,
        end_time: datetime,
        duration: int
    ):
        """Обновляет запись об окончании перерыва (v20.3 format)"""
        try:
            # Проверяем, является ли это Supabase API
            if hasattr(self.sheets, 'client') and hasattr(self.sheets.client, 'table'):
                # Для Supabase используем прямой метод обновления
                try:
                    from datetime import timezone
                    # Находим активный перерыв по email и break_type без end_time
                    response = self.sheets.client.table('break_log')\
                        .select('id')\
                        .eq('email', email.lower())\
                        .eq('break_type', break_type)\
                        .is_('end_time', 'null')\
                        .order('start_time', desc=True)\
                        .limit(1)\
                        .execute()
                    
                    if response.data:
                        break_id = response.data[0]['id']
                        
                        # Обновляем запись
                        update_data = {
                            'end_time': end_time.astimezone(timezone.utc).isoformat(),
                            'duration_minutes': duration,
                            'status': 'Completed'
                        }
                        
                        self.sheets.client.table('break_log')\
                            .update(update_data)\
                            .eq('id', break_id)\
                            .execute()
                        
                        logger.info(f"✅ Updated break end in Supabase: {email}, {break_type}, duration={duration} min")
                        return
                    else:
                        logger.warning(f"No active break found to update: {email}, {break_type}")
                        return
                except Exception as e:
                    logger.error(f"Failed to update break end in Supabase: {e}", exc_info=True)
                    return
            
            # Старый код для Google Sheets
            ws = self.sheets.get_worksheet(self.USAGE_LOG_SHEET)
            all_values = ws.get_all_values()
            
            if len(all_values) < 2:
                return
            
            header = all_values[0]
            
            # Находим индексы колонок
            try:
                email_idx = header.index("Email")
                break_type_idx = header.index("BreakType")
                end_time_idx = header.index("EndTime")
                actual_dur_idx = header.index("Duration")  # v20.3: renamed from ActualDuration
            except ValueError as e:
                logger.error(f"Column not found: {e}")
                return
            
            # Ищем активный перерыв (последний без EndTime)
            for idx in range(len(all_values) - 1, 0, -1):
                row = all_values[idx]
                if (len(row) > max(email_idx, break_type_idx, end_time_idx) and
                    row[email_idx].lower() == email.lower() and
                    row[break_type_idx] == break_type and
                    not row[end_time_idx]):
                    
                    # Обновляем эту строку
                    row_num = idx + 1
                    end_time_cell = f"{self._col_letter(end_time_idx + 1)}{row_num}"
                    duration_cell = f"{self._col_letter(actual_dur_idx + 1)}{row_num}"
                    
                    # Обновляем EndTime
                    ws.update(end_time_cell, [[end_time.strftime("%Y-%m-%d %H:%M:%S")]])
                    # Обновляем Duration
                    ws.update(duration_cell, [[str(duration)]])
                    
                    logger.info(f"Updated break end: {email}, {break_type}")
                    return
            
        except Exception as e:
            logger.error(f"Failed to update break end: {e}", exc_info=True)
    
    def _log_violation(
        self,
        email: str,
        session_id: Optional[str],
        violation_type: str,
        severity: str,
        details: str
    ):
        """Логирует нарушение"""
        try:
            ws = self.sheets.get_worksheet(self.VIOLATIONS_SHEET)
            
            row = [
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                email,
                session_id or "",
                violation_type,
                details,
                "pending"  # Status
            ]
            
            result = self.sheets._request_with_retry(lambda: ws.append_row(row))
            
            if result:
                logger.warning(f"Violation logged: {email}, {violation_type}, {severity}")
            else:
                logger.error(f"Failed to log violation: {email}, {violation_type}, {severity}")
            
        except Exception as e:
            logger.error(f"Failed to log violation: {e}")
    
    def _col_letter(self, col_num: int) -> str:
        """Преобразует номер колонки в букву (1 -> A, 2 -> B, ...)"""
        result = ""
        while col_num > 0:
            col_num -= 1
            result = chr(65 + (col_num % 26)) + result
            col_num //= 26
        return result
    
    # =================== ОТЧЁТЫ И АНАЛИТИКА ===================
    
    def get_violations_report(
        self,
        email: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        violation_type: Optional[str] = None
    ) -> List[Dict]:
        """Получает отчёт по нарушениям"""
        try:
            ws = self.sheets.get_worksheet(self.VIOLATIONS_SHEET)
            rows = self.sheets._read_table(ws)
            
            filtered = rows
            
            if email:
                filtered = [r for r in filtered if r.get("Email", "").lower() == email.lower()]
            
            def extract_date(ts_str):
                """Извлекает дату из timestamp в формате YYYY-MM-DD"""
                if not ts_str:
                    return ""
                ts_str = str(ts_str)
                # ISO формат: 2025-12-11T14:30:00+00:00 или 2025-12-11T14:30:00
                # Обычный формат: 2025-12-11 14:30:00
                if 'T' in ts_str:
                    return ts_str.split('T')[0][:10]
                elif ' ' in ts_str:
                    return ts_str.split(' ')[0][:10]
                else:
                    return ts_str[:10]
            
            if date_from:
                # Для дат без времени сравниваем первые 10 символов
                if len(date_from) == 10:  # Формат YYYY-MM-DD
                    filtered = [r for r in filtered 
                               if r.get("Timestamp") and extract_date(r.get("Timestamp", "")) >= date_from]
                else:
                    filtered = [r for r in filtered if r.get("Timestamp", "") >= date_from]
            
            if date_to:
                # Для date_to используем <= только если указано время
                if len(date_to) == 10:  # Формат YYYY-MM-DD
                    # Включаем весь день - сравниваем первые 10 символов
                    filtered = [r for r in filtered 
                               if r.get("Timestamp") and extract_date(r.get("Timestamp", "")) <= date_to]
                else:
                    filtered = [r for r in filtered if r.get("Timestamp", "") <= date_to]
            
            if violation_type:
                filtered = [r for r in filtered if r.get("ViolationType") == violation_type]
            
            return filtered
            
        except Exception as e:
            logger.error(f"Failed to get violations report: {e}")
            return []
    
    def get_usage_stats(
        self,
        email: str,
        date_filter: Optional[str] = None
    ) -> Dict:
        """Получает статистику использования перерывов"""
        try:
            ws = self.sheets.get_worksheet(self.USAGE_LOG_SHEET)
            rows = self.sheets._read_table(ws)
            
            if not date_filter:
                date_filter = date.today().isoformat()
            
            stats = {
                "breaks_used": 0,
                "lunches_used": 0,
                "total_break_minutes": 0,
                "total_lunch_minutes": 0
            }
            
            for row in rows:
                if (row.get("Email", "").lower() == email.lower() and
                    row.get("StartTime", "").startswith(date_filter)):
                    
                    break_type = row.get("BreakType", "")
                    duration = int(row.get("ActualDuration") or row.get("ExpectedDuration") or 0)
                    
                    if break_type == "Перерыв":
                        stats["breaks_used"] += 1
                        stats["total_break_minutes"] += duration
                    elif break_type == "Обед":
                        stats["lunches_used"] += 1
                        stats["total_lunch_minutes"] += duration
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get usage stats: {e}")
            return {}
    
    # =================== МЕТОДЫ ДЛЯ ОБРАТНОЙ СОВМЕСТИМОСТИ ===================
    
    def list_schedule_templates(self) -> List[Dict]:
        """Алиас для list_schedules() (обратная совместимость)"""
        return self.list_schedules()
    
    def get_schedule_template(self, schedule_id: str) -> Optional[BreakSchedule]:
        """Алиас для get_schedule() (обратная совместимость)"""
        return self.get_schedule(schedule_id)
    
    def create_schedule_template(
        self,
        schedule_id: str,
        name: str,
        shift_start: str,
        shift_end: str,
        slots_data: List[Dict]
    ) -> bool:
        """
        Алиас для create_schedule() (обратная совместимость)
        
        Преобразует старый формат slots_data в новый формат limits + windows
        """
        # Группируем слоты по типу
        limits_dict = {}
        windows_list = []
        
        for slot in slots_data:
            # Поддерживаем оба варианта ключей: 'type' (из диалога) и 'slot_type' (старый формат)
            slot_type = slot.get('type') or slot.get('slot_type') or 'Перерыв'
            # duration может быть строкой или числом
            duration_val = slot.get('duration', 15)
            duration = int(duration_val) if isinstance(duration_val, (int, str)) and str(duration_val).isdigit() else 15
            window_start = slot.get('window_start', '09:00')
            window_end = slot.get('window_end', '17:00')
            order_val = slot.get('order', 1)
            order = int(order_val) if isinstance(order_val, (int, str)) and str(order_val).isdigit() else 1
            
            # Лимиты
            if slot_type not in limits_dict:
                limits_dict[slot_type] = {
                    'break_type': slot_type,
                    'daily_count': 0,
                    'time_minutes': duration
                }
            limits_dict[slot_type]['daily_count'] += 1
            
            # Окна
            windows_list.append({
                'break_type': slot_type,
                'start': window_start,
                'end': window_end,
                'priority': order
            })
        
        limits = list(limits_dict.values())
        
        return self.create_schedule(
            schedule_id=schedule_id,
            name=name,
            shift_start=shift_start,
            shift_end=shift_end,
            limits=limits,
            windows=windows_list
        )
    
    def delete_schedule_template(self, schedule_id: str) -> bool:
        """Алиас для delete_schedule() (обратная совместимость)"""
        return self.delete_schedule(schedule_id)
    
    def update_schedule_template(
        self,
        schedule_id: str,
        name: str,
        shift_start: str,
        shift_end: str,
        slots_data: List[Dict]
    ) -> bool:
        """
        Обновляет шаблон графика (обратная совместимость)
        
        Фактически удаляет старый и создаёт новый
        """
        # Для Supabase удаляем по name, так как шаблоны группируются по name
        # Проверяем, является ли это Supabase API
        if hasattr(self.sheets, 'client') and hasattr(self.sheets.client, 'table'):
            # Удаляем по name (в Supabase шаблоны группируются по name)
            result = self.sheets._delete_rows_by_schedule_id("break_schedules", name)
        else:
            # Для Google Sheets удаляем по schedule_id
            result = self.delete_schedule(schedule_id)
        
        if not result:
            logger.warning(f"Failed to delete old schedule {name}, continuing anyway...")
        
        # Сбрасываем кэш
        self._cache.pop(schedule_id, None)
        self._cache.pop(name, None)
        
        # Создаём новый
        return self.create_schedule_template(
            schedule_id=schedule_id,
            name=name,
            shift_start=shift_start,
            shift_end=shift_end,
            slots_data=slots_data
        )
    
    def assign_user_schedule(
        self,
        email: str,
        schedule_id: str,
        admin_email: str
    ) -> bool:
        """Алиас для assign_schedule() (обратная совместимость)"""
        return self.assign_schedule(email, schedule_id, admin_email)
    
    def get_user_assigned_schedule(self, email: str) -> Optional[str]:
        """
        Возвращает ID назначенного графика (обратная совместимость)
        
        Returns:
            schedule_id или None
        """
        schedule = self.get_user_schedule(email)
        return schedule.schedule_id if schedule else None
    
    def unassign_user_schedule(self, email: str) -> bool:
        """Алиас для unassign_schedule() (обратная совместимость)"""
        return self.unassign_schedule(email)
    
    def assign_schedule_to_user(
        self,
        email: str,
        schedule_id: str,
        admin_email: Optional[str] = None
    ) -> bool:
        """Алиас для assign_schedule() (обратная совместимость)"""
        if not admin_email:
            admin_email = "admin@system"
        return self.assign_schedule(email, schedule_id, admin_email)
    
    # =================== МЕТОДЫ ДЛЯ DASHBOARD ===================
    
    def get_all_active_breaks(self) -> List[Dict]:
        """
        Возвращает все активные перерывы (без EndTime) за сегодня (v20.3)
        
        Используется Dashboard для отображения "Сейчас в перерыве"
        
        Returns:
            List[Dict]: Список активных перерывов с полями:
                - Email
                - Name
                - BreakType  
                - StartTime
                - Duration (текущая длительность в минутах)
                - is_over_limit (bool): превышен ли лимит времени
                - is_violator (bool): является ли нарушителем
                - violation_reason (str): причина нарушения (если есть)
        """
        try:
            ws = self.sheets.get_worksheet(self.USAGE_LOG_SHEET)
            rows = self.sheets._read_table(ws)
            
            today = date.today().isoformat()
            
            # Ищем записи без EndTime (активные перерывы могут быть за любую дату)
            active = []
            logger.debug(f"Checking for active breaks. Total rows: {len(rows)}, Today: {today}")
            
            for row in rows:
                end_time = row.get('EndTime') or row.get('end_time') or None
                status = row.get('Status') or row.get('status') or ''
                start_time_str = str(row.get('StartTime') or row.get('start_time') or '')
                
                # Перерыв активен если: нет EndTime (None или пустая строка) И Status = 'Active' (или пустой/None)
                # Проверяем end_time: None, пустая строка, или отсутствует в данных
                has_end_time = end_time is not None and str(end_time).strip() != ''
                is_active_status = status == 'Active' or status == '' or status is None or not status
                is_active = not has_end_time and is_active_status
                
                # Проверяем, что запись за сегодня
                is_today = start_time_str.startswith(today)
                
                logger.debug(f"Row check: email={row.get('Email') or row.get('email')}, "
                           f"start_time={start_time_str}, end_time={end_time}, status={status}, "
                           f"has_end_time={has_end_time}, is_active_status={is_active_status}, "
                           f"is_active={is_active}, is_today={is_today}")
                
                # Включаем только активные перерывы за сегодня
                if is_active and is_today:
                    
                    email = row.get('Email') or row.get('email') or ''
                    break_type = row.get('BreakType') or row.get('break_type') or ''
                    name = row.get('Name') or row.get('name') or ''
                    
                    # Вычисляем текущую длительность
                    duration = 0
                    is_over_limit = False
                    
                    if start_time_str:
                        try:
                            # Поддерживаем разные форматы времени
                            if isinstance(start_time_str, str):
                                # Убираем timezone если есть (для совместимости)
                                start_time_clean = start_time_str.replace('Z', '').split('+')[0].split('.')[0]
                                # Пробуем разные форматы
                                try:
                                    start_dt = datetime.strptime(start_time_clean, "%Y-%m-%d %H:%M:%S")
                                except ValueError:
                                    try:
                                        start_dt = datetime.strptime(start_time_clean, "%Y-%m-%dT%H:%M:%S")
                                    except ValueError:
                                        # Используем fromisoformat как fallback
                                        start_dt = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                            else:
                                start_dt = datetime.fromisoformat(str(start_time_str))
                            duration = int((datetime.now() - start_dt).total_seconds() / 60)
                            
                            # Получаем лимит из графика (или дефолтный)
                            schedule = self.get_user_schedule(email)
                            limit_minutes = 15  # Default для перерыва
                            if break_type == "Обед":
                                limit_minutes = 60
                            
                            # Определяем нарушителя
                            is_violator = False
                            violation_reasons = []
                            
                            # 1. Проверка: нет назначенного шаблона
                            if not schedule:
                                is_violator = True
                                violation_reasons.append("Нет назначенного шаблона")
                            
                            # 2. Проверка: превышено количество слотов за сегодня
                            if schedule:
                                limit = next((l for l in schedule.limits if l.break_type == break_type), None)
                                if limit:
                                    limit_minutes = limit.time_minutes
                                    today_count = self._count_breaks_today(email, break_type)
                                    if today_count > limit.daily_count:
                                        is_violator = True
                                        violation_reasons.append(f"Превышено количество ({today_count}/{limit.daily_count})")
                                
                                # 3. Проверка: перерыв вне временного окна (проверяем время НАЧАЛА перерыва)
                                if schedule.windows:
                                    try:
                                        # Парсим время начала перерыва
                                        start_time_clean = start_time_str.replace('Z', '').split('+')[0].split('.')[0]
                                        try:
                                            start_dt = datetime.strptime(start_time_clean, "%Y-%m-%d %H:%M:%S")
                                        except ValueError:
                                            try:
                                                start_dt = datetime.strptime(start_time_clean, "%Y-%m-%dT%H:%M:%S")
                                            except ValueError:
                                                start_dt = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                                        
                                        break_start_time = start_dt.time()
                                        in_window = False
                                        for window in schedule.windows:
                                            if window.break_type == break_type and window.is_within(break_start_time):
                                                in_window = True
                                                break
                                        if not in_window:
                                            is_violator = True
                                            violation_reasons.append("Перерыв вне временного окна")
                                    except Exception as e:
                                        logger.debug(f"Failed to check time window for {email}: {e}")
                            
                            # 4. Проверка: превышен лимит времени
                            is_over_limit = duration > limit_minutes
                            if is_over_limit:
                                is_violator = True
                                violation_reasons.append(f"Превышен лимит времени ({duration}/{limit_minutes} мин)")
                        except Exception as e:
                            logger.warning(f"Failed to calculate duration for {email}: {e}")
                            is_violator = False
                            violation_reasons = []
                            is_over_limit = False
                    
                    active.append({
                        'Email': email,
                        'Name': name,
                        'BreakType': break_type,
                        'StartTime': start_time_str,
                        'Duration': duration,
                        'is_over_limit': is_over_limit,
                        'is_violator': is_violator,
                        'violation_reason': '; '.join(violation_reasons) if violation_reasons else None
                    })
            
            return active
            
        except Exception as e:
            logger.error(f"Failed to get active breaks: {e}")
            return []
    
    def _cleanup_old_active_breaks(self):
        """
        Автоматически завершает старые активные перерывы (не за сегодня)
        Вызывается при инициализации BreakManager
        """
        try:
            today = date.today().isoformat()
            ws = self.sheets.get_worksheet(self.USAGE_LOG_SHEET)
            rows = self.sheets._read_table(ws)
            
            cleaned_count = 0
            for row in rows:
                end_time = row.get('EndTime') or row.get('end_time') or None
                status = row.get('Status') or row.get('status') or ''
                start_time_str = str(row.get('StartTime') or row.get('start_time') or '')
                
                # Проверяем, что перерыв активен и не за сегодня
                has_end_time = end_time is not None and str(end_time).strip() != ''
                is_active_status = status == 'Active' or status == '' or status is None or not status
                is_active = not has_end_time and is_active_status
                is_today = start_time_str.startswith(today)
                
                if is_active and not is_today:
                    # Старый активный перерыв - завершаем его
                    email = row.get('Email') or row.get('email') or ''
                    break_type = row.get('BreakType') or row.get('break_type') or ''
                    
                    if email and break_type:
                        try:
                            logger.info(f"Auto-cleaning old active break: {email}, {break_type}, start_time={start_time_str}")
                            success, error, duration = self.end_break(email, break_type)
                            if success:
                                cleaned_count += 1
                                logger.info(f"✅ Cleaned old break: {email}, duration={duration} min")
                            else:
                                logger.warning(f"Failed to clean old break for {email}: {error}")
                        except Exception as e:
                            logger.warning(f"Error cleaning old break for {email}: {e}")
            
            if cleaned_count > 0:
                logger.info(f"Cleaned {cleaned_count} old active breaks on startup")
            
        except Exception as e:
            logger.error(f"Error in _cleanup_old_active_breaks: {e}", exc_info=True)


# Тестирование
if __name__ == "__main__":
    print("BreakManager v2.0 loaded")
    print("Key changes:")
    print("  - No more slot_order")
    print("  - General limits (3x15 min breaks, 1x60 min lunch)")
    print("  - Flexible time windows")
    print("  - Violation severity levels")
    print("  - Backward compatible methods added")