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
        """
        Возвращает объект-заглушку для совместимости с Google Sheets API.
        Для Supabase имя таблицы сохраняется в объекте для последующего использования.
        """
        class WorksheetStub:
            def __init__(self, table_name: str, api_instance):
                self.table_name = table_name
                self.api = api_instance
            
            def append_row(self, row: List[Any]):
                """Добавляет строку в таблицу Supabase"""
                return self.api._append_row_to_table(self.table_name, row)
            
            def get_all_values(self):
                """Получает все значения из таблицы Supabase"""
                return self.api._get_all_values_from_table(self.table_name)
        
        # Маппинг имён листов Google Sheets на таблицы Supabase
        table_mapping = {
            "BreakSchedules": "break_schedules",
            "UserBreakAssignments": "user_break_assignments",
            "BreakUsageLog": "break_usage_log",
            "BreakViolations": "break_violations",
        }
        
        table_name = table_mapping.get(name, name.lower().replace(" ", "_"))
        return WorksheetStub(table_name, self)
    
    def _get_ws(self, name: str):
        """Алиас для get_worksheet"""
        return self.get_worksheet(name)
    
    def _read_table(self, worksheet) -> List[Dict]:
        """
        Читает данные из таблицы Supabase и преобразует в формат Google Sheets.
        
        Args:
            worksheet: Объект WorksheetStub с table_name
            
        Returns:
            Список словарей с данными строк
        """
        if worksheet is None:
            return []
        
        try:
            table_name = worksheet.table_name
            logger.debug(f"Reading table {table_name}")
            response = self.client.table(table_name).select('*').execute()
            
            logger.debug(f"Got {len(response.data)} rows from {table_name}")
            
            # Преобразуем данные в формат Google Sheets (с заглавными ключами)
            rows = []
            for row in response.data:
                # Преобразуем ключи в заглавные для совместимости
                formatted_row = {}
                for key, value in row.items():
                    # Преобразуем snake_case в PascalCase
                    # schedule_id -> ScheduleId, но нужно ScheduleID
                    # Используем специальный маппинг для известных полей
                    key_mapping = {
                        'schedule_id': 'ScheduleID',
                        'shift_start': 'ShiftStart',
                        'shift_end': 'ShiftEnd',
                        'slot_type': 'SlotType',
                        'window_start': 'WindowStart',
                        'window_end': 'WindowEnd',
                    }
                    pascal_key = key_mapping.get(key)
                    if not pascal_key:
                        # Общий случай: snake_case -> PascalCase
                        pascal_key = ''.join(word.capitalize() for word in key.split('_'))
                    formatted_row[pascal_key] = value
                rows.append(formatted_row)
                logger.debug(f"Formatted row: {formatted_row}")
            
            logger.info(f"Read {len(rows)} rows from {table_name}")
            return rows
        except Exception as e:
            logger.error(f"Failed to read table {getattr(worksheet, 'table_name', 'unknown')}: {e}", exc_info=True)
            return []
    
    def _request_with_retry(self, func, *args, **kwargs):
        """Выполнить с retry"""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise
    
    def _append_row_to_table(self, table_name: str, values: List[Any]) -> bool:
        """
        Добавляет строку в таблицу Supabase.
        
        Args:
            table_name: Имя таблицы в Supabase
            values: Список значений для вставки
            
        Returns:
            True если успешно
        """
        try:
            # Маппинг колонок для break_schedules
            if table_name == "break_schedules":
                # Формат: [schedule_id, name, shift_start, shift_end, break_type, time_minutes, window_start, window_end, priority]
                if len(values) >= 9:
                    data = {
                        'schedule_id': str(values[0]),
                        'name': str(values[1]),
                        'shift_start': str(values[2]),
                        'shift_end': str(values[3]),
                        'slot_type': str(values[4]),
                        'duration': int(values[5]) if values[5] else 15,
                        'window_start': str(values[6]),
                        'window_end': str(values[7]),
                        'priority': int(values[8]) if values[8] else 1
                    }
                    logger.info(f"Inserting into {table_name}: {data}")
                    response = self.client.table(table_name).insert(data).execute()
                    logger.info(f"Insert successful: {len(response.data)} rows inserted")
                    return True
                else:
                    logger.error(f"Invalid values length: {len(values)}, expected 9")
                    return False
            else:
                # Для других таблиц пока не реализовано
                logger.warning(f"Table {table_name} insert not implemented yet")
                return False
        except Exception as e:
            logger.error(f"Failed to append row to {table_name}: {e}", exc_info=True)
            return False
    
    def _get_all_values_from_table(self, table_name: str) -> List[List[Any]]:
        """
        Получает все значения из таблицы Supabase в формате списка списков (как Google Sheets).
        
        Args:
            table_name: Имя таблицы в Supabase
            
        Returns:
            Список списков значений (первая строка - заголовки)
        """
        try:
            response = self.client.table(table_name).select('*').execute()
            
            if not response.data:
                return []
            
            # Первая строка - заголовки
            headers = list(response.data[0].keys())
            rows = [headers]
            
            # Остальные строки - данные
            for row in response.data:
                rows.append([row.get(h, '') for h in headers])
            
            return rows
        except Exception as e:
            logger.error(f"Failed to get all values from {table_name}: {e}", exc_info=True)
            return []
    
    def append_row(self, table: str, values: list):
        """Заглушка для append_row (используется через get_worksheet)"""
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
        """
        Получить все активные сессии (совместимость с sheets_api).
        Преобразует данные в формат Google Sheets с ключами в верхнем регистре.
        """
        try:
            sessions = self.get_active_sessions()
            # Преобразуем в формат, совместимый с sheets_api
            formatted_sessions = []
            for session in sessions:
                formatted_sessions.append({
                    'Email': session.get('email', ''),
                    'Name': session.get('name', ''),
                    'SessionID': session.get('session_id', ''),
                    'LoginTime': session.get('login_time', ''),
                    'Status': session.get('status', ''),
                    'LogoutTime': session.get('logout_time', ''),
                    'LogoutReason': session.get('logout_reason', ''),
                    'RemoteCommand': session.get('remote_command', '')
                })
            return formatted_sessions
        except Exception as e:
            logger.error(f"Failed to get all active sessions: {e}", exc_info=True)
            return []
    
    def get_active_session(self, email: str) -> Optional[Dict[str, str]]:
        """
        Получить активную сессию пользователя по email.
        
        Args:
            email: Email пользователя
        
        Returns:
            Словарь с данными сессии или None если не найдена
        """
        try:
            email_lower = (email or "").strip().lower()
            
            response = self.client.table('active_sessions')\
                .select('*')\
                .eq('email', email_lower)\
                .eq('status', 'active')\
                .order('login_time', desc=True)\
                .limit(1)\
                .execute()
            
            if response.data:
                session = response.data[0]
                # Преобразуем в формат, совместимый с sheets_api
                return {
                    'Email': session.get('email', ''),
                    'Name': session.get('name', ''),
                    'SessionID': session.get('session_id', ''),
                    'LoginTime': session.get('login_time', ''),
                    'Status': session.get('status', 'active'),
                    'LogoutTime': session.get('logout_time', ''),
                    'LogoutReason': session.get('logout_reason', ''),
                    'RemoteCommand': session.get('remote_command', '')
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get active session for {email}: {e}")
            return None
    
    def check_user_session_status(self, email: str, session_id: str) -> str:
        """
        Проверяет статус указанной сессии пользователя в Supabase.
        Возвращает: 'active', 'kicked', 'finished', 'expired', 'unknown'
        
        ВАЖНО: Ищем в work_sessions, а не в VIEW active_sessions,
        чтобы видеть актуальные изменения сразу после обновления.
        """
        try:
            email_lower = (email or "").strip().lower()
            session_id_str = str(session_id).strip()
            
            # Ищем сессию по email и session_id в work_sessions (не в VIEW!)
            response = self.client.table('work_sessions')\
                .select('status')\
                .eq('email', email_lower)\
                .eq('session_id', session_id_str)\
                .order('login_time', desc=True)\
                .limit(1)\
                .execute()
            
            if response.data:
                status = (response.data[0].get('status') or '').strip().lower()
                logger.info(f"Session status for {email_lower}/{session_id_str}: {status}")  # INFO для отладки
                return status if status else 'unknown'
            
            # Если точного совпадения нет, ищем по email (последняя сессия)
            response = self.client.table('work_sessions')\
                .select('status')\
                .eq('email', email_lower)\
                .order('login_time', desc=True)\
                .limit(1)\
                .execute()
            
            if response.data:
                status = (response.data[0].get('status') or '').strip().lower()
                logger.info(f"Session status for {email_lower} (by email only): {status}")  # INFO для отладки
                return status if status else 'unknown'
            
            logger.debug(f"No session found for {email_lower}/{session_id_str}")
            return 'unknown'
            
        except Exception as e:
            logger.error(f"Failed to check session status for {email}: {e}", exc_info=True)
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
        
        ВАЖНО: Устанавливает статус 'kicked' для принудительного разлогинивания из админки.
        """
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
            # Примечание: remote_command может отсутствовать в таблице work_sessions
            update_data = {
                'status': status,
                'logout_time': logout_time_str
            }
            
            # Пытаемся добавить remote_command только если поле существует
            # Если нет - просто обновим статус и logout_time
            
            # Ищем активные сессии пользователя в work_sessions (active_sessions - это VIEW)
            logger.debug(f"Searching for active session: email={email_lower}, session_id={session_id}")
            
            query = self.client.table('work_sessions')\
                .select('*')\
                .eq('email', email_lower)\
                .eq('status', 'active')
            
            # Если указан session_id, фильтруем по нему
            if session_id:
                query = query.eq('session_id', str(session_id).strip())
            
            response = query.order('login_time', desc=True).execute()
            
            logger.debug(f"Found {len(response.data)} sessions for {email_lower}")
            
            if not response.data:
                # Попробуем найти любые сессии этого пользователя (для отладки)
                all_sessions = self.client.table('work_sessions')\
                    .select('*')\
                    .eq('email', email_lower)\
                    .order('login_time', desc=True)\
                    .limit(5)\
                    .execute()
                
                logger.warning(f"No active session found for {email}. Found {len(all_sessions.data)} total sessions:")
                for s in all_sessions.data:
                    logger.warning(f"  Session: id={s.get('id')}, session_id={s.get('session_id')}, status={s.get('status')}, email={s.get('email')}")
                
                return False
            
            # Берем последнюю активную сессию
            session = response.data[0]
            session_id_to_update = session.get('session_id')
            
            # Обновляем сессию в work_sessions
            try:
                logger.info(f"[KICK_SESSION] Updating session {session_id_to_update} for {email} with status='{status}', logout_time='{logout_time_str}'")
                logger.info(f"[KICK_SESSION] Update data: {update_data}")
                
                update_response = self.client.table('work_sessions')\
                    .update(update_data)\
                    .eq('session_id', session_id_to_update)\
                    .execute()
                
                logger.info(f"[KICK_SESSION] Update response: {len(update_response.data)} rows updated")
                
                # Проверяем, что статус действительно обновился (с небольшой задержкой для гарантии)
                import time
                time.sleep(0.5)  # Небольшая задержка для гарантии обновления в БД
                
                verify_response = self.client.table('work_sessions')\
                    .select('status, logout_time')\
                    .eq('session_id', session_id_to_update)\
                    .execute()
                
                if verify_response.data:
                    actual_status = verify_response.data[0].get('status', '')
                    actual_logout_time = verify_response.data[0].get('logout_time', '')
                    logger.info(f"[KICK_SESSION] Verified status after update: '{actual_status}' (expected: '{status}')")
                    logger.info(f"[KICK_SESSION] Verified logout_time: '{actual_logout_time}'")
                    if actual_status.lower() != status.lower():
                        logger.warning(f"[KICK_SESSION] ⚠️ Status mismatch! Expected '{status}', got '{actual_status}'")
                    else:
                        logger.info(f"[KICK_SESSION] ✅ Status correctly set to '{status}'")
                else:
                    logger.warning(f"[KICK_SESSION] ⚠️ Could not verify status - session not found after update")
                
                logger.info(f"[KICK_SESSION] Successfully kicked session {session_id_to_update} for {email}")
                return True
            except Exception as update_error:
                # Если ошибка из-за remote_command - пробуем без него
                error_msg = str(update_error)
                if 'remote_command' in error_msg.lower():
                    logger.debug(f"Field 'remote_command' not found, updating without it")
                    update_data_minimal = {
                        'status': status,
                        'logout_time': logout_time_str
                    }
                    self.client.table('work_sessions')\
                        .update(update_data_minimal)\
                        .eq('session_id', session_id_to_update)\
                        .execute()
                    logger.info(f"Successfully kicked session {session_id_to_update} for {email} (without remote_command)")
                    return True
                else:
                    raise
            
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
            
            # Обновляем только существующие поля
            # Примечание: logout_reason может отсутствовать в таблице work_sessions
            update_data = {
                'status': 'finished',
                'logout_time': logout_time_str
            }
            
            # Пытаемся добавить logout_reason только если поле существует
            # Если нет - просто обновим статус и logout_time
            
            # Обновляем в work_sessions (active_sessions - это VIEW)
            try:
                response = self.client.table('work_sessions')\
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
            except Exception as update_error:
                # Если ошибка из-за logout_reason - пробуем без него
                error_msg = str(update_error)
                if 'logout_reason' in error_msg.lower():
                    logger.debug(f"Field 'logout_reason' not found, updating without it")
                    update_data_minimal = {
                        'status': 'finished',
                        'logout_time': logout_time_str
                    }
                    response = self.client.table('work_sessions')\
                        .update(update_data_minimal)\
                        .eq('email', email_lower)\
                        .eq('session_id', session_id_str)\
                        .eq('status', 'active')\
                        .execute()
                    
                    if response.data:
                        logger.info(f"Successfully finished session {session_id_str} for {email} (without logout_reason)")
                        return True
                    else:
                        logger.info(f"No active session found with session_id {session_id_str} for {email}")
                        return False
                else:
                    raise
                
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
            
            # Обновляем в work_sessions (active_sessions - это VIEW)
            # Примечание: если в work_sessions нет поля remote_command, этот метод может не работать
            # В таком случае можно пропустить обновление или добавить поле в таблицу
            try:
                update_data = {
                    'remote_command': ''  # Очищаем команду после подтверждения
                }
                
                self.client.table('work_sessions')\
                    .update(update_data)\
                    .eq('email', email_lower)\
                    .eq('session_id', session_id_str)\
                    .execute()
            except Exception as e:
                # Если поля remote_command нет в work_sessions - просто логируем
                logger.debug(f"Could not update remote_command (field may not exist): {e}")
                return True
            
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
        
        ВАЖНО: active_sessions - это VIEW, поэтому вставляем данные в work_sessions.
        
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
            
            # Формируем данные для таблицы work_sessions (не active_sessions - это VIEW!)
            data = {
                'session_id': session_id,
                'email': email_lower,
                'login_time': login_time_str,
                'status': 'active'
            }
            
            # Добавляем user_id только если он есть
            if user_id:
                data['user_id'] = user_id
            
            # Проверяем, существует ли уже сессия с таким session_id в work_sessions
            existing = self.client.table('work_sessions')\
                .select('id')\
                .eq('session_id', session_id)\
                .execute()
            
            if existing.data:
                # Обновляем существующую сессию
                self.client.table('work_sessions')\
                    .update(data)\
                    .eq('session_id', session_id)\
                    .execute()
            else:
                # Создаем новую сессию в work_sessions (active_sessions - это VIEW, в него нельзя вставлять)
                self.client.table('work_sessions').insert(data).execute()
            
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
        """
        Получить пользователя по email.
        Возвращает данные в формате, совместимом с sheets_api.py
        """
        try:
            email_lower = (email or "").strip().lower()
            response = self.client.table('users')\
                .select('*')\
                .eq('email', email_lower)\
                .execute()
            
            if response.data:
                row = response.data[0]
                # Возвращаем в формате, совместимом с sheets_api.py
                return {
                    # Ключи в нижнем регистре для совместимости с login_window.py
                    'email': email_lower,
                    'name': row.get('name', ''),
                    'role': row.get('role', 'специалист'),
                    'shift_hours': row.get('shift_hours', '8 часов'),
                    'telegram_login': row.get('telegram_id', ''),
                    'group': row.get('group_name', ''),
                    # Также возвращаем в формате с заглавными буквами для совместимости
                    'Email': email_lower,
                    'Name': row.get('name', ''),
                    'Phone': row.get('phone', ''),
                    'Role': row.get('role', 'специалист'),
                    'Telegram': row.get('telegram_id', ''),
                    'Group': row.get('group_name', ''),
                    'ShiftHours': row.get('shift_hours', '8 часов'),
                    'NotifyTelegram': 'Yes' if row.get('notify_telegram') else 'No'
                }
            return None
            
        except Exception as e:
            logger.error(f"Failed to get user by email {email}: {e}", exc_info=True)
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
            # ВАЖНО: Некоторые поля могут отсутствовать в таблице work_log в Supabase
            # Проверяем только существующие поля: user_id, email, name, timestamp, action_type, status, session_id, user_group
            records = []
            for action in actions:
                record = {
                    'user_id': user_id,
                    'email': email.lower(),
                    'name': action.get('name', ''),
                    'timestamp': action.get('timestamp') or datetime.now(timezone.utc).isoformat(),
                    'action_type': action.get('action_type', ''),
                    'status': action.get('status', ''),
                    'session_id': action.get('session_id', ''),
                    'user_group': user_group or action.get('user_group')
                }
                # Удаляем пустые значения
                record = {k: v for k, v in record.items() if v is not None and v != ''}
                records.append(record)
            
            # Вставляем записи batch-ом с обработкой ошибок сокета
            try:
                self.client.table('work_log').insert(records).execute()
                logger.info(f"Logged {len(records)} actions for {email}")
                return True
            except Exception as insert_error:
                # Ошибки сокета в Windows (WinError 10035) не критичны для работы приложения
                error_str = str(insert_error)
                if '10035' in error_str or 'socket' in error_str.lower() or 'ReadError' in str(type(insert_error).__name__):
                    logger.warning(f"Socket error while logging actions for {email} (non-critical): {insert_error}")
                    # Возвращаем True, чтобы не блокировать основную функциональность
                    return True
                else:
                    # Другие ошибки - пробрасываем дальше
                    raise
            
        except Exception as e:
            logger.error(f"Failed to log user actions for {email}: {e}", exc_info=True)
            # Не блокируем основную функциональность из-за ошибок логирования
            return False
    
    # ========================================================================
    # VIOLATIONS (нарушения перерывов)
    # ========================================================================
    
    def get_violations(
        self,
        email: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        violation_type: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Получить список нарушений перерывов.
        
        Args:
            email: Фильтр по email пользователя
            date_from: Начальная дата (ISO строка или YYYY-MM-DD)
            date_to: Конечная дата (ISO строка или YYYY-MM-DD)
            violation_type: Тип нарушения
            status: Статус нарушения (pending, reviewed, resolved)
        
        Returns:
            Список словарей с нарушениями
        """
        try:
            query = self.client.table('violations').select('*')
            
            # Фильтр по email
            if email:
                query = query.eq('email', email.lower().strip())
            
            # Фильтр по дате начала
            if date_from:
                if len(date_from) == 10:  # Формат YYYY-MM-DD
                    query = query.gte('timestamp', date_from)
                else:
                    query = query.gte('timestamp', date_from)
            
            # Фильтр по дате конца
            if date_to:
                if len(date_to) == 10:  # Формат YYYY-MM-DD
                    # Включаем весь день - добавляем время 23:59:59
                    query = query.lte('timestamp', f"{date_to}T23:59:59")
                else:
                    query = query.lte('timestamp', date_to)
            
            # Фильтр по типу нарушения
            if violation_type:
                query = query.eq('violation_type', violation_type)
            
            # Фильтр по статусу
            if status:
                query = query.eq('status', status)
            
            # Сортируем по дате (новые сначала)
            response = query.order('timestamp', desc=True).execute()
            
            # Преобразуем в формат, совместимый с sheets_api
            violations = []
            for row in response.data:
                violations.append({
                    'Timestamp': row.get('timestamp', ''),
                    'Email': row.get('email', ''),
                    'ViolationType': row.get('violation_type', ''),
                    'Details': row.get('details', ''),
                    'Status': row.get('status', 'pending'),
                    'SessionID': row.get('session_id', ''),
                    'Severity': row.get('severity', 'INFO'),
                    'BreakType': row.get('break_type', ''),
                    'BreakID': row.get('break_id', ''),
                    'OvertimeMinutes': row.get('overtime_minutes', 0)
                })
            
            return violations
            
        except Exception as e:
            logger.error(f"Failed to get violations: {e}", exc_info=True)
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
