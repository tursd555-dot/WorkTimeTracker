"""
Синхронизация данных из Supabase в Google Sheets
Для отчетов и визуального просмотра
"""
import sys
import os
import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Any

sys.path.insert(0, 'D:\\proj vs code\\WorkTimeTracker')

from sheets_api import SheetsAPI
from supabase_api import get_supabase_api
from shared.sheets_batching import BatchManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SupabaseToSheetsSync:
    """Синхронизация Supabase → Google Sheets"""
    
    def __init__(self):
        self.supabase = get_supabase_api()
        self.sheets = SheetsAPI()
        self.stats = {}
    
    def sync_users(self) -> bool:
        """
        Синхронизация пользователей
        Полная перезапись листа Users
        """
        print("\n👥 Синхронизация пользователей...")
        
        try:
            # Читаем из Supabase
            users = self.supabase.get_users()
            
            # Очищаем лист (кроме заголовка)
            ws = self.sheets.get_worksheet('Users')
            self.sheets._request_with_retry(lambda: ws.clear())
            
            # Заголовки
            headers = ['Email', 'Name', 'Phone', 'Role', 'Telegram', 'Group', 'NotifyTelegram']
            
            # Формируем данные
            data = [headers]
            for user in users:
                row = [
                    user.get('Email', ''),
                    user.get('Name', ''),
                    user.get('Phone', ''),
                    user.get('Role', ''),
                    user.get('Telegram', ''),
                    user.get('Group', ''),
                    user.get('NotifyTelegram', 'No')
                ]
                data.append(row)
            
            # Записываем батчем
            self.sheets._request_with_retry(
                lambda: ws.update('A1', data, value_input_option='USER_ENTERED')
            )
            
            self.stats['users'] = len(users)
            print(f"   ✅ Синхронизировано: {len(users)} пользователей")
            return True
            
        except Exception as e:
            logger.error(f"Failed to sync users: {e}")
            print(f"   ❌ Ошибка: {e}")
            return False
    
    def sync_daily_worklog(self, days_back: int = 7) -> bool:
        """
        Синхронизация WorkLog за последние N дней
        
        Args:
            days_back: Количество дней назад
        """
        print(f"\n📊 Синхронизация WorkLog (последние {days_back} дней)...")
        
        try:
            # Читаем из Supabase
            start_date = (date.today() - timedelta(days=days_back)).isoformat()
            
            response = self.supabase.client.table('work_log')\
                .select('*')\
                .gte('timestamp', start_date)\
                .order('timestamp', desc=True)\
                .execute()
            
            records = response.data
            
            # Очищаем лист
            ws = self.sheets.get_worksheet('WorkLog')
            self.sheets._request_with_retry(lambda: ws.clear())
            
            # Заголовки
            headers = ['Email', 'Name', 'Timestamp', 'Action', 'Status', 'Details', 'SessionID']
            
            # Формируем данные
            data = [headers]
            for record in records:
                row = [
                    record.get('email', ''),
                    record.get('name', ''),
                    record.get('timestamp', ''),
                    record.get('action_type', ''),
                    record.get('status', ''),
                    record.get('details', ''),
                    record.get('session_id', '')
                ]
                data.append(row)
            
            # Записываем батчем
            self.sheets._request_with_retry(
                lambda: ws.update('A1', data, value_input_option='USER_ENTERED')
            )
            
            self.stats['work_log'] = len(records)
            print(f"   ✅ Синхронизировано: {len(records)} записей")
            return True
            
        except Exception as e:
            logger.error(f"Failed to sync worklog: {e}")
            print(f"   ❌ Ошибка: {e}")
            return False
    
    def sync_active_sessions(self) -> bool:
        """Синхронизация активных сессий"""
        print("\n🔄 Синхронизация активных сессий...")
        
        try:
            # Читаем из Supabase
            sessions = self.supabase.get_active_sessions()
            
            # Очищаем лист
            ws = self.sheets.get_worksheet('ActiveSessions')
            self.sheets._request_with_retry(lambda: ws.clear())
            
            # Заголовки
            headers = ['SessionID', 'Email', 'Name', 'Group', 'LoginTime', 'Duration', 'Status']
            
            # Формируем данные
            data = [headers]
            for session in sessions:
                row = [
                    session.get('session_id', ''),
                    session.get('email', ''),
                    session.get('name', ''),
                    session.get('group_name', ''),
                    session.get('login_time', ''),
                    str(int(session.get('duration_minutes', 0))),
                    session.get('status', '')
                ]
                data.append(row)
            
            # Записываем
            self.sheets._request_with_retry(
                lambda: ws.update('A1', data, value_input_option='USER_ENTERED')
            )
            
            self.stats['active_sessions'] = len(sessions)
            print(f"   ✅ Синхронизировано: {len(sessions)} активных сессий")
            return True
            
        except Exception as e:
            logger.error(f"Failed to sync active sessions: {e}")
            print(f"   ❌ Ошибка: {e}")
            return False
    
    def sync_break_log(self, days_back: int = 7) -> bool:
        """
        Синхронизация BreakLog за последние N дней
        
        Args:
            days_back: Количество дней назад
        """
        print(f"\n☕ Синхронизация BreakLog (последние {days_back} дней)...")
        
        try:
            # Читаем из Supabase
            start_date = (date.today() - timedelta(days=days_back)).isoformat()
            
            response = self.supabase.client.table('break_log')\
                .select('*')\
                .gte('date', start_date)\
                .order('start_time', desc=True)\
                .execute()
            
            records = response.data
            
            # Очищаем лист
            ws = self.sheets.get_worksheet('BreakLog')
            self.sheets._request_with_retry(lambda: ws.clear())
            
            # Заголовки
            headers = ['Email', 'Name', 'BreakType', 'StartTime', 'EndTime', 'Duration', 'Date', 'Status']
            
            # Формируем данные
            data = [headers]
            for record in records:
                row = [
                    record.get('email', ''),
                    record.get('name', ''),
                    record.get('break_type', ''),
                    record.get('start_time', ''),
                    record.get('end_time', ''),
                    str(record.get('duration_minutes', '')) if record.get('duration_minutes') else '',
                    record.get('date', ''),
                    record.get('status', '')
                ]
                data.append(row)
            
            # Записываем
            self.sheets._request_with_retry(
                lambda: ws.update('A1', data, value_input_option='USER_ENTERED')
            )
            
            self.stats['break_log'] = len(records)
            print(f"   ✅ Синхронизировано: {len(records)} записей")
            return True
            
        except Exception as e:
            logger.error(f"Failed to sync break log: {e}")
            print(f"   ❌ Ошибка: {e}")
            return False
    
    def sync_violations(self, days_back: int = 30) -> bool:
        """
        Синхронизация нарушений за последние N дней
        
        Args:
            days_back: Количество дней назад
        """
        print(f"\n⚠️  Синхронизация нарушений (последние {days_back} дней)...")
        
        try:
            # Читаем из Supabase
            start_date = (date.today() - timedelta(days=days_back)).isoformat()
            
            response = self.supabase.client.table('violations')\
                .select('*')\
                .gte('date', start_date)\
                .order('timestamp', desc=True)\
                .execute()
            
            records = response.data
            
            # Очищаем лист
            ws = self.sheets.get_worksheet('Violations')
            self.sheets._request_with_retry(lambda: ws.clear())
            
            # Заголовки
            headers = ['Email', 'Name', 'Type', 'BreakType', 'Timestamp', 'Expected', 'Actual', 'Excess', 'Date']
            
            # Формируем данные
            data = [headers]
            for record in records:
                row = [
                    record.get('email', ''),
                    record.get('name', ''),
                    record.get('violation_type', ''),
                    record.get('break_type', ''),
                    record.get('timestamp', ''),
                    str(record.get('expected_duration', '')),
                    str(record.get('actual_duration', '')),
                    str(record.get('excess_minutes', '')),
                    record.get('date', '')
                ]
                data.append(row)
            
            # Записываем
            self.sheets._request_with_retry(
                lambda: ws.update('A1', data, value_input_option='USER_ENTERED')
            )
            
            self.stats['violations'] = len(records)
            print(f"   ✅ Синхронизировано: {len(records)} нарушений")
            return True
            
        except Exception as e:
            logger.error(f"Failed to sync violations: {e}")
            print(f"   ❌ Ошибка: {e}")
            return False
    
    def sync_daily_stats(self) -> bool:
        """Синхронизация ежедневной статистики"""
        print("\n📈 Синхронизация статистики за сегодня...")
        
        try:
            # Читаем из Supabase
            stats = self.supabase.get_daily_stats()
            
            # Создаем или очищаем лист
            try:
                ws = self.sheets.get_worksheet('DailyStats')
            except:
                # Создаем новый лист
                spreadsheet = self.sheets.client.open_by_key(self.sheets._sheet_id)
                ws = spreadsheet.add_worksheet(title='DailyStats', rows=500, cols=10)
            
            self.sheets._request_with_retry(lambda: ws.clear())
            
            # Заголовки
            headers = ['Email', 'Name', 'Sessions', 'WorkMinutes', 'Breaks', 'BreakMinutes', 'Violations']
            
            # Формируем данные
            data = [headers]
            for stat in stats:
                row = [
                    stat.get('email', ''),
                    stat.get('name', ''),
                    str(stat.get('sessions_today', 0)),
                    str(stat.get('work_minutes_today', 0)),
                    str(stat.get('breaks_today', 0)),
                    str(stat.get('break_minutes_today', 0)),
                    str(stat.get('violations_today', 0))
                ]
                data.append(row)
            
            # Записываем
            self.sheets._request_with_retry(
                lambda: ws.update('A1', data, value_input_option='USER_ENTERED')
            )
            
            self.stats['daily_stats'] = len(stats)
            print(f"   ✅ Синхронизировано: {len(stats)} пользователей")
            return True
            
        except Exception as e:
            logger.error(f"Failed to sync daily stats: {e}")
            print(f"   ❌ Ошибка: {e}")
            return False
    
    def log_sync(self, status: str, error_message: str = ""):
        """Записать лог синхронизации в Supabase"""
        try:
            data = {
                'sync_type': 'export_to_sheets',
                'table_name': 'all_tables',
                'records_processed': sum(self.stats.values()),
                'records_success': sum(self.stats.values()),
                'records_failed': 0,
                'status': status,
                'error_message': error_message,
                'completed_at': datetime.now().isoformat(),
                'duration_seconds': 0  # Можно добавить таймер
            }
            
            self.supabase.client.table('sync_log').insert(data).execute()
        except Exception as e:
            logger.error(f"Failed to log sync: {e}")
    
    def run_full_sync(self):
        """Запуск полной синхронизации"""
        print("\n" + "="*80)
        print("🔄 СИНХРОНИЗАЦИЯ SUPABASE → GOOGLE SHEETS")
        print("="*80)
        
        start_time = datetime.now()
        
        success = True
        success = success and self.sync_users()
        success = success and self.sync_active_sessions()
        success = success and self.sync_daily_worklog(days_back=7)
        success = success and self.sync_break_log(days_back=7)
        success = success and self.sync_violations(days_back=30)
        success = success and self.sync_daily_stats()
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Итоги
        print("\n" + "="*80)
        print("📊 ИТОГИ СИНХРОНИЗАЦИИ")
        print("="*80)
        print(f"\n{'Таблица':<20} {'Записей':<10}")
        print("-" * 30)
        for table, count in self.stats.items():
            print(f"{table:<20} {count:<10}")
        print("-" * 30)
        print(f"{'ИТОГО:':<20} {sum(self.stats.values()):<10}")
        print(f"\nВремя выполнения: {duration:.1f} сек")
        print("="*80)
        
        # Логируем
        if success:
            print("\n✅ СИНХРОНИЗАЦИЯ ЗАВЕРШЕНА УСПЕШНО!")
            self.log_sync('completed')
        else:
            print("\n⚠️  СИНХРОНИЗАЦИЯ ЗАВЕРШЕНА С ОШИБКАМИ")
            self.log_sync('completed_with_errors', 'Some tables failed')
        
        return success


def main():
    """Главная функция"""
    print("WorkTimeTracker - Синхронизация отчетов")
    print("Supabase → Google Sheets")
    print()
    
    sync = SupabaseToSheetsSync()
    
    try:
        sync.run_full_sync()
    except KeyboardInterrupt:
        print("\n\n⚠️  Синхронизация прервана")
    except Exception as e:
        print(f"\n\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
    
    input("\n\nНажмите Enter для выхода...")


if __name__ == "__main__":
    main()
