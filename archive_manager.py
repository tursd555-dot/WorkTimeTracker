"""
Модуль автоматической архивации данных из Supabase в Google Таблицы
Экономит место на бесплатном тарифе Supabase
"""
import os
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from supabase_api import get_supabase_api, SupabaseAPI
    from sheets_api import get_sheets_api, SheetsAPI
    IMPORTS_AVAILABLE = True
except ImportError as e:
    IMPORTS_AVAILABLE = False
    logger.error(f"Failed to import required modules: {e}")


@dataclass
class ArchiveConfig:
    """Конфигурация архивации"""
    # Возраст данных для архивации (дни)
    archive_age_days: int = 90
    
    # Таблицы для архивации
    tables_to_archive: List[str] = None
    
    # Размер батча для экспорта
    batch_size: int = 1000
    
    # Удалять ли данные после архивации
    delete_after_archive: bool = True
    
    # ID Google Таблицы для архива
    archive_sheet_id: Optional[str] = None
    
    def __post_init__(self):
        if self.tables_to_archive is None:
            self.tables_to_archive = [
                'work_log',
                'break_log',
                'work_sessions',
                'violations',
                'sync_log'
            ]
        
        # Получаем ID таблицы из переменных окружения
        if not self.archive_sheet_id:
            self.archive_sheet_id = os.getenv("GOOGLE_ARCHIVE_SHEET_ID") or os.getenv("GOOGLE_SHEET_ID")


@dataclass
class ArchiveStats:
    """Статистика архивации"""
    table_name: str
    total_records: int = 0
    archived_records: int = 0
    deleted_records: int = 0
    failed_records: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    @property
    def duration_seconds(self) -> float:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0


