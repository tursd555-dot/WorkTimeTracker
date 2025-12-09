"""
Supabase API для WorkTimeTracker - УПРОЩЕННАЯ ВЕРСИЯ
Совместимый интерфейс с sheets_api.py
"""
import os
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, date, timezone
from dataclasses import dataclass

logger = logging.getLogger(__name__)

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    logger.error("supabase library not installed")


# ============================================================================
# EXCEPTION CLASSES
# ============================================================================

class SupabaseAPIError(Exception):
    """
    Исключение для Supabase API ошибок
    Совместимо с SheetsAPIError
    """
    def __init__(self, message: str, is_retryable: bool = False, details: str = None):
        super().__init__(message)
        self.is_retryable = is_retryable
        self.details = details


# Алиас для совместимости
SheetsAPIError = SupabaseAPIError

__all__ = ["SupabaseAPI", "SupabaseAPIError", "SheetsAPIError", "get_supabase_api"]


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
        self.client: Client = create_client(self.config.url, self.config.key)
        
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
        """Заглушка для совместимости"""
        return None
    
    def _get_ws(self, name: str):
        """Заглушка для совместимости"""
        return None
    
    def _read_table(self, worksheet):
        """Заглушка для совместимости"""
        return []
    
    def _request_with_retry(self, func, *args, **kwargs):
        """Выполнить с retry"""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise
    
    def append_row(self, table: str, values: list):
        """Заглушка для append_row"""
        pass
    
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

    def get_user_by_email(self, email: str) -> Optional[Dict[str, str]]:
        """
        Получить пользователя по email
        Совместимо с sheets_api.get_user_by_email
        """
        try:
            email = (email or "").strip().lower()
            if not email:
                return None

            response = self.client.table('users')\
                .select('*')\
                .eq('email', email)\
                .eq('is_active', True)\
                .limit(1)\
                .execute()

            if not response.data:
                logger.info(f"User not found: {email}")
                return None

            row = response.data[0]
            user_data = {
                "email": row.get('email', ''),
                "name": row.get('name', ''),
                "role": row.get('role', 'специалист'),
                "shift_hours": "8 часов",  # Default, можно добавить в БД
                "telegram_login": row.get('telegram_id', ''),
                "group": row.get('group_name', ''),
            }

            logger.info(f"✅ User found: {email}")
            return user_data

        except Exception as e:
            logger.error(f"Failed to lookup user '{email}': {e}")
            raise Exception(f"Failed to lookup user: {e}")

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

    def delete_user(self, email: str) -> bool:
        """
        Удалить пользователя (мягкое удаление - установка is_active = false)
        Совместимо с sheets_api.delete_user

        Returns:
            True если пользователь найден и помечен как неактивный
            False если пользователь не найден
        """
        try:
            email_lower = (email or "").strip().lower()
            if not email_lower:
                logger.warning("delete_user: empty email")
                return False

            # Проверяем существует ли пользователь
            response = self.client.table('users')\
                .select('id, email')\
                .eq('email', email_lower)\
                .execute()

            if not response.data:
                logger.warning(f"delete_user: user not found: {email_lower}")
                return False

            # Мягкое удаление - устанавливаем is_active = false
            update_data = {
                'is_active': False,
                'updated_at': datetime.now(timezone.utc).isoformat()
            }

            self.client.table('users')\
                .update(update_data)\
                .eq('email', email_lower)\
                .execute()

            logger.info(f"User soft-deleted: {email_lower}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete user {email}: {e}")
            return False

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
            response = self.client.table('work_sessions')\
                .select('*')\
                .eq('status', 'active')\
                .execute()
            return response.data
        except:
            return []

    def get_all_active_sessions(self) -> List[Dict]:
        """
        Получить все активные сессии
        Совместимо с sheets_api.get_all_active_sessions
        """
        try:
            # Получаем сессии с именем пользователя через JOIN
            response = self.client.table('work_sessions')\
                .select('*, users(name)')\
                .eq('status', 'active')\
                .execute()

            # Преобразуем в формат совместимый с sheets_api
            sessions = []
            for row in response.data:
                # Получаем имя пользователя из связанной таблицы
                user_name = ''
                if row.get('users') and isinstance(row['users'], dict):
                    user_name = row['users'].get('name', '')

                sessions.append({
                    'Email': row.get('email', ''),
                    'Name': user_name,
                    'SessionID': row.get('session_id', ''),
                    'LoginTime': row.get('login_time', ''),
                    'Status': row.get('status', ''),
                    'Comment': row.get('comment', '')
                })

            return sessions

        except Exception as e:
            logger.error(f"Failed to get all active sessions: {e}")
            return []

    def get_active_session(self, email: str) -> Optional[Dict[str, str]]:
        """
        Получить активную сессию для конкретного пользователя
        Совместимо с sheets_api.get_active_session
        """
        try:
            email_lower = (email or "").strip().lower()
            if not email_lower:
                return None

            # Получаем сессию с именем пользователя через JOIN
            response = self.client.table('work_sessions')\
                .select('*, users(name)')\
                .eq('email', email_lower)\
                .eq('status', 'active')\
                .order('login_time', desc=True)\
                .limit(1)\
                .execute()

            if not response.data:
                return None

            row = response.data[0]

            # Получаем имя пользователя из связанной таблицы
            user_name = ''
            if row.get('users') and isinstance(row['users'], dict):
                user_name = row['users'].get('name', '')

            return {
                'Email': row.get('email', ''),
                'Name': user_name,
                'SessionID': row.get('session_id', ''),
                'LoginTime': row.get('login_time', ''),
                'Status': row.get('status', ''),
                'Comment': row.get('comment', '')
            }

        except Exception as e:
            logger.error(f"Failed to get active session for {email}: {e}")
            return None

    def set_active_session(self, email: str, name: str, session_id: str, login_time: Optional[str] = None) -> bool:
        """
        Установить активную сессию
        Совместимо с sheets_api.set_active_session
        """
        try:
            user = self.client.table('users').select('id').eq('email', email).execute()
            user_id = user.data[0]['id'] if user.data else None

            lt = login_time or datetime.now(timezone.utc).isoformat()

            data = {
                'session_id': session_id,
                'user_id': user_id,
                'email': email,
                'login_time': lt,
                'status': 'active'
            }

            self.client.table('work_sessions').insert(data).execute()
            logger.info(f"✅ Active session set for {email}")
            return True

        except Exception as e:
            logger.error(f"Failed to set active session for {email}: {e}")
            return False

    def check_user_session_status(self, email: str, session_id: str) -> str:
        """
        Проверить статус сессии пользователя
        Возвращает: 'active', 'kicked', 'finished', или 'unknown'
        """
        try:
            response = self.client.table('work_sessions')\
                .select('status')\
                .eq('email', email)\
                .eq('session_id', session_id)\
                .order('login_time', desc=True)\
                .limit(1)\
                .execute()

            if response.data:
                status = response.data[0].get('status', 'unknown')
                return status

            return 'unknown'

        except Exception as e:
            logger.error(f"Failed to check session status: {e}")
            return 'unknown'

    def finish_active_session(
        self,
        email: str,
        session_id: str,
        logout_time: Optional[str] = None,
        reason: str = "user_exit"
    ) -> bool:
        """
        Завершить активную сессию
        Совместимо с sheets_api.finish_active_session
        """
        try:
            lt = logout_time or datetime.now(timezone.utc).isoformat()

            data = {
                'logout_time': lt,
                'logout_type': reason,
                'status': 'finished'
            }

            self.client.table('work_sessions')\
                .update(data)\
                .eq('email', email)\
                .eq('session_id', session_id)\
                .execute()

            logger.info(f"✅ Session finished for {email} (reason: {reason})")
            return True

        except Exception as e:
            logger.error(f"Failed to finish session: {e}")
            return False

    def kick_active_session(
        self,
        email: str,
        session_id: Optional[str] = None,
        status: str = "kicked",
        remote_cmd: str = "FORCE_LOGOUT",
        logout_time: Optional[datetime] = None
    ) -> bool:
        """
        Принудительно завершить активную сессию (kick)
        Совместимо с sheets_api.kick_active_session

        Args:
            email: Email пользователя
            session_id: ID сессии (опционально, если None - берется последняя активная)
            status: Статус для установки (по умолчанию "kicked")
            remote_cmd: Команда для клиента (не используется в Supabase, для совместимости)
            logout_time: Время выхода (если None - текущее время)

        Returns:
            True если сессия была kicked, False если активных сессий не найдено
        """
        try:
            email_lower = (email or "").strip().lower()
            if not email_lower:
                logger.warning("kick_active_session: empty email")
                return False

            # Формируем запрос для поиска активной сессии
            query = self.client.table('work_sessions')\
                .select('*')\
                .eq('email', email_lower)\
                .eq('status', 'active')\
                .order('login_time', desc=True)

            # Если указан session_id, фильтруем по нему
            if session_id:
                query = query.eq('session_id', session_id)

            response = query.limit(1).execute()

            if not response.data:
                logger.warning(f"No active session found for {email_lower}")
                return False

            # Получаем session_id активной сессии
            active_session = response.data[0]
            found_session_id = active_session.get('session_id')

            # Формируем данные для обновления
            lt = logout_time.isoformat() if isinstance(logout_time, datetime) else \
                 (logout_time or datetime.now(timezone.utc).isoformat())

            data = {
                'status': status,
                'logout_time': lt,
                'logout_type': 'forced'  # Используем logout_type вместо remote_command
            }

            # Обновляем сессию
            self.client.table('work_sessions')\
                .update(data)\
                .eq('session_id', found_session_id)\
                .execute()

            logger.info(f"✅ Session kicked for {email_lower} (session_id: {found_session_id})")
            return True

        except Exception as e:
            logger.error(f"Failed to kick active session for {email}: {e}")
            return False

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

    def log_user_actions(self, actions: List[Dict[str, Any]], email: str, user_group: Optional[str] = None) -> bool:
        """
        Залогировать действия пользователя
        Совместимо с sheets_api.log_user_actions
        """
        try:
            if not actions:
                return True

            # Нормализуем email
            email = (email or "").strip().lower()
            if not email and actions:
                email = actions[0].get("email", "").strip().lower()

            # Получаем user_id
            user_response = self.client.table('users').select('id').eq('email', email).execute()
            user_id = user_response.data[0]['id'] if user_response.data else None

            # Подготавливаем данные для вставки
            records = []
            for action in actions:
                record = {
                    'user_id': user_id,
                    'email': action.get('email', email),
                    'name': action.get('name', ''),
                    'timestamp': action.get('timestamp', datetime.now(timezone.utc).isoformat()),
                    'action_type': action.get('action_type', ''),
                    'status': action.get('status', ''),
                    'details': action.get('comment', ''),
                    'session_id': action.get('session_id', '')
                }
                records.append(record)

            # Вставляем batch
            if records:
                self.client.table('work_log').insert(records).execute()
                logger.info(f"✅ Logged {len(records)} actions for {email}")

            return True

        except Exception as e:
            logger.error(f"Failed to log user actions for {email}: {e}")
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
    # BREAK SCHEDULES / TEMPLATES
    # ========================================================================

    def list_schedule_templates(self) -> List[Dict[str, Any]]:
        """
        Получить список всех шаблонов графиков перерывов
        Совместимо с break_manager.list_schedules()

        Returns:
            List of dicts with keys: schedule_id, name, shift_start, shift_end
            (deduplicated by schedule_id)
        """
        try:
            # Получаем все графики
            response = self.client.table('break_schedules')\
                .select('id, name, description, shift_start, shift_end')\
                .eq('is_active', True)\
                .execute()

            if not response.data:
                return []

            # Преобразуем в формат совместимый с break_manager
            templates = []
            for schedule in response.data:
                schedule_id = str(schedule.get('id', ''))
                name = schedule.get('name', '') or schedule.get('description', '')
                shift_start = str(schedule.get('shift_start', ''))
                shift_end = str(schedule.get('shift_end', ''))

                templates.append({
                    'schedule_id': schedule_id,
                    'name': name,
                    'shift_start': shift_start,
                    'shift_end': shift_end
                })

            return templates

        except Exception as e:
            logger.error(f"Failed to list schedule templates: {e}")
            return []

    def create_break_schedule_simple(
        self,
        schedule_id: str,
        name: str,
        shift_start: str,
        shift_end: str,
        limits: List[Dict[str, Any]]
    ) -> bool:
        """
        Создать график перерывов (упрощённая версия)

        Args:
            schedule_id: ID графика (будет использован как name если уникально)
            name: Название графика
            shift_start: Начало смены "09:00"
            shift_end: Конец смены "17:00"
            limits: [{"break_type": "Перерыв", "daily_count": 3, "time_minutes": 15}, ...]

        Returns:
            True если успешно
        """
        try:
            # Создаём график
            schedule_data = {
                'name': f"{schedule_id} - {name}",  # Комбинируем ID и имя
                'description': name,
                'shift_start': shift_start,
                'shift_end': shift_end,
                'is_active': True
            }

            schedule_response = self.client.table('break_schedules')\
                .insert(schedule_data)\
                .execute()

            if not schedule_response.data:
                logger.error("Failed to create break schedule")
                return False

            created_schedule_id = schedule_response.data[0]['id']

            # Создаём лимиты
            for limit in limits:
                limit_data = {
                    'schedule_id': created_schedule_id,
                    'break_type': limit.get('break_type', 'Перерыв'),
                    'duration_minutes': int(limit.get('time_minutes', 15)),
                    'daily_count': int(limit.get('daily_count', 1))
                }

                self.client.table('break_limits')\
                    .insert(limit_data)\
                    .execute()

            logger.info(f"Break schedule created: {schedule_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to create break schedule: {e}")
            return False

    def delete_break_schedule_by_name(self, schedule_name: str) -> bool:
        """
        Удалить график перерывов по ID (для совместимости)

        Args:
            schedule_name: ID графика (UUID)

        Returns:
            True если успешно
        """
        try:
            # schedule_name на самом деле это schedule_id (UUID)
            # Мягкое удаление
            response = self.client.table('break_schedules')\
                .update({'is_active': False})\
                .eq('id', schedule_name)\
                .execute()

            if response.data:
                logger.info(f"Break schedule soft-deleted: {schedule_name}")
                return True
            else:
                logger.warning(f"Break schedule not found: {schedule_name}")
                return False

        except Exception as e:
            logger.error(f"Failed to delete break schedule: {e}")
            return False

    def assign_break_schedule_to_user(
        self,
        email: str,
        schedule_id: str,
        admin_email: str
    ) -> bool:
        """
        Назначить график перерывов пользователю

        Args:
            email: Email пользователя
            schedule_id: ID графика (UUID)
            admin_email: Email администратора

        Returns:
            True если успешно
        """
        try:
            email_lower = (email or "").strip().lower()
            if not email_lower or not schedule_id:
                logger.warning("assign_break_schedule: empty email or schedule_id")
                return False

            # Получаем user_id
            user_response = self.client.table('users')\
                .select('id')\
                .eq('email', email_lower)\
                .eq('is_active', True)\
                .execute()

            if not user_response.data:
                logger.warning(f"User not found: {email_lower}")
                return False

            user_id = user_response.data[0]['id']

            # Проверяем существует ли график
            schedule_response = self.client.table('break_schedules')\
                .select('id')\
                .eq('id', schedule_id)\
                .eq('is_active', True)\
                .execute()

            if not schedule_response.data:
                logger.warning(f"Break schedule not found: {schedule_id}")
                return False

            # Деактивируем старые назначения
            self.client.table('user_break_assignments')\
                .update({'is_active': False})\
                .eq('email', email_lower)\
                .eq('is_active', True)\
                .execute()

            # Создаём новое назначение
            assignment_data = {
                'user_id': user_id,
                'email': email_lower,
                'schedule_id': schedule_id,
                'assigned_by': admin_email,
                'is_active': True
            }

            self.client.table('user_break_assignments')\
                .insert(assignment_data)\
                .execute()

            logger.info(f"Break schedule assigned: {email_lower} -> {schedule_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to assign break schedule: {e}")
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
