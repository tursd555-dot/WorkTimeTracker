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

    def finish_active_session(self, email: str, session_id: str) -> bool:
        """
        Завершить активную сессию
        Совместимо с sheets_api.finish_active_session
        """
        try:
            data = {
                'logout_time': datetime.now(timezone.utc).isoformat(),
                'status': 'finished'
            }

            self.client.table('work_sessions')\
                .update(data)\
                .eq('email', email)\
                .eq('session_id', session_id)\
                .execute()

            logger.info(f"✅ Session finished for {email}")
            return True

        except Exception as e:
            logger.error(f"Failed to finish session: {e}")
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
