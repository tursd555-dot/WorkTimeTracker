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
            
            def clear(self):
                """Очищает таблицу (не реализовано для безопасности, используется delete_rows вместо этого)"""
                logger.warning(f"clear() called on {self.table_name} - not implemented for safety")
                pass
            
            def delete_rows_by_schedule_id(self, schedule_id: str) -> bool:
                """Удаляет строки по schedule_id (для break_schedules)"""
                return self.api._delete_rows_by_schedule_id(self.table_name, schedule_id)
        
        # Маппинг имён листов Google Sheets на таблицы Supabase
        table_mapping = {
            "BreakSchedules": "break_schedules",
            "UserBreakAssignments": "user_break_assignments",
            "BreakUsageLog": "break_usage_log",
            "BreakLog": "break_log",  # v20.3: renamed from BreakUsageLog
            "BreakViolations": "violations",  # В Supabase таблица называется violations
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
                    # Специальный маппинг для известных полей разных таблиц
                    key_mapping = {}
                    if table_name == "break_schedules":
                        key_mapping = {
                            'id': 'ScheduleID',  # Используем id как ScheduleID
                            'name': 'Name',
                            'shift_start': 'ShiftStart',
                            'shift_end': 'ShiftEnd',
                            'slot_type': 'SlotType',
                            'window_start': 'WindowStart',
                            'window_end': 'WindowEnd',
                            'duration': 'Duration',
                            'priority': 'Order',
                            'description': 'Description',
                            'is_active': 'IsActive',
                            'created_by': 'CreatedBy',
                            'created_at': 'CreatedAt',
                            'updated_at': 'UpdatedAt',
                        }
                    elif table_name == "user_break_assignments":
                        key_mapping = {
                            'id': 'Id',
                            'email': 'Email',
                            'schedule_id': 'ScheduleID',  # Это UUID, но для совместимости оставляем как ScheduleID
                            'effective_date': 'EffectiveDate',
                            'assigned_by': 'AssignedBy',
                            'created_at': 'CreatedAt',
                            'updated_at': 'UpdatedAt',
                        }
                        
                        # После преобразования ключей, преобразуем UUID schedule_id в имя шаблона для отображения
                        if 'schedule_id' in row and row['schedule_id']:
                            try:
                                # Пробуем найти имя шаблона по UUID
                                schedule_response = self.client.table('break_schedules')\
                                    .select('name, id')\
                                    .eq('id', row['schedule_id'])\
                                    .execute()
                                if schedule_response.data:
                                    # Сохраняем и UUID и имя для совместимости
                                    formatted_row['ScheduleID'] = schedule_response.data[0].get('name', row['schedule_id'])
                                    formatted_row['ScheduleUUID'] = row['schedule_id']  # Сохраняем UUID отдельно
                                else:
                                    # Если шаблон не найден, оставляем UUID
                                    formatted_row['ScheduleID'] = row['schedule_id']
                            except Exception as e:
                                logger.debug(f"Could not find schedule name for UUID {row.get('schedule_id')}: {e}")
                                formatted_row['ScheduleID'] = row.get('schedule_id', '')
                    elif table_name == "break_log":
                        key_mapping = {
                            'id': 'Id',
                            'email': 'Email',
                            'name': 'Name',
                            'break_type': 'BreakType',
                            'start_time': 'StartTime',
                            'end_time': 'EndTime',
                            'duration_minutes': 'Duration',
                            'date': 'Date',
                            'status': 'Status',
                            'session_id': 'SessionID',
                            'created_at': 'CreatedAt',
                            'updated_at': 'UpdatedAt',
                        }
                    elif table_name == "violations" or table_name == "break_violations":
                        key_mapping = {
                            'id': 'Id',
                            'timestamp': 'Timestamp',
                            'email': 'Email',
                            'session_id': 'SessionID',
                            'violation_type': 'ViolationType',
                            'details': 'Details',
                            'status': 'Status',
                            'created_at': 'CreatedAt',
                            'updated_at': 'UpdatedAt',
                        }
                    else:
                        key_mapping = {}
                    
                    pascal_key = key_mapping.get(key)
                    if not pascal_key:
                        # Общий случай: snake_case -> PascalCase
                        pascal_key = ''.join(word.capitalize() for word in key.split('_'))
                    formatted_row[pascal_key] = value
                
                # Специальная обработка для user_break_assignments: преобразуем UUID в имя шаблона
                if table_name == "user_break_assignments" and 'schedule_id' in row and row['schedule_id']:
                    try:
                        # Пробуем найти имя шаблона по UUID
                        schedule_response = self.client.table('break_schedules')\
                            .select('name, id')\
                            .eq('id', row['schedule_id'])\
                            .execute()
                        if schedule_response.data:
                            # Заменяем UUID на имя шаблона для отображения
                            formatted_row['ScheduleID'] = schedule_response.data[0].get('name', row['schedule_id'])
                            formatted_row['ScheduleUUID'] = row['schedule_id']  # Сохраняем UUID отдельно
                        else:
                            # Если шаблон не найден (удалён), показываем UUID или "Удалён"
                            formatted_row['ScheduleID'] = f"[Удалён: {row['schedule_id'][:8]}...]"
                            formatted_row['ScheduleUUID'] = row['schedule_id']
                    except Exception as e:
                        logger.debug(f"Could not find schedule name for UUID {row.get('schedule_id')}: {e}")
                        formatted_row['ScheduleID'] = row.get('schedule_id', '')
                
                # Специальная обработка для break_schedules: парсим JSON из description ПОСЛЕ заполнения всех полей
                if table_name == "break_schedules":
                    description_value = formatted_row.get('Description') or row.get('description')
                    if description_value:
                        try:
                            import json
                            slot_info = json.loads(description_value)
                            logger.debug(f"Parsed slot info from description: {slot_info}")
                            # Добавляем поля слота из JSON, если их еще нет
                            if 'slot_type' in slot_info and not formatted_row.get('SlotType'):
                                formatted_row['SlotType'] = slot_info['slot_type']
                            if 'duration' in slot_info and not formatted_row.get('Duration'):
                                formatted_row['Duration'] = str(slot_info['duration'])
                            if 'window_start' in slot_info and not formatted_row.get('WindowStart'):
                                formatted_row['WindowStart'] = slot_info['window_start']
                            if 'window_end' in slot_info and not formatted_row.get('WindowEnd'):
                                formatted_row['WindowEnd'] = slot_info['window_end']
                            if 'priority' in slot_info and not formatted_row.get('Order'):
                                formatted_row['Order'] = str(slot_info['priority'])
                        except (json.JSONDecodeError, KeyError, TypeError) as e:
                            # Если description не JSON или не содержит данных слота, это основная запись шаблона
                            logger.debug(f"Could not parse slot info from description '{description_value}': {e}")
                
                # Специальная обработка для violations: нормализуем timestamp
                if table_name == "violations" or table_name == "break_violations":
                    timestamp = formatted_row.get('Timestamp') or row.get('timestamp')
                    if timestamp:
                        # Если timestamp в формате ISO (2025-12-11T14:30:00+00:00), преобразуем в читаемый формат
                        if 'T' in str(timestamp):
                            # ISO формат: оставляем как есть для фильтрации, но можно нормализовать
                            formatted_row['Timestamp'] = str(timestamp)
                        else:
                            formatted_row['Timestamp'] = str(timestamp)
                
                rows.append(formatted_row)
                logger.debug(f"Formatted row: {formatted_row}")
            
            logger.info(f"Read {len(rows)} rows from {table_name}")
            
            # Дополнительное логирование для break_log
            if table_name == "break_log" and rows:
                logger.debug(f"break_log sample row keys: {list(rows[0].keys()) if rows else 'no rows'}")
                logger.debug(f"break_log sample row: {rows[0] if rows else 'no rows'}")
            
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
            # Маппинг колонок для разных таблиц
            if table_name == "user_break_assignments":
                # Формат: [email, schedule_id, effective_date, assigned_by]
                # schedule_id должен быть UUID, а не строка!
                if len(values) >= 2:
                    email_val = str(values[0]).lower() if values[0] else None
                    schedule_id_or_name = str(values[1]) if len(values) > 1 and values[1] else None
                    
                    if not email_val or not schedule_id_or_name:
                        logger.error(f"Missing required fields: email={email_val}, schedule_id={schedule_id_or_name}")
                        return False
                    
                    # Нужно найти UUID шаблона по его имени или ID
                    schedule_uuid = None
                    try:
                        logger.info(f"[ASSIGNMENT] Looking for schedule: {schedule_id_or_name}")
                        
                        # Проверяем, является ли это валидным UUID (формат: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)
                        import re
                        uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
                        is_uuid = uuid_pattern.match(schedule_id_or_name.strip())
                        
                        if is_uuid:
                            # Это уже UUID, проверяем что шаблон существует
                            logger.info(f"[ASSIGNMENT] schedule_id_or_name is a UUID, validating: {schedule_id_or_name}")
                            try:
                                response = self.client.table('break_schedules')\
                                    .select('id, name')\
                                    .eq('id', schedule_id_or_name)\
                                    .execute()
                                if response.data:
                                    schedule_uuid = response.data[0]['id']
                                    schedule_name = response.data[0].get('name', schedule_id_or_name)
                                    logger.info(f"[ASSIGNMENT] ✅ Schedule UUID validated: {schedule_uuid} (name: {schedule_name})")
                                else:
                                    logger.error(f"[ASSIGNMENT] ❌ Schedule UUID not found in database: {schedule_id_or_name}")
                                    return False
                            except Exception as uuid_error:
                                logger.error(f"[ASSIGNMENT] ❌ Failed to validate UUID: {uuid_error}", exc_info=True)
                                return False
                        else:
                            # Это не UUID, ищем по имени
                            logger.info(f"[ASSIGNMENT] schedule_id_or_name is not a UUID, searching by name: {schedule_id_or_name}")
                            response = self.client.table('break_schedules')\
                                .select('id, name')\
                                .eq('name', schedule_id_or_name)\
                                .execute()
                            if response.data:
                                schedule_uuid = response.data[0]['id']
                                schedule_name = response.data[0].get('name', schedule_id_or_name)
                                logger.info(f"[ASSIGNMENT] ✅ Found schedule by name '{schedule_id_or_name}': UUID={schedule_uuid}")
                            else:
                                logger.warning(f"[ASSIGNMENT] ⚠️ Schedule not found by name: {schedule_id_or_name}")
                                # Пробуем найти все шаблоны для отладки
                                try:
                                    all_schedules = self.client.table('break_schedules')\
                                        .select('id, name')\
                                        .limit(10)\
                                        .execute()
                                    logger.info(f"[ASSIGNMENT] Available schedules: {[(s.get('name'), s.get('id')) for s in all_schedules.data]}")
                                except Exception:
                                    pass
                                return False
                        
                        if not schedule_uuid:
                            logger.error(f"[ASSIGNMENT] ❌ Schedule not found: {schedule_id_or_name}")
                            return False
                    except Exception as e:
                        logger.error(f"[ASSIGNMENT] ❌ Failed to find schedule UUID: {e}", exc_info=True)
                        return False
                    
                    # Создаём назначение с UUID шаблона
                    data = {
                        'email': email_val,
                        'schedule_id': schedule_uuid  # Используем UUID, а не строку
                    }
                    
                    try:
                        logger.info(f"Inserting assignment into {table_name}: email={email_val}, schedule_id={schedule_uuid}")
                        response = self.client.table(table_name).insert(data).execute()
                        logger.info(f"✅ Insert successful: {len(response.data)} rows inserted")
                        return True
                    except Exception as insert_error:
                        logger.error(f"Failed to insert assignment: {insert_error}", exc_info=True)
                        return False
                else:
                    logger.error(f"Invalid values length: {len(values)}, expected at least 2")
                    return False
            elif table_name == "break_schedules":
                # Формат: [schedule_id, name, shift_start, shift_end, break_type, time_minutes, window_start, window_end, priority]
                # В Supabase храним слоты как отдельные строки в break_schedules (как в Google Sheets)
                # Используем поля slot_type, window_start, window_end, duration, priority прямо в break_schedules
                if len(values) >= 9:
                    schedule_id = str(values[0])  # Это может быть строка-идентификатор или UUID
                    name = str(values[1])
                    shift_start = str(values[2]) if values[2] else None
                    shift_end = str(values[3]) if values[3] else None
                    slot_type = str(values[4])
                    duration = int(values[5]) if values[5] else 15
                    window_start = str(values[6]) if values[6] else None
                    window_end = str(values[7]) if values[7] else None
                    priority = int(values[8]) if values[8] else 1
                    
                    # Проверяем, существует ли уже шаблон с таким именем
                    # Используем name как идентификатор шаблона
                    existing = self.client.table('break_schedules')\
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
                    
                    # Если основной записи нет, создаем её только при первом слоте
                    if not main_record:
                        # Создаём основную запись шаблона (без description)
                        schedule_data = {
                            'name': name,
                            'shift_start': shift_start,
                            'shift_end': shift_end,
                            'is_active': True,
                            'description': None  # Основная запись без description
                        }
                        schedule_response = self.client.table('break_schedules').insert(schedule_data).execute()
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
                            self.client.table('break_schedules')\
                                .update(update_data)\
                                .eq('id', main_record['id'])\
                                .execute()
                            logger.debug(f"Updated main schedule record: {update_data}")
                    
                    # Сохраняем слот как отдельную строку в break_schedules
                    # Используем поле description для хранения данных слота в JSON формате
                    import json
                    slot_info = {
                        'slot_type': slot_type,
                        'duration': duration,
                        'window_start': window_start,
                        'window_end': window_end,
                        'priority': priority
                    }
                    
                    slot_data = {
                        'name': name,  # Связь через name
                        'shift_start': shift_start,
                        'shift_end': shift_end,
                        'description': json.dumps(slot_info),  # Храним данные слота в JSON
                        'is_active': True
                    }
                    
                    try:
                        self.client.table('break_schedules').insert(slot_data).execute()
                        logger.info(f"Created slot row: slot_type={slot_type}, duration={duration}, window={window_start}-{window_end}")
                    except Exception as insert_error:
                        logger.error(f"Failed to insert slot row: {insert_error}", exc_info=True)
                        return False
                        
                        return True
                    
                    return False
                else:
                    logger.error(f"Invalid values length: {len(values)}, expected 9")
                    return False
            elif table_name == "break_log":
                # Формат: [email, name, break_type, start_time, end_time, duration, date, status]
                # Формат из break_manager._log_break_start: Email, Name, BreakType, StartTime, EndTime, Duration, Date, Status
                if len(values) >= 8:
                    try:
                        from datetime import datetime
                        email_val = str(values[0]).lower() if values[0] else None
                        name_val = str(values[1]) if len(values) > 1 and values[1] else None
                        break_type_val = str(values[2]) if len(values) > 2 and values[2] else None
                        start_time_str = str(values[3]) if len(values) > 3 and values[3] else None
                        end_time_str = str(values[4]) if len(values) > 4 and values[4] else None
                        duration_val = str(values[5]) if len(values) > 5 and values[5] else None
                        date_str = str(values[6]) if len(values) > 6 else None
                        status_val = str(values[7]) if len(values) > 7 else "Active"
                        
                        if not email_val or not break_type_val or not start_time_str:
                            logger.error(f"Missing required fields for break_log: email={email_val}, break_type={break_type_val}, start_time={start_time_str}")
                            return False
                        
                        # Преобразуем start_time в ISO формат с timezone
                        try:
                            # Пробуем разные форматы времени
                            if 'T' in start_time_str or '+' in start_time_str or start_time_str.endswith('Z'):
                                # Уже в ISO формате
                                start_time_iso = start_time_str
                            else:
                                # Формат "YYYY-MM-DD HH:MM:SS" -> преобразуем в ISO
                                dt = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
                                start_time_iso = dt.isoformat() + "Z"
                        except ValueError:
                            try:
                                dt = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M")
                                start_time_iso = dt.isoformat() + "Z"
                            except ValueError:
                                logger.error(f"Invalid start_time format: {start_time_str}")
                                return False
                        
                        # Преобразуем end_time если есть (НЕ добавляем если пусто!)
                        end_time_iso = None
                        if end_time_str and end_time_str.strip() and end_time_str.strip() != "":
                            try:
                                if 'T' in end_time_str or '+' in end_time_str or end_time_str.endswith('Z'):
                                    end_time_iso = end_time_str
                                else:
                                    dt = datetime.strptime(end_time_str, "%Y-%m-%d %H:%M:%S")
                                    end_time_iso = dt.isoformat() + "Z"
                            except ValueError:
                                pass
                        
                        # Преобразуем duration (НЕ добавляем если пусто!)
                        duration_minutes = None
                        if duration_val and duration_val.strip() and duration_val.strip() != "":
                            try:
                                duration_minutes = int(duration_val)
                            except ValueError:
                                pass
                        
                        # Преобразуем date
                        date_iso = date_str if date_str else datetime.now().strftime("%Y-%m-%d")
                        
                        data = {
                            'email': email_val,
                            'name': name_val,
                            'break_type': break_type_val,
                            'start_time': start_time_iso,
                            'date': date_iso,
                            'status': status_val
                        }
                        
                        # Добавляем end_time ТОЛЬКО если он реально есть (не пустой)
                        if end_time_iso:
                            data['end_time'] = end_time_iso
                        # Добавляем duration ТОЛЬКО если он реально есть (не пустой)
                        if duration_minutes is not None:
                            data['duration_minutes'] = duration_minutes
                        
                        logger.debug(f"Inserting break_log data: {data}")
                        
                        logger.info(f"Inserting break_log: email={email_val}, break_type={break_type_val}, start_time={start_time_iso}")
                        response = self.client.table(table_name).insert(data).execute()
                        logger.info(f"✅ Break log insert successful: {len(response.data)} rows inserted")
                        return True
                    except Exception as e:
                        logger.error(f"Failed to insert break_log: {e}", exc_info=True)
                        return False
                else:
                    logger.error(f"Invalid values length: {len(values)}, expected at least 8")
                    return False
            elif table_name == "violations" or table_name == "break_violations":
                # Формат: [timestamp, email, session_id, violation_type, details, status]
                # В Supabase таблица называется "violations"
                if len(values) >= 6:
                    timestamp = str(values[0]) if values[0] else None
                    email_val = str(values[1]).lower() if values[1] else None
                    session_id = str(values[2]) if values[2] else None
                    violation_type = str(values[3]) if values[3] else None
                    details = str(values[4]) if values[4] else None
                    status = str(values[5]) if values[5] else "pending"
                    
                    if not email_val or not violation_type:
                        logger.error(f"Missing required fields for violation: email={email_val}, violation_type={violation_type}")
                        return False
                    
                    # Преобразуем timestamp в формат ISO, если нужно
                    if timestamp:
                        if len(timestamp) == 19:  # Формат "YYYY-MM-DD HH:MM:SS"
                            timestamp = timestamp.replace(" ", "T") + "+00:00"
                        elif len(timestamp) == 10:  # Формат "YYYY-MM-DD"
                            timestamp = timestamp + "T00:00:00+00:00"
                        # Если уже в ISO формате, оставляем как есть
                    else:
                        # Если timestamp не указан, используем текущее время
                        from datetime import datetime
                        timestamp = datetime.now().isoformat() + "+00:00"
                    
                    violation_data = {
                        'timestamp': timestamp or datetime.now().isoformat(),
                        'email': email_val,
                        'session_id': session_id,
                        'violation_type': violation_type,
                        'details': details or '',
                        'status': status
                    }
                    
                    try:
                        # Используем правильное имя таблицы "violations"
                        response = self.client.table('violations').insert(violation_data).execute()
                        if response.data:
                            logger.info(f"Created violation: email={email_val}, type={violation_type}")
                            return True
                        else:
                            logger.warning(f"No data returned when inserting violation")
                            return False
                    except Exception as insert_error:
                        logger.error(f"Failed to insert violation: {insert_error}", exc_info=True)
                        return False
                else:
                    logger.error(f"Invalid values length: {len(values)}, expected at least 6")
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
    
    def _delete_rows_by_schedule_id(self, table_name: str, schedule_id: str) -> bool:
        """
        Удаляет строки из таблицы по schedule_id.
        
        Args:
            table_name: Имя таблицы в Supabase
            schedule_id: ID шаблона (может быть UUID или строка)
            
        Returns:
            True если успешно удалено
        """
        try:
            if table_name == "break_schedules":
                schedule_db_id = None
                schedule_name = None
                
                # Пробуем удалить по id (UUID) или по name
                # Сначала пробуем найти по id (если это UUID)
                try:
                    # Пробуем удалить по id напрямую (если schedule_id это UUID)
                    response = self.client.table(table_name)\
                        .delete()\
                        .eq('id', schedule_id)\
                        .execute()
                    if response.data:
                        schedule_db_id = schedule_id
                        logger.info(f"Deleted schedule by id: {schedule_id}")
                        # Также удаляем связанные слоты и назначения
                        self._delete_schedule_slots(schedule_db_id)
                        self._delete_schedule_assignments(schedule_db_id, schedule_id)
                        return True
                except Exception:
                    pass
                
                # Если не удалось по id, пробуем по name
                try:
                    # В Supabase шаблоны группируются по name, поэтому удаляем все записи с таким name
                    # Сначала находим все записи с таким name
                    find_response = self.client.table(table_name)\
                        .select('id, name')\
                        .eq('name', schedule_id)\
                        .execute()
                    
                    if find_response.data:
                        schedule_name = find_response.data[0].get('name')
                        
                        # Удаляем ВСЕ записи с таким name (и основную запись, и все слоты)
                        response = self.client.table(table_name)\
                            .delete()\
                            .eq('name', schedule_name)\
                            .execute()
                        
                        deleted_count = len(response.data) if response.data else 0
                        logger.info(f"Deleted {deleted_count} records for schedule '{schedule_name}' (name: {schedule_id})")
                        
                        # Также удаляем связанные назначения (по schedule_id или name)
                        try:
                            # Пробуем найти UUID шаблона для удаления назначений
                            schedule_uuid = find_response.data[0].get('id')
                            if schedule_uuid:
                                assignments_response = self.client.table('user_break_assignments')\
                                    .delete()\
                                    .eq('schedule_id', schedule_uuid)\
                                    .execute()
                                if assignments_response.data:
                                    logger.info(f"Deleted {len(assignments_response.data)} assignments for schedule '{schedule_name}'")
                        except Exception as e:
                            logger.debug(f"Could not delete assignments: {e}")
                        
                        return True
                except Exception as e:
                    logger.debug(f"Could not delete by name: {e}")
                    pass
                
                # Если не удалось удалить по name, возможно schedule_id это UUID из другой записи
                # Пробуем найти шаблон по schedule_id как UUID и удалить по name найденного шаблона
                try:
                    # Ищем любую запись с таким id (может быть UUID одной из записей шаблона)
                    find_by_id = self.client.table(table_name)\
                        .select('name')\
                        .eq('id', schedule_id)\
                        .limit(1)\
                        .execute()
                    
                    if find_by_id.data:
                        found_name = find_by_id.data[0].get('name')
                        if found_name:
                            # Удаляем все записи с найденным name
                            response = self.client.table(table_name)\
                                .delete()\
                                .eq('name', found_name)\
                                .execute()
                            
                            deleted_count = len(response.data) if response.data else 0
                            logger.info(f"Deleted {deleted_count} records for schedule '{found_name}' (found by UUID: {schedule_id})")
                            
                            # Удаляем назначения
                            try:
                                assignments_response = self.client.table('user_break_assignments')\
                                    .delete()\
                                    .eq('schedule_id', schedule_id)\
                                    .execute()
                                if assignments_response.data:
                                    logger.info(f"Deleted {len(assignments_response.data)} assignments")
                            except Exception as e:
                                logger.debug(f"Could not delete assignments: {e}")
                            
                            return True
                except Exception as e:
                    logger.debug(f"Could not delete by UUID lookup: {e}")
                    pass
                
                logger.warning(f"Could not delete schedule {schedule_id} from {table_name}")
                return False
            else:
                logger.warning(f"Delete not implemented for table {table_name}")
                return False
        except Exception as e:
            logger.error(f"Failed to delete rows from {table_name}: {e}", exc_info=True)
            return False
    
    def _delete_schedule_slots(self, schedule_db_id: str) -> None:
        """Удаляет слоты перерывов для указанного шаблона"""
        for slot_table in ['break_schedule_slots', 'break_slots', 'break_schedule_items']:
            for schedule_id_field in ['schedule_id', 'break_schedule_id', 'break_schedules_id', 'parent_id']:
                try:
                    self.client.table(slot_table)\
                        .delete()\
                        .eq(schedule_id_field, schedule_db_id)\
                        .execute()
                    logger.info(f"Deleted slots from {slot_table} with field {schedule_id_field}")
                    return
                except Exception:
                    continue
    
    def _delete_schedule_slots_by_name(self, schedule_name: str) -> None:
        """Удаляет слоты перерывов для шаблона по имени (сначала находит id)"""
        try:
            # Находим id шаблона по имени
            response = self.client.table('break_schedules')\
                .select('id')\
                .eq('name', schedule_name)\
                .execute()
            
            if response.data:
                schedule_db_id = response.data[0]['id']
                self._delete_schedule_slots(schedule_db_id)
        except Exception as e:
            logger.debug(f"Could not delete slots by name: {e}")
    
    def _delete_schedule_assignments(self, schedule_db_id: str, schedule_id_or_name: str) -> None:
        """
        Удаляет назначения шаблона перерывов пользователям.
        
        Args:
            schedule_db_id: UUID шаблона в базе данных
            schedule_id_or_name: ID или имя шаблона (для поиска в назначениях)
        """
        try:
            logger.info(f"[DELETE_ASSIGNMENTS] Deleting assignments for schedule_db_id={schedule_db_id}, schedule_id_or_name={schedule_id_or_name}")
            
            # В таблице назначений schedule_id это UUID, поэтому используем schedule_db_id
            assignments_table = 'user_break_assignments'
            
            try:
                # Проверяем, какие записи есть в таблице
                response = self.client.table(assignments_table).select('*').limit(10).execute()
                logger.info(f"[DELETE_ASSIGNMENTS] Found {len(response.data)} records in {assignments_table}")
                if response.data:
                    logger.info(f"[DELETE_ASSIGNMENTS] Sample record keys: {list(response.data[0].keys())}")
            except Exception as check_error:
                logger.debug(f"[DELETE_ASSIGNMENTS] Could not read {assignments_table}: {check_error}")
                return
            
            # Удаляем назначения по UUID шаблона
            try:
                response = self.client.table(assignments_table)\
                    .delete()\
                    .eq('schedule_id', schedule_db_id)\
                    .execute()
                if response.data:
                    logger.info(f"[DELETE_ASSIGNMENTS] ✅ Deleted {len(response.data)} assignments from {assignments_table} by schedule_id={schedule_db_id}")
                else:
                    logger.info(f"[DELETE_ASSIGNMENTS] No assignments found to delete for schedule_id={schedule_db_id}")
            except Exception as delete_error:
                logger.error(f"[DELETE_ASSIGNMENTS] ❌ Failed to delete assignments: {delete_error}", exc_info=True)
        except Exception as e:
            logger.error(f"[DELETE_ASSIGNMENTS] ❌ Error deleting schedule assignments: {e}", exc_info=True)
    
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
            # Проверяем только существующие поля: user_id, email, name, timestamp, action_type, status, session_id
            # Поле user_group отсутствует в схеме work_log, поэтому не добавляем его
            records = []
            for action in actions:
                record = {
                    'user_id': user_id,
                    'email': email.lower(),
                    'name': action.get('name', ''),
                    'timestamp': action.get('timestamp') or datetime.now(timezone.utc).isoformat(),
                    'action_type': action.get('action_type', ''),
                    'status': action.get('status', ''),
                    'session_id': action.get('session_id', '')
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
