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

logger = logging.getLogger(__name__)


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
        """Получает шаблон графика по ID"""
        # Проверяем кэш
        if schedule_id in self._cache:
            return self._cache[schedule_id]
        
        try:
            ws = self.sheets.get_worksheet(self.SCHEDULES_SHEET)
            rows = self.sheets._read_table(ws)
            
            # Фильтруем строки для данного графика
            schedule_rows = [r for r in rows if r.get("ScheduleID") == schedule_id]
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
                    window_start = datetime.strptime(row.get("WindowStart", "09:00"), "%H:%M").time()
                    window_end = datetime.strptime(row.get("WindowEnd", "17:00"), "%H:%M").time()
                    windows.append(BreakWindow(
                        break_type=row.get("SlotType", ""),
                        start_time=window_start,
                        end_time=window_end,
                        priority=int(row.get("Order", "1"))
                    ))
                except:
                    pass
            
            # Создаём объект графика
            schedule = BreakSchedule(
                schedule_id=schedule_id,
                name=first.get("Name", ""),
                shift_start=datetime.strptime(first.get("ShiftStart", "09:00"), "%H:%M").time(),
                shift_end=datetime.strptime(first.get("ShiftEnd", "17:00"), "%H:%M").time(),
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
            
            # Группируем по schedule_id (может быть UUID или строка)
            schedules = {}
            for row in rows:
                # Пробуем разные варианты ключей для schedule_id
                sid = row.get("ScheduleID") or row.get("Id") or row.get("id")
                if sid:
                    sid = str(sid).strip()
                if not sid:
                    continue
                
                if sid not in schedules:
                    schedules[sid] = {
                        "schedule_id": sid,
                        "name": row.get("Name", ""),
                        "shift_start": row.get("ShiftStart", "") or "",
                        "shift_end": row.get("ShiftEnd", "") or ""
                    }
            
            return list(schedules.values())
            
        except Exception as e:
            logger.error(f"Failed to list schedules: {e}")
            return []
    
    def delete_schedule(self, schedule_id: str) -> bool:
        """Удаляет шаблон графика"""
        try:
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
            logger.error(f"Failed to delete schedule: {e}")
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
                return False, f"В вашем графике нет {break_type.lower()}а"
            
            # 3. Проверить дневной лимит
            today_count = self._count_breaks_today(email, break_type)
            quota_exceeded = today_count >= limit.daily_count
            if quota_exceeded:
                # Превышение квоты - критическое нарушение
                # НО разрешаем перерыв (не блокируем пользователя)
                self._log_violation(
                    email=email,
                    session_id=session_id,
                    violation_type=self.VIOLATION_QUOTA_EXCEEDED,
                    severity=self.SEVERITY_CRITICAL,
                    details=f"Превышен дневной лимит {break_type}: {today_count+1}/{limit.daily_count}"
                )
                
                # Отправить уведомление
                try:
                    from shared.break_notifications import send_quota_exceeded_notification
                    send_quota_exceeded_notification(
                        email=email,
                        break_type=break_type,
                        used_count=today_count + 1,
                        limit_count=limit.daily_count
                    )
                except:
                    pass
                
                # НЕ блокируем - продолжаем начинать перерыв
                logger.warning(f"Quota exceeded for {email}, but allowing break (violation logged)")
            
            # 4. Проверить временное окно
            now = datetime.now()
            current_time = now.time()
            in_window = False
            
            for window in schedule.windows:
                if window.break_type == break_type and window.is_within(current_time):
                    in_window = True
                    break
            
            # 5. Логировать начало
            self._log_break_start(
                email=email,
                session_id=session_id,
                break_type=break_type,
                start_time=now,
                limit_minutes=limit.time_minutes,
                in_window=in_window
            )
            
            # 6. Если вне окна - мягкое нарушение (только логируем)
            if not in_window:
                self._log_violation(
                    email=email,
                    session_id=session_id,
                    violation_type=self.VIOLATION_OUT_OF_WINDOW,
                    severity=self.SEVERITY_INFO,
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
            start_time = datetime.fromisoformat(active["StartTime"])
            duration = int((now - start_time).total_seconds() / 60)
            limit = int(active.get("ExpectedDuration", "15"))
            
            # 3. Обновить запись об окончании
            self._update_break_end(
                email=email,
                break_type=break_type,
                end_time=now,
                duration=duration
            )
            
            # 4. Проверить превышение
            overtime = duration - limit
            if overtime > self.OVERTIME_THRESHOLD:
                # Критическое нарушение
                self._log_violation(
                    email=email,
                    session_id=active.get("SessionID"),
                    violation_type=self.VIOLATION_OVER_LIMIT,
                    severity=self.SEVERITY_CRITICAL,
                    details=f"Превышен лимит на {overtime} мин ({duration}/{limit})"
                )
                
                # Отправить уведомления
                try:
                    from shared.break_notifications import send_overtime_notification
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
                    active_break = {
                        "break_type": break_type,
                        "start_time": start_time.strftime("%H:%M"),
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
        """Подсчитывает количество перерывов сегодня"""
        try:
            ws = self.sheets.get_worksheet(self.USAGE_LOG_SHEET)
            rows = self.sheets._read_table(ws)
            
            today = date.today().isoformat()
            
            count = 0
            for row in rows:
                if (row.get("Email", "").lower() == email.lower() and
                    row.get("BreakType") == break_type and
                    row.get("StartTime", "").startswith(today)):
                    count += 1
            
            return count
            
        except Exception as e:
            logger.error(f"Failed to count breaks: {e}")
            return 0
    
    def _get_active_break(self, email: str, break_type: str) -> Optional[Dict]:
        """Получает активный перерыв (без EndTime) за сегодня"""
        try:
            ws = self.sheets.get_worksheet(self.USAGE_LOG_SHEET)
            rows = self.sheets._read_table(ws)
            
            today = date.today().isoformat()
            
            # Ищем с конца (самый последний активный перерыв)
            for row in reversed(rows):
                if (row.get("Email", "").lower() == email.lower() and
                    row.get("BreakType") == break_type and
                    not row.get("EndTime") and
                    row.get("StartTime", "").startswith(today)):  # Только сегодня!
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
            
            self.sheets._request_with_retry(lambda: ws.append_row(row))
            logger.info(f"✅ Break logged to BreakLog: {email}, {break_type}")
            
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
            logger.error(f"Failed to update break end: {e}")
    
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
            
            self.sheets._request_with_retry(lambda: ws.append_row(row))
            
            logger.warning(f"Violation logged: {email}, {violation_type}, {severity}")
            
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
            
            if date_from:
                # Для дат без времени сравниваем первые 10 символов
                if len(date_from) == 10:  # Формат YYYY-MM-DD
                    filtered = [r for r in filtered if r.get("Timestamp", "")[:10] >= date_from]
                else:
                    filtered = [r for r in filtered if r.get("Timestamp", "") >= date_from]
            
            if date_to:
                # Для date_to используем <= только если указано время
                if len(date_to) == 10:  # Формат YYYY-MM-DD
                    # Включаем весь день
                    filtered = [r for r in filtered if r.get("Timestamp", "")[:10] <= date_to]
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
            slot_type = slot.get('slot_type', 'Перерыв')
            duration = slot.get('duration', 15)
            window_start = slot.get('window_start', '09:00')
            window_end = slot.get('window_end', '17:00')
            order = slot.get('order', 1)
            
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
        # Удаляем старый
        self.delete_schedule(schedule_id)
        
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
                - is_over_limit (bool): превышен ли лимит
        """
        try:
            ws = self.sheets.get_worksheet(self.USAGE_LOG_SHEET)
            rows = self.sheets._read_table(ws)
            
            today = date.today().isoformat()
            
            # Ищем записи без EndTime за сегодня
            active = []
            for row in rows:
                if (not row.get('EndTime') and 
                    row.get('StartTime', '').startswith(today)):
                    
                    email = row.get('Email')
                    break_type = row.get('BreakType')
                    start_time_str = row.get('StartTime')
                    
                    # Вычисляем текущую длительность
                    duration = 0
                    is_over_limit = False
                    
                    if start_time_str:
                        try:
                            start_dt = datetime.fromisoformat(start_time_str)
                            duration = int((datetime.now() - start_dt).total_seconds() / 60)
                            
                            # Получаем лимит из графика (или дефолтный)
                            schedule = self.get_user_schedule(email)
                            limit_minutes = 15  # Default для перерыва
                            if break_type == "Обед":
                                limit_minutes = 60
                            
                            if schedule:
                                limit = next((l for l in schedule.limits if l.break_type == break_type), None)
                                if limit:
                                    limit_minutes = limit.time_minutes
                            
                            is_over_limit = duration > limit_minutes
                        except Exception as e:
                            logger.warning(f"Failed to calculate duration for {email}: {e}")
                    
                    active.append({
                        'Email': email,
                        'Name': row.get('Name', ''),
                        'BreakType': break_type,
                        'StartTime': start_time_str,
                        'Duration': duration,
                        'is_over_limit': is_over_limit
                    })
            
            return active
            
        except Exception as e:
            logger.error(f"Failed to get active breaks: {e}")
            return []


# Тестирование
if __name__ == "__main__":
    print("BreakManager v2.0 loaded")
    print("Key changes:")
    print("  - No more slot_order")
    print("  - General limits (3x15 min breaks, 1x60 min lunch)")
    print("  - Flexible time windows")
    print("  - Violation severity levels")
    print("  - Backward compatible methods added")