class ArchiveManager:
    """Менеджер архивации данных"""
    
    def __init__(self, config: Optional[ArchiveConfig] = None):
        if not IMPORTS_AVAILABLE:
            raise ImportError("Required modules not available")
        
        self.config = config or ArchiveConfig()
        
        # Проверяем наличие Google Sheet ID
        if not self.config.archive_sheet_id:
            raise ValueError(
                "GOOGLE_ARCHIVE_SHEET_ID or GOOGLE_SHEET_ID must be set in environment variables"
            )
        
        self.supabase: SupabaseAPI = get_supabase_api()
        self.sheets: SheetsAPI = get_sheets_api()
        self.stats: Dict[str, ArchiveStats] = {}
        
        logger.info(f"✅ ArchiveManager initialized (age: {self.config.archive_age_days} days)")
    
    def _get_cutoff_date(self) -> datetime:
        """Получить дату отсечки для архивации"""
        return datetime.now(timezone.utc) - timedelta(days=self.config.archive_age_days)
    
    def _get_archive_sheet_name(self, table_name: str) -> str:
        """Получить имя листа для архивации таблицы"""
        return f"Archive_{table_name}"
    
    def _ensure_archive_sheet(self, sheet_name: str, headers: List[str]) -> None:
        """Создать лист архива в Google Таблице если его нет"""
        try:
            # Пытаемся получить лист
            self.sheets.get_worksheet(sheet_name)
            logger.debug(f"Archive sheet '{sheet_name}' already exists")
        except Exception:
            # Лист не существует, создаем его
            try:
                # Открываем таблицу
                if hasattr(self.sheets, '_sheet_cache') and '_spreadsheet' in self.sheets._sheet_cache:
                    spreadsheet = self.sheets._sheet_cache['_spreadsheet']
                else:
                    sheet_id = self.config.archive_sheet_id
                    if not sheet_id:
                        raise ValueError("GOOGLE_ARCHIVE_SHEET_ID or GOOGLE_SHEET_ID not set")
                    spreadsheet = self.sheets.client.open_by_key(sheet_id)
                
                # Создаем новый лист
                ws = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=len(headers))
                
                # Добавляем заголовки
                self.sheets._request_with_retry(
                    ws.update,
                    'A1',
                    [headers],
                    value_input_option='USER_ENTERED'
                )
                
                logger.info(f"✅ Created archive sheet '{sheet_name}' with headers: {headers}")
            except Exception as e:
                logger.error(f"Failed to create archive sheet '{sheet_name}': {e}")
                raise
    
    def _convert_record_to_row(self, record: Dict[str, Any], headers: List[str]) -> List[str]:
        """Преобразовать запись из Supabase в строку для Google Sheets"""
        row = []
        for header in headers:
            value = record.get(header, '')
            # Преобразуем типы данных
            if isinstance(value, datetime):
                value = value.isoformat()
            elif isinstance(value, date):
                value = value.isoformat()
            elif value is None:
                value = ''
            else:
                value = str(value)
            row.append(value)
        return row
    
    def _get_table_headers(self, table_name: str, sample_records: List[Dict]) -> List[str]:
        """Получить заголовки таблицы из записей"""
        if not sample_records:
            # Используем стандартные заголовки для известных таблиц
            default_headers = {
                'work_log': ['id', 'user_id', 'email', 'name', 'timestamp', 'action_type', 
                            'status', 'details', 'session_id', 'created_at'],
                'break_log': ['id', 'user_id', 'email', 'name', 'break_type', 'start_time',
                             'end_time', 'duration_minutes', 'date', 'status', 'is_over_limit',
                             'session_id', 'created_at', 'updated_at'],
                'work_sessions': ['id', 'session_id', 'user_id', 'email', 'login_time',
                                 'logout_time', 'duration_minutes', 'status', 'logout_type',
                                 'comment', 'created_at', 'updated_at'],
                'violations': ['id', 'user_id', 'email', 'name', 'violation_type', 'break_type',
                              'timestamp', 'expected_duration', 'actual_duration', 'excess_minutes',
                              'date', 'details', 'created_at'],
                'sync_log': ['id', 'sync_type', 'table_name', 'records_processed', 'records_success',
                            'records_failed', 'status', 'error_message', 'started_at', 'completed_at',
                            'duration_seconds']
            }
            return default_headers.get(table_name, [])
        
        # Получаем заголовки из первой записи
        return list(sample_records[0].keys())
    
    def _fetch_old_records(self, table_name: str, cutoff_date: datetime) -> List[Dict[str, Any]]:
        """Получить старые записи из таблицы Supabase"""
        try:
            # Определяем поле даты в зависимости от таблицы
            date_fields = {
                'work_log': 'timestamp',
                'break_log': 'date',
                'work_sessions': 'login_time',
                'violations': 'timestamp',
                'sync_log': 'started_at'
            }
            
            date_field = date_fields.get(table_name, 'created_at')
            
            # Для break_log используем date (DATE), для остальных - timestamp
            if table_name == 'break_log':
                # Преобразуем datetime в date для сравнения
                cutoff_date_str = cutoff_date.date().isoformat()
                # Используем .lt() для сравнения дат
                query = self.supabase.client.table(table_name)\
                    .select('*')\
                    .lt(date_field, cutoff_date_str)
                response = query.execute()
            else:
                # Для timestamp полей используем ISO формат
                cutoff_date_str = cutoff_date.isoformat()
                query = self.supabase.client.table(table_name)\
                    .select('*')\
                    .lt(date_field, cutoff_date_str)
                # Supabase может иметь лимиты, получаем все записи по частям если нужно
                response = query.execute()
            
            records = response.data if hasattr(response, 'data') else []
            logger.info(f"Found {len(records)} old records in '{table_name}' (older than {cutoff_date.date()})")
            return records
            
        except Exception as e:
            logger.error(f"Failed to fetch old records from '{table_name}': {e}", exc_info=True)
            return []
    
    def _export_to_sheets(self, table_name: str, records: List[Dict[str, Any]]) -> bool:
        """Экспортировать записи в Google Таблицу"""
        if not records:
            logger.warning(f"No records to export for '{table_name}'")
            return True
        
        try:
            # Получаем заголовки
            headers = self._get_table_headers(table_name, records[:1] if records else [])
            
            # Создаем/проверяем лист архива
            sheet_name = self._get_archive_sheet_name(table_name)
            self._ensure_archive_sheet(sheet_name, headers)
            
            # Преобразуем записи в строки
            rows = []
            for record in records:
                row = self._convert_record_to_row(record, headers)
                rows.append(row)
            
            # Экспортируем батчами
            batch_size = self.config.batch_size
            total_batches = (len(rows) + batch_size - 1) // batch_size
            
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                
                try:
                    ws = self.sheets.get_worksheet(sheet_name)
                    self.sheets._request_with_retry(
                        ws.append_rows,
                        batch,
                        value_input_option='USER_ENTERED'
                    )
                    logger.info(f"Exported batch {batch_num}/{total_batches} ({len(batch)} rows) to '{sheet_name}'")
                except Exception as e:
                    logger.error(f"Failed to export batch {batch_num} to '{sheet_name}': {e}")
                    return False
            
            logger.info(f"✅ Successfully exported {len(records)} records to '{sheet_name}'")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export records to sheets for '{table_name}': {e}")
            return False
    
    def _delete_from_supabase(self, table_name: str, record_ids: List[str]) -> int:
        """Удалить записи из Supabase по ID"""
        if not record_ids:
            return 0
        
        try:
            deleted_count = 0
            batch_size = 100  # Supabase может иметь лимиты на размер запроса
            
            for i in range(0, len(record_ids), batch_size):
                batch_ids = record_ids[i:i + batch_size]
                
                try:
                    # Удаляем по одному ID за раз (Supabase может не поддерживать .in_() для delete)
                    # Или используем цикл для каждого ID
                    for record_id in batch_ids:
                        try:
                            self.supabase.client.table(table_name)\
                                .delete()\
                                .eq('id', record_id)\
                                .execute()
                            deleted_count += 1
                        except Exception as e:
                            logger.warning(f"Failed to delete record {record_id} from '{table_name}': {e}")
                    
                    logger.debug(f"Deleted batch {i//batch_size + 1} ({len(batch_ids)} records) from '{table_name}'")
                    
                except Exception as e:
                    logger.error(f"Failed to delete batch from '{table_name}': {e}")
                    # Продолжаем с следующим батчем
            
            logger.info(f"✅ Deleted {deleted_count} records from '{table_name}'")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to delete records from '{table_name}': {e}", exc_info=True)
            return 0
    
    def archive_table(self, table_name: str) -> ArchiveStats:
        """Архивировать одну таблицу"""
        stats = ArchiveStats(table_name=table_name, start_time=datetime.now(timezone.utc))
        self.stats[table_name] = stats
        
        logger.info(f"🔄 Starting archive for table '{table_name}'")
        
        try:
            # Получаем старые записи
            cutoff_date = self._get_cutoff_date()
            records = self._fetch_old_records(table_name, cutoff_date)
            stats.total_records = len(records)
            
            if not records:
                logger.info(f"✅ No records to archive for '{table_name}'")
                stats.end_time = datetime.now(timezone.utc)
                return stats
            
            # Экспортируем в Google Sheets
            export_success = self._export_to_sheets(table_name, records)
            
            if export_success:
                stats.archived_records = len(records)
                
                # Удаляем из Supabase если настроено
                if self.config.delete_after_archive:
                    record_ids = [str(r.get('id', '')) for r in records if r.get('id')]
                    if record_ids:
                        deleted = self._delete_from_supabase(table_name, record_ids)
                        stats.deleted_records = deleted
                else:
                    logger.info(f"⚠️  Skipping deletion (delete_after_archive=False)")
            else:
                stats.failed_records = len(records)
                logger.error(f"❌ Failed to export records for '{table_name}', skipping deletion")
            
            stats.end_time = datetime.now(timezone.utc)
            logger.info(
                f"✅ Archive completed for '{table_name}': "
                f"{stats.archived_records} archived, "
                f"{stats.deleted_records} deleted, "
                f"{stats.failed_records} failed "
                f"({stats.duration_seconds:.1f}s)"
            )
            
        except Exception as e:
            stats.end_time = datetime.now(timezone.utc)
            stats.failed_records = stats.total_records
            logger.error(f"❌ Archive failed for '{table_name}': {e}", exc_info=True)
        
        return stats
    
    def archive_all(self) -> Dict[str, ArchiveStats]:
        """Архивировать все настроенные таблицы"""
        logger.info(f"🚀 Starting archive process for {len(self.config.tables_to_archive)} tables")
        
        all_stats = {}
        for table_name in self.config.tables_to_archive:
            try:
                stats = self.archive_table(table_name)
                all_stats[table_name] = stats
            except Exception as e:
                logger.error(f"Failed to archive table '{table_name}': {e}", exc_info=True)
                all_stats[table_name] = ArchiveStats(
                    table_name=table_name,
                    failed_records=1,
                    start_time=datetime.now(timezone.utc),
                    end_time=datetime.now(timezone.utc)
                )
        
        # Выводим итоговую статистику
        total_archived = sum(s.archived_records for s in all_stats.values())
        total_deleted = sum(s.deleted_records for s in all_stats.values())
        total_failed = sum(s.failed_records for s in all_stats.values())
        
        logger.info(
            f"🎉 Archive process completed: "
            f"{total_archived} archived, "
            f"{total_deleted} deleted, "
            f"{total_failed} failed"
        )
        
        return all_stats
    
    def get_stats_summary(self) -> Dict[str, Any]:
        """Получить сводку статистики архивации"""
        if not self.stats:
            return {}
        
        summary = {
            'tables': {},
            'total': {
                'archived': 0,
                'deleted': 0,
                'failed': 0,
                'duration': 0.0
            }
        }
        
        for table_name, stats in self.stats.items():
            summary['tables'][table_name] = {
                'total': stats.total_records,
                'archived': stats.archived_records,
                'deleted': stats.deleted_records,
                'failed': stats.failed_records,
                'duration': stats.duration_seconds
            }
            
            summary['total']['archived'] += stats.archived_records
            summary['total']['deleted'] += stats.deleted_records
            summary['total']['failed'] += stats.failed_records
            summary['total']['duration'] += stats.duration_seconds
        
        return summary


