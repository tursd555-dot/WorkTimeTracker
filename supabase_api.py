"""
Supabase API для WorkTimeTracker - УПРОЩЕННАЯ ВЕРСИЯ
Совместимый интерфейс с sheets_api.py
"""
import os
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, date, timezone
from dataclasses import dataclass

# Загружаем переменные окружения из .env файла
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv не установлен

logger = logging.getLogger(__name__)

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    logger.error("supabase library not installed")

__all__ = ["SupabaseAPI", "get_supabase_api"]


@dataclass
class SupabaseConfig:
    """Конфигурация Supabase"""
    url: str
    key: str

    @classmethod
    def from_env(cls):
        """Загрузка из переменных окружения"""
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")

        if not url or not key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_KEY must be set in environment variables"
            )

        return cls(url=url, key=key)


class WorksheetWrapper:
    """Обёртка для имитации worksheet объекта Google Sheets"""

    def __init__(self, worksheet_name: str, api_instance):
        self.name = worksheet_name
        self._api = api_instance

    def append_row(self, values: list, value_input_option: str = 'USER_ENTERED'):
        """Добавляет строку в таблицу"""
        return self._api.append_row(self.name, values, value_input_option)

    def get_all_values(self):
        """Получает все значения из таблицы"""
        rows = self._api._read_table(self.name)
        if not rows:
            return []

        # Конвертируем словари в списки значений
        if rows and isinstance(rows[0], dict):
            # Получаем порядок колонок из первой строки
            headers = list(rows[0].keys())
            result = [headers]  # Первая строка - заголовки
            for row in rows:
                result.append([row.get(h, '') for h in headers])
            return result
        return rows


class SupabaseClientWrapper:
    """Обёртка для Supabase Client для совместимости с Google Sheets API"""

    def __init__(self, supabase_client):
        self._client = supabase_client

    def open(self, spreadsheet_name: str):
        """Заглушка для совместимости с gspread.client.open()"""
        logger.debug(f"client.open() called for {spreadsheet_name} - Supabase doesn't use spreadsheets")
        return self  # Возвращаем себя для цепочки вызовов

    def worksheets(self):
        """Заглушка для совместимости"""
        return []

    def worksheet(self, name: str):
        """Заглушка для совместимости"""
        logger.debug(f"client.worksheet() called for {name} - not supported in Supabase")
        return None

    def add_worksheet(self, **kwargs):
        """Заглушка для совместимости"""
        logger.debug("client.add_worksheet() not supported in Supabase")
        return None

    def __getattr__(self, name):
        """Проксируем все остальные атрибуты к реальному Supabase client"""
        return getattr(self._client, name)


