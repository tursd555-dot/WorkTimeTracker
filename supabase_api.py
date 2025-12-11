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
    
    def get_all_active_sessions(self) -> List[Dict]:
        """Получить все активные сессии (совместимость с sheets_api)"""
        return self.get_active_sessions()
    
    def check_user_session_status(self, email: str, session_id: str) -> str:
        """
        Проверяет статус указанной сессии пользователя в Supabase.
        Возвращает: 'active', 'kicked', 'finished', 'expired', 'unknown'
        """
        try:
            email_lower = (email or "").strip().lower()
            session_id_str = str(session_id).strip()
            
            # Ищем сессию по email и session_id
            response = self.client.table('active_sessions')\
                .select('status')\
                .eq('email', email_lower)\
                .eq('session_id', session_id_str)\
                .order('login_time', desc=True)\
                .limit(1)\
                .execute()
            
            if response.data:
                status = (response.data[0].get('status') or '').strip().lower()
                return status if status else 'unknown'
            
            # Если точного совпадения нет, ищем по email (последняя сессия)
            response = self.client.table('active_sessions')\
                .select('status')\
                .eq('email', email_lower)\
                .order('login_time', desc=True)\
                .limit(1)\
                .execute()
            
            if response.data:
                status = (response.data[0].get('status') or '').strip().lower()
                return status if status else 'unknown'
            
            return 'unknown'
            
        except Exception as e:
            logger.error(f"Failed to check session status for {email}: {e}")
            return 'unknown'
    
    def kick_active_session(
        self,
        email: str,
        session_id: Optional[str] = None,
        status: str = "kicked",
        remote_cmd: str = "FORCE_LOGOUT",
        logout_time: Optional[Any] = None
    ) -> bool:
        """
        Принудительно завершает ПОСЛЕДНЮЮ активную сессию пользователя.
        
        Args:
            email: Email пользователя
            session_id: Опциональный ID сессии (если None, берется последняя активная)
            status: Статус для установки (по умолчанию "kicked")
            remote_cmd: Команда для установки (по умолчанию "FORCE_LOGOUT")
            logout_time: Время разлогинивания (datetime, ISO строка или None для текущего времени)
        
        Returns:
            True если сессия найдена и обновлена, False если не найдена
        """
        try:
            email_lower = (email or "").strip().lower()
            
            # Обрабатываем logout_time: может быть datetime, строка или None
            if logout_time is None:
                logout_time_str = datetime.now(timezone.utc).isoformat()
            elif isinstance(logout_time, datetime):
                logout_time_str = logout_time.isoformat()
            else:
                logout_time_str = str(logout_time)
            
            # Формируем данные для обновления
            update_data = {
                'status': status,
                'logout_time': logout_time_str,
                'remote_command': remote_cmd,
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            
            # Ищем активные сессии пользователя
            query = self.client.table('active_sessions')\
                .select('*')\
                .eq('email', email_lower)\
                .eq('status', 'active')
            
            # Если указан session_id, фильтруем по нему
            if session_id:
                query = query.eq('session_id', str(session_id).strip())
            
            response = query.order('login_time', desc=True).execute()
            
            if not response.data:
                logger.info(f"No active session found for {email}")
                return False
            
            # Берем последнюю активную сессию
            session = response.data[0]
            session_id_to_update = session.get('session_id')
            
            # Обновляем сессию
            self.client.table('active_sessions')\
                .update(update_data)\
                .eq('session_id', session_id_to_update)\
                .execute()
            
            logger.info(f"Successfully kicked session {session_id_to_update} for {email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to kick active session for {email}: {e}", exc_info=True)
            return False
    
    def finish_active_session(
        self,
        email: str,
        session_id: str,
        logout_time: Optional[str] = None,
        reason: str = "user_exit"
    ) -> bool:
        """
        Завершает активную сессию пользователя (Status=finished).
        
        Args:
            email: Email пользователя
            session_id: ID сессии
            logout_time: Время завершения (ISO строка или None для текущего времени)
            reason: Причина завершения (по умолчанию "user_exit")
        
        Returns:
            True если сессия найдена и обновлена, False если не найдена
        """
        try:
            email_lower = (email or "").strip().lower()
            session_id_str = str(session_id).strip()
            logout_time_str = logout_time or datetime.now(timezone.utc).isoformat()
            
            update_data = {
                'status': 'finished',
                'logout_time': logout_time_str,
                'logout_reason': reason,
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            
            response = self.client.table('active_sessions')\
                .update(update_data)\
                .eq('email', email_lower)\
                .eq('session_id', session_id_str)\
                .eq('status', 'active')\
                .execute()
            
            if response.data:
                logger.info(f"Successfully finished session {session_id_str} for {email}")
                return True
            else:
                logger.info(f"No active session found with session_id {session_id_str} for {email}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to finish active session for {email}: {e}", exc_info=True)
            return False
    
    def ack_remote_command(self, email: str, session_id: str) -> bool:
        """
        Отправляет подтверждение получения удаленной команды.
        
        Args:
            email: Email пользователя
            session_id: ID сессии
        
        Returns:
            True если успешно
        """
        try:
            email_lower = (email or "").strip().lower()
            session_id_str = str(session_id).strip()
            
            update_data = {
                'remote_command': '',  # Очищаем команду после подтверждения
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            
            self.client.table('active_sessions')\
                .update(update_data)\
                .eq('email', email_lower)\
                .eq('session_id', session_id_str)\
                .execute()
            
            logger.debug(f"ACK sent for remote command: {email}, session_id={session_id_str}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to ACK remote command for {email}: {e}")
            return False
    
    def set_active_session(
        self,
        email: str,
        name: str,
        session_id: str,
        login_time: Optional[str] = None
    ) -> bool:
        """
        Создает или обновляет активную сессию пользователя.
        
        Args:
            email: Email пользователя
            name: Имя пользователя
            session_id: ID сессии
            login_time: Время входа (ISO строка или None для текущего времени)
        
        Returns:
            True если успешно
        """
        try:
            email_lower = (email or "").strip().lower()
            login_time_str = login_time or datetime.now(timezone.utc).isoformat()
            
            # Получаем user_id
            user_response = self.client.table('users')\
                .select('id')\
                .eq('email', email_lower)\
                .execute()
            
            user_id = user_response.data[0]['id'] if user_response.data else None
            
            data = {
                'session_id': session_id,
                'email': email_lower,
                'name': name,
                'user_id': user_id,
                'login_time': login_time_str,
                'status': 'active',
                'created_at': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            
            # Проверяем, существует ли уже сессия с таким session_id
            existing = self.client.table('active_sessions')\
                .select('id')\
                .eq('session_id', session_id)\
                .execute()
            
            if existing.data:
                # Обновляем существующую сессию
                self.client.table('active_sessions')\
                    .update(data)\
                    .eq('session_id', session_id)\
                    .execute()
            else:
                # Создаем новую сессию
                self.client.table('active_sessions').insert(data).execute()
            
            logger.info(f"Active session set for {email}, session_id={session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set active session for {email}: {e}", exc_info=True)
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
    # ADDITIONAL COMPATIBILITY METHODS
    # ========================================================================
    
    def get_user_by_email(self, email: str) -> Optional[Dict[str, str]]:
        """Получить пользователя по email"""
        try:
            email_lower = (email or "").strip().lower()
            response = self.client.table('users')\
                .select('*')\
                .eq('email', email_lower)\
                .execute()
            
            if response.data:
                row = response.data[0]
                return {
                    'Email': row.get('email', ''),
                    'Name': row.get('name', ''),
                    'Phone': row.get('phone', ''),
                    'Role': row.get('role', ''),
                    'Telegram': row.get('telegram_id', ''),
                    'Group': row.get('group_name', ''),
                    'NotifyTelegram': 'Yes' if row.get('notify_telegram') else 'No'
                }
            return None
            
        except Exception as e:
            logger.error(f"Failed to get user by email {email}: {e}")
            return None
    
    def delete_user(self, email: str) -> bool:
        """Удалить пользователя (пометить как неактивного)"""
        try:
            email_lower = (email or "").strip().lower()
            self.client.table('users')\
                .update({'is_active': False, 'updated_at': datetime.now(timezone.utc).isoformat()})\
                .eq('email', email_lower)\
                .execute()
            logger.info(f"User {email} marked as inactive")
            return True
        except Exception as e:
            logger.error(f"Failed to delete user {email}: {e}")
            return False
    
    def update_user_fields(self, email: str, fields: Dict[str, str]) -> None:
        """Обновить поля пользователя"""
        try:
            email_lower = (email or "").strip().lower()
            
            # Преобразуем поля из формата Sheets в формат Supabase
            data = {}
            field_mapping = {
                'Name': 'name',
                'Phone': 'phone',
                'Role': 'role',
                'Telegram': 'telegram_id',
                'Group': 'group_name',
                'NotifyTelegram': 'notify_telegram'
            }
            
            for key, value in fields.items():
                if key in field_mapping:
                    db_key = field_mapping[key]
                    if db_key == 'notify_telegram':
                        data[db_key] = str(value).lower() in ('yes', 'true', '1', 'да')
                    else:
                        data[db_key] = value
            
            data['updated_at'] = datetime.now(timezone.utc).isoformat()
            
            self.client.table('users')\
                .update(data)\
                .eq('email', email_lower)\
                .execute()
            
            logger.info(f"Updated fields for user {email}")
            
        except Exception as e:
            logger.error(f"Failed to update user fields for {email}: {e}")
            raise
    
    def log_user_actions(self, actions: List[Dict[str, Any]], email: str, user_group: Optional[str] = None) -> bool:
        """
        Записать действия пользователя в лог.
        
        Args:
            actions: Список действий для записи
            email: Email пользователя
            user_group: Группа пользователя (опционально)
        
        Returns:
            True если успешно записано
        """
        try:
            if not actions:
                return True
            
            # Получаем user_id
            user = self.get_user_by_email(email)
            if not user:
                logger.warning(f"User {email} not found, cannot log actions")
                return False
            
            user_response = self.client.table('users')\
                .select('id')\
                .eq('email', email.lower())\
                .execute()
            
            user_id = user_response.data[0]['id'] if user_response.data else None
            
            # Подготавливаем данные для вставки
            records = []
            for action in actions:
                record = {
                    'user_id': user_id,
                    'email': email.lower(),
                    'name': action.get('name', ''),
                    'timestamp': action.get('timestamp') or datetime.now(timezone.utc).isoformat(),
                    'action_type': action.get('action_type', ''),
                    'status': action.get('status', ''),
                    'comment': action.get('comment', ''),
                    'session_id': action.get('session_id', ''),
                    'status_start_time': action.get('status_start_time'),
                    'status_end_time': action.get('status_end_time'),
                    'reason': action.get('reason'),
                    'user_group': user_group or action.get('user_group')
                }
                records.append(record)
            
            # Вставляем записи batch-ом
            self.client.table('work_log').insert(records).execute()
            
            logger.info(f"Logged {len(records)} actions for {email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to log user actions for {email}: {e}", exc_info=True)
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
