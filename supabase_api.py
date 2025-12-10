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
        """Возвращает имя таблицы для совместимости с sheets API"""
        # Мапинг имен листов Google Sheets на таблицы Supabase
        sheet_to_table_mapping = {
            "BreakLog": "break_log",
            "BreakSchedules": "break_schedules",
            "UserBreakAssignments": "user_break_assignments",
            "Violations": "violations",
            "Users": "users",
            "Groups": "groups"
        }
        return sheet_to_table_mapping.get(name, name.lower())

    def _get_ws(self, name: str):
        """Алиас для get_worksheet"""
        return self.get_worksheet(name)

    def _read_table(self, table_name):
        """
        Читает все записи из таблицы Supabase
        Возвращает список словарей в формате совместимом с sheets_api
        """
        if not table_name:
            return []

        try:
            response = self.client.table(table_name).select('*').execute()

            # Преобразуем данные из Supabase в формат sheets_api
            result = []
            for row in response.data:
                # Преобразуем snake_case в PascalCase для совместимости
                converted_row = {}
                for key, value in row.items():
                    # Специальные маппинги полей
                    if key == 'email':
                        converted_row['Email'] = value
                    elif key == 'name':
                        converted_row['Name'] = value
                    elif key == 'break_type':
                        converted_row['BreakType'] = value
                    elif key == 'start_time':
                        # Преобразуем timestamp в строку
                        if isinstance(value, datetime):
                            converted_row['StartTime'] = value.isoformat()
                        else:
                            converted_row['StartTime'] = value
                    elif key == 'end_time':
                        if isinstance(value, datetime):
                            converted_row['EndTime'] = value.isoformat() if value else ''
                        else:
                            converted_row['EndTime'] = value or ''
                    elif key == 'duration':
                        converted_row['Duration'] = str(value) if value else ''
                    elif key == 'status':
                        converted_row['Status'] = value
                    elif key == 'session_id':
                        converted_row['SessionID'] = value
                    elif key == 'schedule_id':
                        converted_row['ScheduleID'] = value
                    elif key == 'violation_type':
                        converted_row['ViolationType'] = value
                    elif key == 'timestamp':
                        if isinstance(value, datetime):
                            converted_row['Timestamp'] = value.isoformat()
                        else:
                            converted_row['Timestamp'] = value
                    elif key == 'details':
                        converted_row['Details'] = value
                    elif key == 'group_name':
                        converted_row['Group'] = value
                    else:
                        # Для других полей просто используем PascalCase
                        pascal_key = ''.join(word.capitalize() for word in key.split('_'))
                        converted_row[pascal_key] = value

                result.append(converted_row)

            return result

        except Exception as e:
            logger.error(f"Failed to read table {table_name}: {e}")
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