def main():
    """Основная функция для запуска архивации"""
    import sys
    
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('archive.log', encoding='utf-8')
        ]
    )
    
    try:
        # Создаем менеджер архивации
        config = ArchiveConfig(
            archive_age_days=int(os.getenv("ARCHIVE_AGE_DAYS", "90")),
            delete_after_archive=os.getenv("ARCHIVE_DELETE_AFTER", "1").lower() == "1",
            batch_size=int(os.getenv("ARCHIVE_BATCH_SIZE", "1000"))
        )
        
        manager = ArchiveManager(config)
        
        # Запускаем архивацию
        stats = manager.archive_all()
        
        # Выводим статистику
        summary = manager.get_stats_summary()
        print("\n" + "="*60)
        print("ARCHIVE SUMMARY")
        print("="*60)
        for table_name, table_stats in summary.get('tables', {}).items():
            print(f"\n{table_name}:")
            print(f"  Total records: {table_stats['total']}")
            print(f"  Archived: {table_stats['archived']}")
            print(f"  Deleted: {table_stats['deleted']}")
            print(f"  Failed: {table_stats['failed']}")
            print(f"  Duration: {table_stats['duration']:.1f}s")
        
        total = summary.get('total', {})
        print(f"\nTOTAL:")
        print(f"  Archived: {total.get('archived', 0)}")
        print(f"  Deleted: {total.get('deleted', 0)}")
        print(f"  Failed: {total.get('failed', 0)}")
        print(f"  Duration: {total.get('duration', 0):.1f}s")
        print("="*60)
        
        # Возвращаем код выхода
        if total.get('failed', 0) > 0:
            sys.exit(1)
        else:
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"Archive process failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