class SupabaseAPI:
    """
    API для работы с Supabase
    Совместимый интерфейс с SheetsAPI
    """

    def __init__(self, config: Optional[SupabaseConfig] = None):
        """Инициализация"""
        if not SUPABASE_AVAILABLE:
            raise ImportError("supabase library not installed")

        self.config = config or SupabaseConfig.from_env()
        real_client = create_client(self.config.url, self.config.key)

        # Оборачиваем клиент для совместимости
        self.client = SupabaseClientWrapper(real_client)

        logger.info(f"✅ Supabase API initialized: {self.config.url}")
    
    # ========================================================================
    # COMPATIBILITY METHODS (для совместимости с sheets_api)
    # ========================================================================
    
    def check_credentials(self) -> bool:
        """Проверка credentials"""
        try:
            self.client.table('users').select('id').limit(1).execute()
            return True
        except:
            return False
    
    def get_worksheet(self, name: str):
        """Возвращает worksheet wrapper для совместимости с sheets_api"""
        return WorksheetWrapper(name, self)

    def _get_ws(self, name: str):
        """Возвращает имя листа для совместимости с sheets_api"""
        return name
    
    def _read_table(self, worksheet):
        """Читает данные из таблицы (для совместимости с sheets_api)"""
        # worksheet может быть WorksheetWrapper или строкой
        if not worksheet:
            return []

        # Если передан WorksheetWrapper, извлекаем имя
        worksheet_name = worksheet.name if isinstance(worksheet, WorksheetWrapper) else worksheet

        # Маппинг имён листов Google Sheets на таблицы Supabase
        table_mapping = {
            'Users': 'users',
            'ActiveSessions': 'active_sessions',
            'BreakLog': 'break_log',
            'BreakUsageLog': 'break_log',
            'BreakSchedules': 'break_schedules',
            'UserBreakAssignments': 'user_break_assignments',
            'BreakViolations': 'break_violations',
            'Violations': 'violations',  # v20.3: renamed sheet
            'Groups': 'groups',
            'WorkLog': 'work_log',
        }

        # Если worksheet - это строка (имя листа), используем маппинг
        table_name = table_mapping.get(worksheet_name, worksheet_name)

        try:
            response = self.client.table(table_name).select('*').execute()
            data = response.data or []

            # Преобразуем snake_case ключи в PascalCase для совместимости
            return self._normalize_keys(data, table_name)
        except Exception as e:
            logger.error(f"Failed to read table {table_name}: {e}")
            return []

    def _normalize_keys(self, data: List[Dict], table_name: str) -> List[Dict]:
        """Преобразует ключи из snake_case в PascalCase для совместимости"""
        if not data:
            return []

        # Маппинг ключей для разных таблиц
        key_mappings = {
            'users': {
                'email': 'Email',
                'name': 'Name',
                'phone': 'Phone',
                'role': 'Role',
                'telegram_id': 'Telegram',
                'group_name': 'Group',
                'notify_telegram': 'NotifyTelegram',
                'shift_hours': 'ShiftHours',
            },
            'active_sessions': {
                'email': 'Email',
                'name': 'Name',
                'session_id': 'SessionID',
                'login_time': 'LoginTime',
                'logout_time': 'LogoutTime',
                'status': 'Status',
            },
            'break_log': {
                'email': 'Email',
                'name': 'Name',
                'break_type': 'BreakType',
                'start_time': 'StartTime',
                'end_time': 'EndTime',
                'date': 'Date',
                'status': 'Status',
                'session_id': 'SessionID',
            },
            'break_schedules': {
                'schedule_id': 'ScheduleID',
                'name': 'Name',
                'shift_start': 'ShiftStart',
                'shift_end': 'ShiftEnd',
                'break_type': 'BreakType',
                'time_minutes': 'TimeMinutes',
                'window_start': 'WindowStart',
                'window_end': 'WindowEnd',
                'priority': 'Priority',
            },
            'user_break_assignments': {
                'email': 'Email',
                'schedule_id': 'ScheduleID',
                'effective_date': 'EffectiveDate',
                'assigned_by': 'AssignedBy',
            },
            'violations': {
                'timestamp': 'Timestamp',
                'email': 'Email',
                'name': 'Name',
                'violation_type': 'ViolationType',
                'break_type': 'BreakType',
                'expected_duration': 'ExpectedDuration',
                'actual_duration': 'ActualDuration',
                'excess_minutes': 'ExcessMinutes',
                'date': 'Date',
                'details': 'Details',
            },
            'groups': {
                'group_name': 'Group',
                'description': 'Description',
            },
        }

        mapping = key_mappings.get(table_name, {})

        normalized = []
        for row in data:
            new_row = {}
            for old_key, value in row.items():
                # Используем маппинг или оставляем как есть
                new_key = mapping.get(old_key, old_key)
                new_row[new_key] = value
            normalized.append(new_row)

        return normalized
    
    def _request_with_retry(self, func, *args, **kwargs):
        """Выполнить с retry"""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise
    
    def append_row(self, worksheet, values: list, value_input_option: str = 'USER_ENTERED'):
        """Добавляет строку в таблицу (для совместимости с sheets_api)"""
        if not worksheet or not values:
            return

        # Если передан WorksheetWrapper, извлекаем имя
        worksheet_name = worksheet.name if isinstance(worksheet, WorksheetWrapper) else worksheet

        # Маппинг имён листов на таблицы
        table_mapping = {
            'Users': 'users',
            'ActiveSessions': 'active_sessions',
            'BreakLog': 'break_log',
            'BreakUsageLog': 'break_log',
            'BreakSchedules': 'break_schedules',
            'UserBreakAssignments': 'user_break_assignments',
            'BreakViolations': 'break_violations',
            'Violations': 'violations',  # v20.3: renamed sheet
            'Groups': 'groups',
            'WorkLog': 'work_log',
        }

        table_name = table_mapping.get(worksheet_name, worksheet_name)

        try:
            # Получаем заголовки таблицы для маппинга позиций
            # Для каждой таблицы определяем порядок колонок
            column_mappings = {
                'break_log': ['email', 'name', 'break_type', 'start_time', 'end_time', 'date', 'status', 'session_id'],
                'violations': ['email', 'name', 'violation_type', 'break_type', 'timestamp', 'expected_duration', 'actual_duration', 'excess_minutes', 'date', 'details'],
                'break_schedules': ['name', 'shift_start', 'shift_end', 'description'],
                'break_limits': ['schedule_id', 'break_type', 'duration_minutes', 'daily_count'],
                'break_windows': ['schedule_id', 'break_type', 'window_start', 'window_end', 'priority'],
                'user_break_assignments': ['email', 'schedule_id', 'assigned_by'],
                'work_log': ['email', 'name', 'timestamp', 'action_type', 'status', 'details', 'session_id'],
                'active_sessions': ['email', 'name', 'session_id', 'login_time', 'status'],
            }

            columns = column_mappings.get(table_name, [])
            if not columns:
                logger.warning(f"No column mapping for table {table_name}")
                return

            # Создаём словарь из values
            data = {}
            for i, value in enumerate(values):
                if i < len(columns):
                    data[columns[i]] = value

            # Для таблиц с user_id - получаем ID пользователя по email
            if table_name in ['break_log', 'work_log', 'violations'] and 'email' in data:
                email = data.get('email', '').strip().lower()
                if email:
                    try:
                        user_response = self.client.table('users')\
                            .select('id')\
                            .eq('email', email)\
                            .execute()

                        if user_response.data:
                            data['user_id'] = user_response.data[0]['id']
                            logger.debug(f"Added user_id for email {email}")
                    except Exception as e:
                        logger.warning(f"Failed to get user_id for {email}: {e}")
                        # Продолжаем без user_id (будет NULL)

            # Вставляем данные
            self.client.table(table_name).insert(data).execute()
            logger.debug(f"Appended row to {table_name}: {data}")

        except Exception as e:
            logger.error(f"Failed to append row to {table_name}: {e}")
            raise
    
    # ========================================================================
    # USERS
    # ========================================================================
    
    def get_users(self) -> List[Dict[str, str]]:
        """Получить всех пользователей"""
        try:
            response = self.client.table('users')\
                .select('*')\
                .eq('is_active', True)\
                .execute()
            
            users = []
            for row in response.data:
                users.append({
                    'Email': row.get('email', ''),
                    'Name': row.get('name', ''),
                    'Phone': row.get('phone', ''),
                    'Role': row.get('role', ''),
                    'Telegram': row.get('telegram_id', ''),
                    'Group': row.get('group_name', ''),
                    'NotifyTelegram': 'Yes' if row.get('notify_telegram') else 'No'
                })
            
            return users
            
        except Exception as e:
            logger.error(f"Failed to get users: {e}")
            return []
    
    def upsert_user(self, user: Dict[str, str]) -> None:
        """Добавить или обновить пользователя"""
        email = user.get('Email')
        if not email:
            raise ValueError("Email is required")
        
        data = {
            'email': email,
            'name': user.get('Name', ''),
            'phone': user.get('Phone', ''),
            'role': user.get('Role', ''),
            'telegram_id': user.get('Telegram', ''),
            'group_name': user.get('Group', ''),
            'notify_telegram': user.get('NotifyTelegram', 'No').lower() == 'yes',
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
        
        try:
            existing = self.client.table('users')\
                .select('id')\
                .eq('email', email)\
                .execute()
            
            if existing.data:
                self.client.table('users').update(data).eq('email', email).execute()
            else:
                data['created_at'] = datetime.now(timezone.utc).isoformat()
                self.client.table('users').insert(data).execute()
                
        except Exception as e:
            logger.error(f"Failed to upsert user {email}: {e}")
            raise
    
    # ========================================================================
    # WORK SESSIONS
    # ========================================================================
    
    def start_session(self, email: str, session_id: str, comment: str = ""):
        """Начать рабочую сессию"""
        user = self.client.table('users').select('id').eq('email', email).execute()
        user_id = user.data[0]['id'] if user.data else None
        
        data = {
            'session_id': session_id,
            'user_id': user_id,
            'email': email,
            'login_time': datetime.now(timezone.utc).isoformat(),
            'status': 'active',
            'comment': comment
        }
        
        self.client.table('work_sessions').insert(data).execute()
    
    def end_session(self, session_id: str, logout_type: str = "manual"):
        """Завершить рабочую сессию"""
        data = {
            'logout_time': datetime.now(timezone.utc).isoformat(),
            'logout_type': logout_type,
            'status': 'completed'
        }
        
        self.client.table('work_sessions').update(data).eq('session_id', session_id).execute()
    
    def get_active_sessions(self) -> List[Dict]:
        """Получить активные сессии"""
        try:
            response = self.client.table('active_sessions').select('*').execute()
            return response.data
        except:
            return []
    
    # ========================================================================
    # WORK LOG
    # ========================================================================
    
    def log_action(self, email: str, name: str, action_type: str, 
                   status: str = "", details: str = "", session_id: str = ""):
        """Записать действие в лог"""
        user = self.client.table('users').select('id').eq('email', email).execute()
        user_id = user.data[0]['id'] if user.data else None
        
        data = {
            'user_id': user_id,
            'email': email,
            'name': name,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'action_type': action_type,
            'status': status,
            'details': details,
            'session_id': session_id
        }
        
        try:
            self.client.table('work_log').insert(data).execute()
        except Exception as e:
            logger.error(f"Failed to log action: {e}")

    # ========================================================================
    # BREAK SCHEDULES
    # ========================================================================

    def create_break_schedule(
        self,
        name: str,
        shift_start: str,
        shift_end: str,
        description: str = ""
    ) -> Optional[str]:
        """
        Создает график перерывов

        Returns:
            UUID графика или None если ошибка
        """
        try:
            data = {
                'name': name,
                'description': description,
                'shift_start': shift_start,
                'shift_end': shift_end,
                'is_active': True
            }

            response = self.client.table('break_schedules').insert(data).execute()

            if response.data:
                schedule_id = response.data[0]['id']
                logger.info(f"Created break schedule: {name} (ID: {schedule_id})")
                return str(schedule_id)

            return None

        except Exception as e:
            logger.error(f"Failed to create break schedule: {e}")
            return None

    def create_break_limit(
        self,
        schedule_id: str,
        break_type: str,
        duration_minutes: int,
        daily_count: int
    ) -> bool:
        """Создает лимит перерывов для графика"""
        try:
            data = {
                'schedule_id': schedule_id,
                'break_type': break_type,
                'duration_minutes': duration_minutes,
                'daily_count': daily_count
            }

            self.client.table('break_limits').insert(data).execute()
            logger.debug(f"Created break limit for schedule {schedule_id}: {break_type}, {duration_minutes}min")
            return True

        except Exception as e:
            logger.error(f"Failed to create break limit: {e}")
            return False

    def create_break_window(
        self,
        schedule_id: str,
        break_type: str,
        window_start: str,
        window_end: str,
        priority: int = 1
    ) -> bool:
        """Создает временное окно для перерывов"""
        try:
            data = {
                'schedule_id': schedule_id,
                'break_type': break_type,
                'window_start': window_start,
                'window_end': window_end,
                'priority': priority
            }

            self.client.table('break_windows').insert(data).execute()
            logger.debug(f"Created break window for schedule {schedule_id}: {break_type}, {window_start}-{window_end}")
            return True

        except Exception as e:
            logger.error(f"Failed to create break window: {e}")
            return False

    def get_break_schedule(self, schedule_id: str) -> Optional[Dict]:
        """Получает график перерывов с лимитами и окнами"""
        try:
            # Получаем основную информацию
            schedule = self.client.table('break_schedules')\
                .select('*')\
                .eq('id', schedule_id)\
                .execute()

            if not schedule.data:
                return None

            result = schedule.data[0]

            # Получаем лимиты
            limits = self.client.table('break_limits')\
                .select('*')\
                .eq('schedule_id', schedule_id)\
                .execute()

            result['limits'] = limits.data or []

            # Получаем окна
            windows = self.client.table('break_windows')\
                .select('*')\
                .eq('schedule_id', schedule_id)\
                .execute()

            result['windows'] = windows.data or []

            return result

        except Exception as e:
            logger.error(f"Failed to get break schedule: {e}")
            return None

    def delete_break_schedule(self, schedule_id: str) -> bool:
        """Удаляет график перерывов (каскадно удаляет лимиты и окна)"""
        try:
            self.client.table('break_schedules').delete().eq('id', schedule_id).execute()
            logger.info(f"Deleted break schedule: {schedule_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete break schedule: {e}")
            return False

    # ========================================================================
    # BREAK LOG
    # ========================================================================
    
    def start_break(self, email: str, name: str, break_type: str, session_id: str = "") -> str:
        """Начать перерыв"""
        user = self.client.table('users').select('id').eq('email', email).execute()
        user_id = user.data[0]['id'] if user.data else None
        
        data = {
            'user_id': user_id,
            'email': email,
            'name': name,
            'break_type': break_type,
            'start_time': datetime.now(timezone.utc).isoformat(),
            'date': date.today().isoformat(),
            'status': 'Active',
            'session_id': session_id
        }
        
        response = self.client.table('break_log').insert(data).execute()
        return str(response.data[0]['id'])
    
    def end_break(self, break_id: str):
        """Завершить перерыв"""
        data = {
            'end_time': datetime.now(timezone.utc).isoformat(),
            'status': 'Completed'
        }
        
        self.client.table('break_log').update(data).eq('id', break_id).execute()
    
    def get_active_breaks(self) -> List[Dict]:
        """Получить активные перерывы"""
        try:
            response = self.client.table('active_breaks').select('*').execute()
            return response.data
        except:
            return []

    # ========================================================================
    # USER LOOKUP (для совместимости с sheets_api)
    # ========================================================================

    def get_user_by_email(self, email: str) -> Optional[Dict[str, str]]:
        """Получить пользователя по email"""
        try:
            response = self.client.table('users')\
                .select('*')\
                .eq('email', email.strip().lower())\
                .eq('is_active', True)\
                .execute()

            if not response.data:
                return None

            row = response.data[0]
            return {
                'email': row.get('email', ''),
                'name': row.get('name', ''),
                'role': row.get('role', ''),
                'shift_hours': row.get('shift_hours', 8),
                'telegram_login': row.get('telegram_id', ''),
                'group': row.get('group_name', ''),
                'phone': row.get('phone', ''),
            }

        except Exception as e:
            logger.error(f"Failed to get user by email {email}: {e}")
            return None

    # ========================================================================
    # ACTIVE SESSIONS (для совместимости с sheets_api)
    # ========================================================================

    def get_all_active_sessions(self) -> List[Dict[str, str]]:
        """Получить все активные сессии"""
        try:
            response = self.client.table('active_sessions').select('*').execute()

            sessions = []
            for row in response.data:
                sessions.append({
                    'Email': row.get('email', ''),
                    'Name': row.get('name', ''),
                    'SessionID': row.get('session_id', ''),
                    'LoginTime': row.get('login_time', ''),
                    'Status': row.get('status', ''),
                    'LogoutTime': row.get('logout_time', ''),
                })

            return sessions

        except Exception as e:
            logger.error(f"Failed to get all active sessions: {e}")
            return []

    def get_active_session(self, email: str) -> Optional[Dict[str, str]]:
        """Получить активную сессию для пользователя"""
        email_lower = (email or "").strip().lower()
        for row in self.get_all_active_sessions():
            if (row.get("Email", "") or "").strip().lower() == email_lower and \
               (row.get("Status", "") or "").strip().lower() == "active":
                return row
        return None

    def set_active_session(self, email: str, name: str, session_id: str, login_time: Optional[str] = None) -> bool:
        """Создать активную сессию"""
        try:
            data = {
                'email': email.strip().lower(),
                'name': name,
                'session_id': session_id,
                'login_time': login_time or datetime.now(timezone.utc).isoformat(),
                'status': 'active',
            }

            self.client.table('work_sessions').insert(data).execute()
            return True

        except Exception as e:
            logger.error(f"Failed to set active session: {e}")
            return False

    def finish_active_session(
        self,
        email: str,
        session_id: str,
        logout_time: Optional[str] = None,
        reason: str = "user_exit"
    ) -> bool:
        """Завершить активную сессию"""
        try:
            data = {
                'status': 'finished',
                'logout_time': logout_time or datetime.now(timezone.utc).isoformat(),
            }

            self.client.table('work_sessions')\
                .update(data)\
                .eq('email', email.strip().lower())\
                .eq('session_id', session_id)\
                .execute()

            return True

        except Exception as e:
            logger.error(f"Failed to finish active session: {e}")
            return False

    def check_user_session_status(self, email: str, session_id: str) -> str:
        """Проверить статус сессии пользователя"""
        try:
            response = self.client.table('active_sessions')\
                .select('status')\
                .eq('email', email.strip().lower())\
                .eq('session_id', session_id)\
                .execute()

            if response.data:
                return response.data[0].get('status', 'unknown')

            return 'unknown'

        except Exception as e:
            logger.error(f"Failed to check session status: {e}")
            return 'unknown'

    # ========================================================================
    # WORK LOG (для совместимости с sheets_api)
    # ========================================================================

    def log_user_actions(self, actions: List[Dict[str, Any]], email: str, user_group: Optional[str] = None) -> bool:
        """Записать действия пользователя в лог"""
        try:
            user = self.client.table('users').select('id').eq('email', email.strip().lower()).execute()
            user_id = user.data[0]['id'] if user.data else None

            for action in actions:
                data = {
                    'user_id': user_id,
                    'email': email.strip().lower(),
                    'name': action.get('name', ''),
                    'timestamp': action.get('timestamp', datetime.now(timezone.utc).isoformat()),
                    'action_type': action.get('action_type', ''),
                    'status': action.get('status', ''),
                    'details': action.get('comment', ''),
                    'session_id': action.get('session_id', ''),
                }

                self.client.table('work_log').insert(data).execute()

            return True

        except Exception as e:
            logger.error(f"Failed to log user actions: {e}")
            return False


# ============================================================================
# SINGLETON
# ============================================================================

_supabase_api_instance: Optional[SupabaseAPI] = None


def get_supabase_api() -> SupabaseAPI:
    """Получить глобальный экземпляр SupabaseAPI (singleton)"""
    global _supabase_api_instance
    
    if _supabase_api_instance is None:
        _supabase_api_instance = SupabaseAPI()
    
    return _supabase_api_instance


if __name__ == "__main__":
    print("Supabase API Simple Module")
    api = get_supabase_api()
    users = api.get_users()
    print(f"✅ Loaded {len(users)} users")
