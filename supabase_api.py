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
        """Быстрый поиск пользователя по email"""
        try:
            em = (email or "").strip().lower()
            response = self.client.table('users')\
                .select('*')\
                .eq('email', em)\
                .limit(1)\
                .execute()

            if not response.data:
                return None

            row = response.data[0]
            return {
                "email": em,
                "name": row.get('name', ''),
                "role": row.get('role', 'специалист'),
                "shift_hours": row.get('shift_hours', '8 часов'),
                "telegram_login": row.get('telegram_id', ''),
                "group": row.get('group_name', ''),
            }
        except Exception as e:
            logger.error(f"User lookup failed for '{email}': {e}")
            return None

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
        """Удалить пользователя (soft delete - is_active=False)"""
        try:
            em = (email or "").strip().lower()
            # Soft delete - помечаем как неактивного
            self.client.table('users')\
                .update({'is_active': False, 'updated_at': datetime.now(timezone.utc).isoformat()})\
                .eq('email', em)\
                .execute()
            logger.info(f"✅ User deleted: {em}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete user {email}: {e}")
            return False

    def update_user_fields(self, email: str, fields: Dict[str, Any]) -> None:
        """Обновить отдельные поля пользователя"""
        try:
            em = (email or "").strip().lower()

            # Маппинг полей из sheets формата в supabase
            data = {'updated_at': datetime.now(timezone.utc).isoformat()}
            field_map = {
                'Name': 'name',
                'Phone': 'phone',
                'Role': 'role',
                'Telegram': 'telegram_id',
                'Group': 'group_name',
                'NotifyTelegram': 'notify_telegram'
            }

            for key, value in fields.items():
                supabase_key = field_map.get(key, key.lower())
                if supabase_key == 'notify_telegram':
                    data[supabase_key] = str(value).lower() in ('yes', 'true', '1', 'да')
                else:
                    data[supabase_key] = value

            self.client.table('users').update(data).eq('email', em).execute()
            logger.info(f"✅ User fields updated: {em}")
        except Exception as e:
            logger.error(f"Failed to update user fields for {email}: {e}")
            raise

    def list_worksheet_titles(self) -> List[str]:
        """Заглушка для совместимости с sheets_api"""
        # В Supabase нет листов, возвращаем имена таблиц
        return ['users', 'work_sessions', 'work_log', 'break_log', 'break_schedules']

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
        Получить все активные сессии (совместимость с sheets_api)

        Returns:
            List с полями Email, Status, SessionID, LoginTime для совместимости
        """
        try:
            response = self.client.table('work_sessions')\
                .select('*')\
                .eq('status', 'active')\
                .execute()

            # Маппинг в формат sheets_api (с заглавными буквами)
            result = []
            for row in response.data:
                result.append({
                    'Email': row.get('email', ''),
                    'Status': 'active',  # Всегда active, т.к. фильтруем по этому статусу
                    'SessionID': row.get('session_id', ''),
                    'LoginTime': row.get('login_time', ''),
                    'Name': row.get('name', '')
                })
            return result
        except Exception as e:
            logger.error(f"Failed to get all active sessions: {e}")
            return []

    def get_active_session(self, email: str) -> Optional[Dict]:
        """Получить активную сессию по email"""
        try:
            em = (email or "").strip().lower()
            response = self.client.table('work_sessions')\
                .select('*')\
                .eq('email', em)\
                .eq('status', 'active')\
                .order('login_time', desc=True)\
                .limit(1)\
                .execute()

            if not response.data:
                return None

            row = response.data[0]
            return {
                'Email': row.get('email', ''),
                'SessionID': row.get('session_id', ''),
                'LoginTime': row.get('login_time', ''),
                'Status': row.get('status', ''),
                'Name': row.get('name', '')
            }
        except Exception as e:
            logger.error(f"Failed to get active session for {email}: {e}")
            return None

    def set_active_session(self, email: str, name: str, session_id: str, login_time: str):
        """Записать активную сессию (алиас для start_session)"""
        try:
            logger.info(f"📝 Creating session: email={email}, session_id={session_id}")

            user = self.client.table('users').select('id').eq('email', email.lower()).execute()
            user_id = user.data[0]['id'] if user.data else None

            data = {
                'session_id': session_id,
                'user_id': user_id,
                'email': email.lower(),
                'login_time': login_time,
                'status': 'active'
            }

            result = self.client.table('work_sessions').insert(data).execute()
            logger.info(f"✅ Active session created for {email}: session_id={session_id}, db_id={result.data[0].get('id') if result.data else 'unknown'}")
        except Exception as e:
            logger.error(f"Failed to set active session for {email}: {e}")

    def finish_active_session(self, email: str, session_id: str, logout_time: str):
        """Завершить активную сессию"""
        try:
            data = {
                'logout_time': logout_time,
                'status': 'completed'
            }

            # Обновляем по session_id если есть, иначе по email
            if session_id:
                self.client.table('work_sessions')\
                    .update(data)\
                    .eq('session_id', session_id)\
                    .execute()
            else:
                self.client.table('work_sessions')\
                    .update(data)\
                    .eq('email', email.lower())\
                    .eq('status', 'active')\
                    .execute()

            logger.info(f"✅ Session finished for {email}")
        except Exception as e:
            logger.error(f"Failed to finish session for {email}: {e}")

    def check_user_session_status(self, email: str, session_id: str) -> str:
        """Проверить статус сессии пользователя"""
        try:
            logger.debug(f"🔍 Checking session status: email={email}, session_id={session_id}")

            # Сначала пробуем найти по session_id
            response = self.client.table('work_sessions')\
                .select('id, session_id, email, status, login_time')\
                .eq('session_id', session_id)\
                .limit(1)\
                .execute()

            if response.data:
                row = response.data[0]
                status = row.get('status', 'unknown')
                logger.info(f"📊 Session found by session_id: id={row.get('id')}, status={status}, email={row.get('email')}")
                if status in ('kicked', 'finished'):
                    logger.info(f"🚨 Session {session_id} has status: {status}")
                return status

            # Если не нашли по session_id, пробуем по email (последняя активная)
            logger.warning(f"⚠️ No session found for session_id={session_id}, trying by email={email}")

            response2 = self.client.table('work_sessions')\
                .select('id, session_id, email, status, login_time')\
                .eq('email', email.lower())\
                .order('login_time', desc=True)\
                .limit(1)\
                .execute()

            if response2.data:
                row = response2.data[0]
                status = row.get('status', 'unknown')
                logger.info(f"📊 Session found by email: id={row.get('id')}, session_id={row.get('session_id')}, status={status}")
                if status in ('kicked', 'finished'):
                    logger.info(f"🚨 Session for {email} has status: {status}")
                return status

            logger.warning(f"❌ No session found for email={email} at all")
            return 'unknown'
        except Exception as e:
            logger.error(f"Failed to check session status for {email}/{session_id}: {e}")
            return 'unknown'

    def kick_active_session(self, email: str, logout_time: str = None) -> bool:
        """
        Принудительно завершить активную сессию пользователя (force logout)

        Args:
            email: Email пользователя
            logout_time: Время разлогина (ISO формат)

        Returns:
            True если сессия найдена и завершена, False если не найдена
        """
        try:
            em = (email or "").strip().lower()
            if not logout_time:
                logout_time = datetime.now(timezone.utc).isoformat()

            # Проверяем есть ли активная сессия
            check = self.client.table('work_sessions')\
                .select('id, session_id')\
                .eq('email', em)\
                .eq('status', 'active')\
                .execute()

            if not check.data:
                logger.info(f"No active session found for {em}")
                return False

            # Завершаем все активные сессии пользователя
            data = {
                'logout_time': logout_time,
                'logout_type': 'force',
                'status': 'kicked'  # gui.py проверяет 'kicked' или 'finished'
            }

            # Логируем какие сессии будем обновлять
            session_ids = [s.get('session_id') for s in check.data]
            logger.info(f"🔄 Updating sessions to 'kicked': {session_ids}")

            result = self.client.table('work_sessions')\
                .update(data)\
                .eq('email', em)\
                .eq('status', 'active')\
                .execute()

            logger.info(f"✅ Force logout completed for {em}, updated {len(result.data)} sessions")
            return True

        except Exception as e:
            logger.error(f"Failed to kick session for {email}: {e}")
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

    def log_user_actions(self, actions: List[Dict], email: str, user_group: str = "") -> bool:
        """
        Записать список действий пользователя в work_log

        Args:
            actions: Список словарей с действиями
            email: Email пользователя
            user_group: Группа пользователя

        Returns:
            True если успешно, False если ошибка
        """
        try:
            user = self.client.table('users').select('id').eq('email', email.lower()).execute()
            user_id = user.data[0]['id'] if user.data else None

            for action in actions:
                data = {
                    'user_id': user_id,
                    'email': action.get('email', email).lower(),
                    'name': action.get('name', ''),
                    'timestamp': action.get('timestamp', datetime.now(timezone.utc).isoformat()),
                    'action_type': action.get('action_type', ''),
                    'status': action.get('status', ''),
                    'details': action.get('comment', '') or action.get('details', ''),
                    'session_id': action.get('session_id', '')
                }

                self.client.table('work_log').insert(data).execute()

            logger.info(f"✅ Logged {len(actions)} actions for {email}")
            return True
        except Exception as e:
            logger.error(f"Failed to log user actions: {e}")
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
    # BREAK SCHEDULES (Графики перерывов)
    # ========================================================================

    def get_break_schedules(self) -> List[Dict]:
        """Получить все графики перерывов"""
        try:
            response = self.client.table('break_schedules')\
                .select('*')\
                .eq('is_active', True)\
                .execute()
            return response.data
        except Exception as e:
            logger.error(f"Failed to get break schedules: {e}")
            return []

    def get_break_schedule_by_id(self, schedule_id: str) -> Optional[Dict]:
        """Получить график по ID"""
        try:
            response = self.client.table('break_schedules')\
                .select('*')\
                .eq('id', schedule_id)\
                .execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Failed to get schedule {schedule_id}: {e}")
            return None

    def get_break_schedule_by_name(self, name: str) -> Optional[Dict]:
        """Получить график по названию"""
        try:
            response = self.client.table('break_schedules')\
                .select('*')\
                .eq('name', name)\
                .eq('is_active', True)\
                .execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Failed to get schedule by name {name}: {e}")
            return None

    def create_break_schedule(self, name: str, description: str = "",
                              shift_start: str = None, shift_end: str = None,
                              created_by: str = "") -> Optional[str]:
        """Создать новый график перерывов"""
        try:
            data = {
                'name': name,
                'description': description,
                'shift_start': shift_start,
                'shift_end': shift_end,
                'created_by': created_by,
                'is_active': True
            }
            response = self.client.table('break_schedules').insert(data).execute()
            return str(response.data[0]['id']) if response.data else None
        except Exception as e:
            logger.error(f"Failed to create schedule: {e}")
            return None

    def delete_break_schedule(self, schedule_id: str) -> bool:
        """Удалить график (мягкое удаление)"""
        try:
            self.client.table('break_schedules')\
                .update({'is_active': False})\
                .eq('id', schedule_id)\
                .execute()
            return True
        except Exception as e:
            logger.error(f"Failed to delete schedule: {e}")
            return False

    # ========================================================================
    # BREAK LIMITS (Лимиты перерывов)
    # ========================================================================

    def get_break_limits(self, schedule_id: str) -> List[Dict]:
        """Получить лимиты для графика"""
        try:
            response = self.client.table('break_limits')\
                .select('*')\
                .eq('schedule_id', schedule_id)\
                .execute()
            return response.data
        except Exception as e:
            logger.error(f"Failed to get break limits: {e}")
            return []

    def create_break_limit(self, schedule_id: str, break_type: str,
                           duration_minutes: int, daily_count: int) -> bool:
        """Создать лимит для графика"""
        try:
            data = {
                'schedule_id': schedule_id,
                'break_type': break_type,
                'duration_minutes': duration_minutes,
                'daily_count': daily_count
            }
            self.client.table('break_limits').insert(data).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to create break limit: {e}")
            return False

    def get_default_limits(self) -> List[Dict]:
        """Получить дефолтные лимиты (из Default Schedule или config)"""
        try:
            # Пробуем найти дефолтный график
            default_schedule = self.get_break_schedule_by_name('Default Schedule')
            if default_schedule:
                limits = self.get_break_limits(default_schedule['id'])
                if limits:
                    return limits

            # Возвращаем хардкод дефолты
            return [
                {'break_type': 'Перерыв', 'duration_minutes': 15, 'daily_count': 3},
                {'break_type': 'Обед', 'duration_minutes': 60, 'daily_count': 1}
            ]
        except Exception as e:
            logger.error(f"Failed to get default limits: {e}")
            return [
                {'break_type': 'Перерыв', 'duration_minutes': 15, 'daily_count': 3},
                {'break_type': 'Обед', 'duration_minutes': 60, 'daily_count': 1}
            ]

    # ========================================================================
    # USER BREAK ASSIGNMENTS (Назначение графиков)
    # ========================================================================

    def get_user_break_assignment(self, email: str) -> Optional[Dict]:
        """Получить назначенный график пользователя"""
        try:
            response = self.client.table('user_break_assignments')\
                .select('*, break_schedules(*)')\
                .eq('email', email.lower())\
                .eq('is_active', True)\
                .execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Failed to get user assignment for {email}: {e}")
            return None

    def assign_break_schedule(self, email: str, schedule_id: str,
                              assigned_by: str = "") -> bool:
        """Назначить график пользователю"""
        try:
            # Получаем user_id
            user = self.client.table('users').select('id').eq('email', email.lower()).execute()
            user_id = user.data[0]['id'] if user.data else None

            # Деактивируем предыдущие назначения
            self.client.table('user_break_assignments')\
                .update({'is_active': False})\
                .eq('email', email.lower())\
                .execute()

            # Создаем новое назначение
            data = {
                'user_id': user_id,
                'email': email.lower(),
                'schedule_id': schedule_id,
                'assigned_by': assigned_by,
                'is_active': True
            }
            self.client.table('user_break_assignments').insert(data).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to assign schedule to {email}: {e}")
            return False

    def unassign_break_schedule(self, email: str) -> bool:
        """Снять назначение графика"""
        try:
            self.client.table('user_break_assignments')\
                .update({'is_active': False})\
                .eq('email', email.lower())\
                .execute()
            return True
        except Exception as e:
            logger.error(f"Failed to unassign schedule from {email}: {e}")
            return False

    # ========================================================================
    # BREAK LOG (Расширенные методы)
    # ========================================================================

    def start_break_extended(self, email: str, name: str, break_type: str,
                             session_id: str = "", expected_duration: int = None) -> Optional[str]:
        """Начать перерыв (расширенная версия)"""
        try:
            user = self.client.table('users').select('id').eq('email', email.lower()).execute()
            user_id = user.data[0]['id'] if user.data else None

            data = {
                'user_id': user_id,
                'email': email.lower(),
                'name': name,
                'break_type': break_type,
                'start_time': datetime.now(timezone.utc).isoformat(),
                'date': date.today().isoformat(),
                'status': 'Active',
                'session_id': session_id,
                'is_over_limit': False
            }

            response = self.client.table('break_log').insert(data).execute()
            logger.info(f"✅ Break started for {email}: {break_type}")
            return str(response.data[0]['id']) if response.data else None
        except Exception as e:
            logger.error(f"Failed to start break for {email}: {e}")
            return None

    def end_break_extended(self, email: str, break_type: str) -> Optional[Dict]:
        """Завершить активный перерыв (расширенная версия)"""
        try:
            # Находим активный перерыв
            today = date.today().isoformat()
            response = self.client.table('break_log')\
                .select('*')\
                .eq('email', email.lower())\
                .eq('break_type', break_type)\
                .eq('status', 'Active')\
                .eq('date', today)\
                .order('start_time', desc=True)\
                .limit(1)\
                .execute()

            if not response.data:
                logger.warning(f"No active break found for {email}")
                return None

            break_record = response.data[0]
            break_id = break_record['id']
            start_time = datetime.fromisoformat(break_record['start_time'].replace('Z', '+00:00'))
            end_time = datetime.now(timezone.utc)
            duration = int((end_time - start_time).total_seconds() / 60)

            # Обновляем запись
            update_data = {
                'end_time': end_time.isoformat(),
                'duration_minutes': duration,
                'status': 'Completed'
            }

            self.client.table('break_log')\
                .update(update_data)\
                .eq('id', break_id)\
                .execute()

            logger.info(f"✅ Break ended for {email}: {break_type}, duration={duration}min")
            return {
                'id': break_id,
                'duration': duration,
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to end break for {email}: {e}")
            return None

    def get_active_break_for_user(self, email: str, break_type: str = None) -> Optional[Dict]:
        """Получить активный перерыв пользователя"""
        try:
            today = date.today().isoformat()
            query = self.client.table('break_log')\
                .select('*')\
                .eq('email', email.lower())\
                .eq('status', 'Active')\
                .eq('date', today)

            if break_type:
                query = query.eq('break_type', break_type)

            response = query.order('start_time', desc=True).limit(1).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Failed to get active break for {email}: {e}")
            return None

    def count_breaks_today(self, email: str, break_type: str) -> int:
        """Подсчитать количество перерывов сегодня"""
        try:
            today = date.today().isoformat()
            response = self.client.table('break_log')\
                .select('id', count='exact')\
                .eq('email', email.lower())\
                .eq('break_type', break_type)\
                .eq('date', today)\
                .execute()
            return response.count or 0
        except Exception as e:
            logger.error(f"Failed to count breaks for {email}: {e}")
            return 0

    def get_all_active_breaks_today(self) -> List[Dict]:
        """Получить все активные перерывы за сегодня (для Dashboard)"""
        try:
            today = date.today().isoformat()
            response = self.client.table('break_log')\
                .select('*')\
                .eq('status', 'Active')\
                .eq('date', today)\
                .execute()

            # Вычисляем текущую длительность для каждого
            result = []
            now = datetime.now(timezone.utc)
            for row in response.data:
                start_time = datetime.fromisoformat(row['start_time'].replace('Z', '+00:00'))
                duration = int((now - start_time).total_seconds() / 60)
                row['current_duration'] = duration
                result.append(row)

            return result
        except Exception as e:
            logger.error(f"Failed to get all active breaks: {e}")
            return []

    def get_break_usage_today(self, email: str) -> Dict:
        """Получить использование перерывов за сегодня"""
        try:
            today = date.today().isoformat()
            response = self.client.table('break_log')\
                .select('*')\
                .eq('email', email.lower())\
                .eq('date', today)\
                .execute()

            usage = {
                'Перерыв': {'count': 0, 'total_minutes': 0},
                'Обед': {'count': 0, 'total_minutes': 0}
            }

            for row in response.data:
                break_type = row.get('break_type', '')
                if break_type in usage:
                    usage[break_type]['count'] += 1
                    usage[break_type]['total_minutes'] += row.get('duration_minutes') or 0

            return usage
        except Exception as e:
            logger.error(f"Failed to get break usage for {email}: {e}")
            return {'Перерыв': {'count': 0, 'total_minutes': 0},
                    'Обед': {'count': 0, 'total_minutes': 0}}

    def mark_break_over_limit(self, break_id: str) -> bool:
        """Пометить перерыв как превысивший лимит"""
        try:
            self.client.table('break_log')\
                .update({'is_over_limit': True})\
                .eq('id', break_id)\
                .execute()
            return True
        except Exception as e:
            logger.error(f"Failed to mark break over limit: {e}")
            return False

    # ========================================================================
    # VIOLATIONS (Нарушения)
    # ========================================================================

    def log_violation(self, email: str, name: str, violation_type: str,
                      break_type: str = None, expected_duration: int = None,
                      actual_duration: int = None, details: str = "") -> bool:
        """Записать нарушение"""
        try:
            user = self.client.table('users').select('id').eq('email', email.lower()).execute()
            user_id = user.data[0]['id'] if user.data else None

            excess = (actual_duration - expected_duration) if (actual_duration and expected_duration) else None

            data = {
                'user_id': user_id,
                'email': email.lower(),
                'name': name,
                'violation_type': violation_type,
                'break_type': break_type,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'expected_duration': expected_duration,
                'actual_duration': actual_duration,
                'excess_minutes': excess,
                'date': date.today().isoformat(),
                'details': details
            }

            self.client.table('violations').insert(data).execute()
            logger.warning(f"⚠️ Violation logged for {email}: {violation_type}")
            return True
        except Exception as e:
            logger.error(f"Failed to log violation: {e}")
            return False

    def get_violations(self, email: str = None, date_from: str = None,
                       date_to: str = None, violation_type: str = None) -> List[Dict]:
        """Получить нарушения с фильтрацией"""
        try:
            query = self.client.table('violations').select('*')

            if email:
                query = query.eq('email', email.lower())
            if date_from:
                query = query.gte('date', date_from)
            if date_to:
                query = query.lte('date', date_to)
            if violation_type:
                query = query.eq('violation_type', violation_type)

            response = query.order('timestamp', desc=True).execute()
            return response.data
        except Exception as e:
            logger.error(f"Failed to get violations: {e}")
            return []

    def get_violations_today(self) -> List[Dict]:
        """Получить все нарушения за сегодня"""
        today = date.today().isoformat()
        return self.get_violations(date_from=today, date_to=today)

    # ========================================================================
    # BREAK STATUS (Полный статус для пользователя)
    # ========================================================================

    def get_user_break_status(self, email: str) -> Dict:
        """
        Получить полный статус перерывов пользователя

        Returns:
            {
                'schedule': {'id': ..., 'name': ..., ...} or None,
                'limits': {'Перерыв': {'count': 3, 'time': 15}, 'Обед': {...}},
                'used_today': {'Перерыв': 1, 'Обед': 0},
                'active_break': {...} or None
            }
        """
        try:
            result = {
                'schedule': None,
                'limits': {},
                'used_today': {'Перерыв': 0, 'Обед': 0},
                'active_break': None
            }

            # 1. Получить назначенный график
            assignment = self.get_user_break_assignment(email)
            if assignment and 'break_schedules' in assignment:
                schedule = assignment['break_schedules']
                result['schedule'] = {
                    'id': schedule.get('id'),
                    'name': schedule.get('name'),
                    'schedule_id': schedule.get('id')  # для совместимости
                }

                # Получить лимиты из назначенного графика
                limits = self.get_break_limits(schedule['id'])
                for limit in limits:
                    result['limits'][limit['break_type']] = {
                        'count': limit['daily_count'],
                        'time': limit['duration_minutes']
                    }

            # 2. Если нет графика - использовать дефолтные лимиты
            if not result['limits']:
                default_limits = self.get_default_limits()
                for limit in default_limits:
                    result['limits'][limit['break_type']] = {
                        'count': limit['daily_count'],
                        'time': limit['duration_minutes']
                    }

            # 3. Получить использование за сегодня
            usage = self.get_break_usage_today(email)
            result['used_today'] = {
                'Перерыв': usage.get('Перерыв', {}).get('count', 0),
                'Обед': usage.get('Обед', {}).get('count', 0)
            }

            # 4. Получить активный перерыв
            active = self.get_active_break_for_user(email)
            if active:
                start_time = datetime.fromisoformat(active['start_time'].replace('Z', '+00:00'))
                now = datetime.now(timezone.utc)
                duration = int((now - start_time).total_seconds() / 60)

                break_type = active.get('break_type', 'Перерыв')
                limit = result['limits'].get(break_type, {}).get('time', 15)

                result['active_break'] = {
                    'id': active['id'],
                    'break_type': break_type,
                    'start_time': start_time.strftime('%H:%M'),
                    'duration': duration,
                    'limit': limit
                }

            return result

        except Exception as e:
            logger.error(f"Failed to get break status for {email}: {e}")
            return {
                'schedule': None,
                'limits': {'Перерыв': {'count': 3, 'time': 15}, 'Обед': {'count': 1, 'time': 60}},
                'used_today': {'Перерыв': 0, 'Обед': 0},
                'active_break': None
            }


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
