# admin_app/break_manager_supabase.py
"""
Менеджер системы перерывов v2.1 для Supabase

Унифицированный менеджер, работающий с Supabase.
Совместимый интерфейс с оригинальным BreakManager для Google Sheets.
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
    priority: int = 1

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


class BreakManagerSupabase:
    """
    Менеджер системы перерывов v2.1 для Supabase

    Полностью совместим с оригинальным BreakManager,
    но работает через Supabase API.
    """

    def __init__(self, api):
        """
        Args:
            api: SupabaseAPI instance
        """
        self.api = api
        self.sheets = api  # Совместимость с break_analytics_tab и другими модулями
        self._cache: Dict[str, BreakSchedule] = {}

        # Импорт настроек
        try:
            from config import (
                BREAK_OVERTIME_THRESHOLD,
                VIOLATION_TYPE_OUT_OF_WINDOW,
                VIOLATION_TYPE_OVER_LIMIT,
                VIOLATION_TYPE_QUOTA_EXCEEDED,
                SEVERITY_INFO,
                SEVERITY_WARNING,
                SEVERITY_CRITICAL,
                BREAK_LIMIT_MINUTES,
                LUNCH_LIMIT_MINUTES
            )
            self.OVERTIME_THRESHOLD = BREAK_OVERTIME_THRESHOLD
            self.VIOLATION_OUT_OF_WINDOW = VIOLATION_TYPE_OUT_OF_WINDOW
            self.VIOLATION_OVER_LIMIT = VIOLATION_TYPE_OVER_LIMIT
            self.VIOLATION_QUOTA_EXCEEDED = VIOLATION_TYPE_QUOTA_EXCEEDED
            self.SEVERITY_INFO = SEVERITY_INFO
            self.SEVERITY_WARNING = SEVERITY_WARNING
            self.SEVERITY_CRITICAL = SEVERITY_CRITICAL
            self.DEFAULT_BREAK_LIMIT = BREAK_LIMIT_MINUTES
            self.DEFAULT_LUNCH_LIMIT = LUNCH_LIMIT_MINUTES
        except ImportError as e:
            logger.warning(f"Failed to import config: {e}, using defaults")
            self.OVERTIME_THRESHOLD = 2
            self.VIOLATION_OUT_OF_WINDOW = "OUT_OF_WINDOW"
            self.VIOLATION_OVER_LIMIT = "OVER_LIMIT"
            self.VIOLATION_QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
            self.SEVERITY_INFO = "INFO"
            self.SEVERITY_WARNING = "WARNING"
            self.SEVERITY_CRITICAL = "CRITICAL"
            self.DEFAULT_BREAK_LIMIT = 15
            self.DEFAULT_LUNCH_LIMIT = 60

        logger.info("BreakManagerSupabase initialized")

    # =================== УПРАВЛЕНИЕ ШАБЛОНАМИ ===================

    def create_schedule(
        self,
        schedule_id: str,
        name: str,
        shift_start: str,
        shift_end: str,
        limits: List[Dict],
        windows: List[Dict] = None
    ) -> bool:
        """Создаёт новый шаблон графика"""
        try:
            # Создаём график
            new_schedule_id = self.api.create_break_schedule(
                name=name,
                description=f"Schedule ID: {schedule_id}",
                shift_start=shift_start,
                shift_end=shift_end
            )

            if not new_schedule_id:
                return False

            # Создаём лимиты
            for limit in limits:
                self.api.create_break_limit(
                    schedule_id=new_schedule_id,
                    break_type=limit.get('break_type', 'Перерыв'),
                    duration_minutes=limit.get('time_minutes', 15),
                    daily_count=limit.get('daily_count', 3)
                )

            # Сбрасываем кэш
            self._cache.pop(schedule_id, None)

            logger.info(f"Created schedule {name} with id {new_schedule_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to create schedule: {e}", exc_info=True)
            return False

    def get_schedule(self, schedule_id: str) -> Optional[BreakSchedule]:
        """Получает шаблон графика по ID"""
        if schedule_id in self._cache:
            return self._cache[schedule_id]

        try:
            schedule_data = self.api.get_break_schedule_by_id(schedule_id)
            if not schedule_data:
                # Пробуем найти по имени
                schedule_data = self.api.get_break_schedule_by_name(schedule_id)

            if not schedule_data:
                return None

            # Получаем лимиты
            limits_data = self.api.get_break_limits(schedule_data['id'])
            limits = []
            for l in limits_data:
                limits.append(BreakLimit(
                    break_type=l.get('break_type', 'Перерыв'),
                    daily_count=l.get('daily_count', 3),
                    time_minutes=l.get('duration_minutes', 15)
                ))

            # Если нет лимитов - используем дефолтные
            if not limits:
                limits = [
                    BreakLimit('Перерыв', 3, self.DEFAULT_BREAK_LIMIT),
                    BreakLimit('Обед', 1, self.DEFAULT_LUNCH_LIMIT)
                ]

            # Парсим время смены
            shift_start = time(9, 0)
            shift_end = time(18, 0)
            if schedule_data.get('shift_start'):
                try:
                    shift_start = datetime.strptime(str(schedule_data['shift_start']), "%H:%M:%S").time()
                except:
                    pass
            if schedule_data.get('shift_end'):
                try:
                    shift_end = datetime.strptime(str(schedule_data['shift_end']), "%H:%M:%S").time()
                except:
                    pass

            schedule = BreakSchedule(
                schedule_id=schedule_data['id'],
                name=schedule_data.get('name', ''),
                shift_start=shift_start,
                shift_end=shift_end,
                limits=limits,
                windows=[]  # Окна не используются в упрощённой версии
            )

            self._cache[schedule_id] = schedule
            return schedule

        except Exception as e:
            logger.error(f"Failed to get schedule {schedule_id}: {e}", exc_info=True)
            return None

    def list_schedules(self) -> List[Dict]:
        """Возвращает список всех шаблонов"""
        try:
            schedules = self.api.get_break_schedules()
            return [{
                'schedule_id': s['id'],
                'name': s.get('name', ''),
                'shift_start': str(s.get('shift_start', '')),
                'shift_end': str(s.get('shift_end', ''))
            } for s in schedules]
        except Exception as e:
            logger.error(f"Failed to list schedules: {e}")
            return []

    def delete_schedule(self, schedule_id: str) -> bool:
        """Удаляет шаблон графика"""
        try:
            result = self.api.delete_break_schedule(schedule_id)
            self._cache.pop(schedule_id, None)
            return result
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
            return self.api.assign_break_schedule(
                email=email,
                schedule_id=schedule_id,
                assigned_by=admin_email
            )
        except Exception as e:
            logger.error(f"Failed to assign schedule: {e}")
            return False

    def get_user_schedule(self, email: str) -> Optional[BreakSchedule]:
        """Получает назначенный график пользователя"""
        try:
            assignment = self.api.get_user_break_assignment(email)
            if not assignment:
                return None

            schedule_id = assignment.get('schedule_id')
            if not schedule_id:
                return None

            return self.get_schedule(schedule_id)

        except Exception as e:
            logger.error(f"Failed to get user schedule: {e}")
            return None

    def unassign_schedule(self, email: str) -> bool:
        """Удаляет назначение графика"""
        return self.api.unassign_break_schedule(email)

    # =================== ИСПОЛЬЗОВАНИЕ ПЕРЕРЫВОВ ===================

    def start_break(
        self,
        email: str,
        break_type: str,
        session_id: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Начинает перерыв/обед

        Returns:
            (success, error_message)
        """
        try:
            # 1. Получить лимиты (из графика или дефолтные)
            schedule = self.get_user_schedule(email)

            if schedule:
                limit = next((l for l in schedule.limits if l.break_type == break_type), None)
            else:
                # Используем дефолтные лимиты
                default_limits = self._get_default_limits()
                limit = next((l for l in default_limits if l.break_type == break_type), None)

            if not limit:
                logger.warning(f"No limit found for {break_type}, using defaults")
                limit = BreakLimit(
                    break_type=break_type,
                    daily_count=3 if break_type == "Перерыв" else 1,
                    time_minutes=self.DEFAULT_BREAK_LIMIT if break_type == "Перерыв" else self.DEFAULT_LUNCH_LIMIT
                )

            # 2. Проверить дневной лимит
            today_count = self.api.count_breaks_today(email, break_type)
            quota_exceeded = today_count >= limit.daily_count

            if quota_exceeded:
                # Логируем нарушение, но разрешаем перерыв
                self._log_violation(
                    email=email,
                    violation_type=self.VIOLATION_QUOTA_EXCEEDED,
                    break_type=break_type,
                    details=f"Превышен дневной лимит {break_type}: {today_count+1}/{limit.daily_count}"
                )

                # Отправляем уведомление
                try:
                    from shared.break_notifications import send_quota_exceeded_notification
                    send_quota_exceeded_notification(
                        email=email,
                        break_type=break_type,
                        used_count=today_count + 1,
                        limit_count=limit.daily_count
                    )
                except Exception as e:
                    logger.warning(f"Failed to send notification: {e}")

                logger.warning(f"Quota exceeded for {email}, but allowing break")

            # 3. Получить имя пользователя
            try:
                users = self.api.get_users()
                user = next((u for u in users if u.get('Email', '').lower() == email.lower()), None)
                name = user.get('Name', '') if user else ''
            except:
                name = ''

            # 4. Записать начало перерыва
            break_id = self.api.start_break_extended(
                email=email,
                name=name,
                break_type=break_type,
                session_id=session_id or '',
                expected_duration=limit.time_minutes
            )

            if not break_id:
                return False, "Не удалось записать начало перерыва"

            logger.info(f"✅ Break started: {email}, {break_type}")
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

        Returns:
            (success, error_message, actual_duration)
        """
        try:
            # 1. Завершить перерыв в БД
            result = self.api.end_break_extended(email, break_type)

            if not result:
                return False, "Активный перерыв не найден", None

            duration = result.get('duration', 0)
            break_id = result.get('id')

            # 2. Получить лимит
            schedule = self.get_user_schedule(email)
            if schedule:
                limit_obj = next((l for l in schedule.limits if l.break_type == break_type), None)
                limit = limit_obj.time_minutes if limit_obj else self.DEFAULT_BREAK_LIMIT
            else:
                limit = self.DEFAULT_BREAK_LIMIT if break_type == "Перерыв" else self.DEFAULT_LUNCH_LIMIT

            # 3. Проверить превышение
            overtime = duration - limit
            if overtime > self.OVERTIME_THRESHOLD:
                # Помечаем перерыв как превысивший лимит
                self.api.mark_break_over_limit(break_id)

                # Логируем нарушение
                self._log_violation(
                    email=email,
                    violation_type=self.VIOLATION_OVER_LIMIT,
                    break_type=break_type,
                    expected_duration=limit,
                    actual_duration=duration,
                    details=f"Превышен лимит на {overtime} мин ({duration}/{limit})"
                )

                # Отправляем уведомление
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
                    logger.warning(f"Failed to send notification: {e}")

            logger.info(f"✅ Break ended: {email}, {break_type}, duration={duration}")
            return True, None, duration

        except Exception as e:
            logger.error(f"Failed to end break: {e}", exc_info=True)
            return False, f"Ошибка: {str(e)}", None

    def get_break_status(self, email: str) -> Dict:
        """
        Получает текущий статус перерывов пользователя

        Returns:
            {
                "schedule": {"name": "...", ...} or None,
                "limits": {"Перерыв": {"count": 3, "time": 15}, ...},
                "used_today": {"Перерыв": 2, "Обед": 0},
                "active_break": {...} or None
            }
        """
        try:
            # Используем метод из API
            status = self.api.get_user_break_status(email)

            # Если нет графика, добавляем сообщение
            if not status.get('schedule'):
                status['schedule'] = {
                    'name': 'Дефолтный график',
                    'schedule_id': 'default'
                }

            return status

        except Exception as e:
            logger.error(f"Failed to get break status: {e}")
            # Возвращаем дефолтный статус вместо пустого словаря
            return {
                'schedule': {'name': 'Дефолтный график', 'schedule_id': 'default'},
                'limits': {
                    'Перерыв': {'count': 3, 'time': self.DEFAULT_BREAK_LIMIT},
                    'Обед': {'count': 1, 'time': self.DEFAULT_LUNCH_LIMIT}
                },
                'used_today': {'Перерыв': 0, 'Обед': 0},
                'active_break': None
            }

    # =================== DASHBOARD МЕТОДЫ ===================

    def get_all_active_breaks(self) -> List[Dict]:
        """
        Возвращает все активные перерывы за сегодня
        Используется Dashboard для отображения "Сейчас в перерыве"
        """
        try:
            active = self.api.get_all_active_breaks_today()

            result = []
            for row in active:
                email = row.get('email', '')
                break_type = row.get('break_type', 'Перерыв')
                duration = row.get('current_duration', 0)

                # Получаем лимит для проверки превышения
                schedule = self.get_user_schedule(email)
                if schedule:
                    limit_obj = next((l for l in schedule.limits if l.break_type == break_type), None)
                    limit = limit_obj.time_minutes if limit_obj else 15
                else:
                    limit = self.DEFAULT_BREAK_LIMIT if break_type == "Перерыв" else self.DEFAULT_LUNCH_LIMIT

                result.append({
                    'Email': email,
                    'Name': row.get('name', ''),
                    'BreakType': break_type,
                    'StartTime': row.get('start_time', ''),
                    'Duration': duration,
                    'is_over_limit': duration > limit
                })

            return result

        except Exception as e:
            logger.error(f"Failed to get active breaks: {e}")
            return []

    # =================== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ===================

    def _get_default_limits(self) -> List[BreakLimit]:
        """Возвращает дефолтные лимиты"""
        return [
            BreakLimit('Перерыв', 3, self.DEFAULT_BREAK_LIMIT),
            BreakLimit('Обед', 1, self.DEFAULT_LUNCH_LIMIT)
        ]

    def _log_violation(
        self,
        email: str,
        violation_type: str,
        break_type: str = None,
        expected_duration: int = None,
        actual_duration: int = None,
        details: str = ""
    ):
        """Логирует нарушение"""
        try:
            # Получаем имя пользователя
            try:
                users = self.api.get_users()
                user = next((u for u in users if u.get('Email', '').lower() == email.lower()), None)
                name = user.get('Name', '') if user else ''
            except:
                name = ''

            self.api.log_violation(
                email=email,
                name=name,
                violation_type=violation_type,
                break_type=break_type,
                expected_duration=expected_duration,
                actual_duration=actual_duration,
                details=details
            )
        except Exception as e:
            logger.error(f"Failed to log violation: {e}")

    # =================== ОТЧЁТЫ И АНАЛИТИКА ===================

    def get_violations_report(
        self,
        email: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        violation_type: Optional[str] = None
    ) -> List[Dict]:
        """Получает отчёт по нарушениям"""
        return self.api.get_violations(
            email=email,
            date_from=date_from,
            date_to=date_to,
            violation_type=violation_type
        )

    def get_usage_stats(
        self,
        email: str,
        date_filter: Optional[str] = None
    ) -> Dict:
        """Получает статистику использования перерывов"""
        try:
            usage = self.api.get_break_usage_today(email)
            return {
                'breaks_used': usage.get('Перерыв', {}).get('count', 0),
                'lunches_used': usage.get('Обед', {}).get('count', 0),
                'total_break_minutes': usage.get('Перерыв', {}).get('total_minutes', 0),
                'total_lunch_minutes': usage.get('Обед', {}).get('total_minutes', 0)
            }
        except Exception as e:
            logger.error(f"Failed to get usage stats: {e}")
            return {}

    # =================== МЕТОДЫ ДЛЯ ОБРАТНОЙ СОВМЕСТИМОСТИ ===================

    def list_schedule_templates(self) -> List[Dict]:
        """Алиас для list_schedules()"""
        return self.list_schedules()

    def get_schedule_template(self, schedule_id: str) -> Optional[BreakSchedule]:
        """Алиас для get_schedule()"""
        return self.get_schedule(schedule_id)

    def assign_user_schedule(self, email: str, schedule_id: str, admin_email: str) -> bool:
        """Алиас для assign_schedule()"""
        return self.assign_schedule(email, schedule_id, admin_email)

    def get_user_assigned_schedule(self, email: str) -> Optional[str]:
        """Возвращает ID назначенного графика"""
        schedule = self.get_user_schedule(email)
        return schedule.schedule_id if schedule else None

    def unassign_user_schedule(self, email: str) -> bool:
        """Алиас для unassign_schedule()"""
        return self.unassign_schedule(email)

    def assign_schedule_to_user(self, email: str, schedule_id: str, admin_email: Optional[str] = None) -> bool:
        """Алиас для assign_schedule()"""
        return self.assign_schedule(email, schedule_id, admin_email or "admin@system")

    def create_schedule_template(
        self,
        schedule_id: str,
        name: str,
        shift_start: str,
        shift_end: str,
        slots_data: List[Dict]
    ) -> bool:
        """
        Создаёт шаблон графика (обратная совместимость с Google Sheets версией)

        Преобразует старый формат slots_data в новый формат limits
        """
        try:
            # Группируем слоты по типу для создания лимитов
            limits_dict = {}

            for slot in slots_data:
                slot_type = slot.get('slot_type', 'Перерыв')
                duration = slot.get('duration', 15)

                if slot_type not in limits_dict:
                    limits_dict[slot_type] = {
                        'break_type': slot_type,
                        'daily_count': 0,
                        'time_minutes': duration
                    }
                limits_dict[slot_type]['daily_count'] += 1

            limits = list(limits_dict.values())

            return self.create_schedule(
                schedule_id=schedule_id,
                name=name,
                shift_start=shift_start,
                shift_end=shift_end,
                limits=limits
            )

        except Exception as e:
            logger.error(f"Failed to create schedule template: {e}", exc_info=True)
            return False

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

    def delete_schedule_template(self, schedule_id: str) -> bool:
        """Алиас для delete_schedule() (обратная совместимость)"""
        return self.delete_schedule(schedule_id)


# ============================================================================
# ФАБРИКА ДЛЯ СОЗДАНИЯ МЕНЕДЖЕРА
# ============================================================================

def get_break_manager(api=None):
    """
    Фабричный метод для получения правильного BreakManager

    Автоматически определяет тип API и возвращает соответствующий менеджер.
    """
    if api is None:
        try:
            from api_adapter import get_sheets_api
            api = get_sheets_api()
        except ImportError:
            from supabase_api import get_supabase_api
            api = get_supabase_api()

    # Проверяем тип API
    api_class_name = type(api).__name__

    if 'Supabase' in api_class_name:
        return BreakManagerSupabase(api)
    else:
        # Для Google Sheets используем оригинальный менеджер
        from admin_app.break_manager import BreakManager
        return BreakManager(api)


if __name__ == "__main__":
    print("BreakManagerSupabase v2.1 loaded")
    print("Use get_break_manager() to automatically select the right manager")
