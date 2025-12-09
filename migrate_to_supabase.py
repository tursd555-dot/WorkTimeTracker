"""
Миграция данных из Google Sheets в Supabase
WorkTimeTracker v20.5
"""
import sys
import os
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any
import json

# Добавляем путь к проекту
sys.path.insert(0, 'D:\\proj vs code\\WorkTimeTracker')

from sheets_api import SheetsAPI
from supabase_api import SupabaseAPI, SupabaseConfig

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DataMigration:
    """Миграция данных из Google Sheets в Supabase"""
    
    def __init__(self):
        self.sheets = SheetsAPI()
        self.supabase = None  # Будет инициализирован после проверки
        self.stats = {
            'users': {'total': 0, 'migrated': 0, 'failed': 0},
            'work_log': {'total': 0, 'migrated': 0, 'failed': 0},
            'break_log': {'total': 0, 'migrated': 0, 'failed': 0},
            'violations': {'total': 0, 'migrated': 0, 'failed': 0}
        }
        
    def connect_supabase(self) -> bool:
        """Подключение к Supabase"""
        print("\n" + "="*80)
        print("🔌 ПОДКЛЮЧЕНИЕ К SUPABASE")
        print("="*80)
        
        # Проверяем переменные окружения
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        
        if not url or not key:
            print("\n❌ ОШИБКА: Переменные окружения не заданы!")
            print("\nНужно задать:")
            print("  SET SUPABASE_URL=https://your-project.supabase.co")
            print("  SET SUPABASE_KEY=your-anon-key")
            print("\nИли создайте файл .env с этими переменными")
            return False
        
        try:
            self.supabase = SupabaseAPI(SupabaseConfig(url=url, key=key))
            print(f"✅ Подключено к: {url}")
            return True
        except Exception as e:
            print(f"❌ Ошибка подключения: {e}")
            return False
    
    def backup_sheets_data(self) -> bool:
        """Создать backup данных из Google Sheets"""
        print("\n" + "="*80)
        print("📦 BACKUP ДАННЫХ ИЗ GOOGLE SHEETS")
        print("="*80)
        
        backup_file = f"backup_sheets_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            backup_data = {}
            
            # Users
            print("\n📋 Читаем Users...")
            users = self.sheets.get_users()
            backup_data['users'] = users
            print(f"   ✅ {len(users)} пользователей")
            
            # WorkLog
            print("📋 Читаем WorkLog...")
            ws = self.sheets.get_worksheet('WorkLog')
            work_log = self.sheets._read_table(ws)
            backup_data['work_log'] = work_log
            print(f"   ✅ {len(work_log)} записей")
            
            # BreakLog
            print("📋 Читаем BreakLog...")
            try:
                ws = self.sheets.get_worksheet('BreakLog')
                break_log = self.sheets._read_table(ws)
                backup_data['break_log'] = break_log
                print(f"   ✅ {len(break_log)} записей")
            except:
                print("   ⚠️  BreakLog не найден, пропускаем")
                backup_data['break_log'] = []
            
            # Violations
            print("📋 Читаем Violations...")
            try:
                ws = self.sheets.get_worksheet('Violations')
                violations = self.sheets._read_table(ws)
                backup_data['violations'] = violations
                print(f"   ✅ {len(violations)} записей")
            except:
                print("   ⚠️  Violations не найден, пропускаем")
                backup_data['violations'] = []
            
            # Сохраняем backup
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
            
            print(f"\n✅ Backup сохранен: {backup_file}")
            return True
            
        except Exception as e:
            print(f"\n❌ Ошибка backup: {e}")
            return False
    
    def migrate_users(self) -> bool:
        """Миграция пользователей"""
        print("\n" + "="*80)
        print("👥 МИГРАЦИЯ ПОЛЬЗОВАТЕЛЕЙ")
        print("="*80)
        
        try:
            users = self.sheets.get_users()
            self.stats['users']['total'] = len(users)
            
            print(f"\nВсего пользователей: {len(users)}")
            
            for i, user in enumerate(users, 1):
                try:
                    self.supabase.upsert_user(user)
                    self.stats['users']['migrated'] += 1
                    
                    if i % 10 == 0:
                        print(f"   Обработано: {i}/{len(users)}")
                        
                except Exception as e:
                    logger.error(f"Failed to migrate user {user.get('Email')}: {e}")
                    self.stats['users']['failed'] += 1
            
            print(f"\n✅ Мигрировано: {self.stats['users']['migrated']}/{len(users)}")
            if self.stats['users']['failed'] > 0:
                print(f"⚠️  Ошибки: {self.stats['users']['failed']}")
            
            return True
            
        except Exception as e:
            print(f"\n❌ Ошибка миграции пользователей: {e}")
            return False
    
    def migrate_work_log(self) -> bool:
        """Миграция рабочих логов"""
        print("\n" + "="*80)
        print("📊 МИГРАЦИЯ WORKLOG")
        print("="*80)
        
        try:
            ws = self.sheets.get_worksheet('WorkLog')
            records = self.sheets._read_table(ws)
            self.stats['work_log']['total'] = len(records)
            
            print(f"\nВсего записей: {len(records)}")
            print("⚠️  Это может занять несколько минут...")
            
            # Батчами по 100 записей
            batch_size = 100
            batches = [records[i:i+batch_size] for i in range(0, len(records), batch_size)]
            
            for batch_num, batch in enumerate(batches, 1):
                try:
                    # Преобразуем записи
                    supabase_records = []
                    for record in batch:
                        supabase_record = {
                            'email': record.get('Email', ''),
                            'name': record.get('Name', ''),
                            'timestamp': record.get('Timestamp', ''),
                            'action_type': record.get('Action', 'STATUS_CHANGE'),
                            'status': record.get('Status', ''),
                            'details': record.get('Details', ''),
                            'session_id': record.get('SessionID', '')
                        }
                        supabase_records.append(supabase_record)
                    
                    # Batch insert
                    self.supabase.batch_insert('work_log', supabase_records)
                    self.stats['work_log']['migrated'] += len(batch)
                    
                    print(f"   Batch {batch_num}/{len(batches)}: {self.stats['work_log']['migrated']}/{len(records)}")
                    
                except Exception as e:
                    logger.error(f"Failed batch {batch_num}: {e}")
                    self.stats['work_log']['failed'] += len(batch)
            
            print(f"\n✅ Мигрировано: {self.stats['work_log']['migrated']}/{len(records)}")
            if self.stats['work_log']['failed'] > 0:
                print(f"⚠️  Ошибки: {self.stats['work_log']['failed']}")
            
            return True
            
        except Exception as e:
            print(f"\n❌ Ошибка миграции WorkLog: {e}")
            return False
    
    def migrate_break_log(self) -> bool:
        """Миграция логов перерывов"""
        print("\n" + "="*80)
        print("☕ МИГРАЦИЯ BREAK LOG")
        print("="*80)
        
        try:
            ws = self.sheets.get_worksheet('BreakLog')
            records = self.sheets._read_table(ws)
            self.stats['break_log']['total'] = len(records)
            
            print(f"\nВсего записей: {len(records)}")
            
            batch_size = 100
            batches = [records[i:i+batch_size] for i in range(0, len(records), batch_size)]
            
            for batch_num, batch in enumerate(batches, 1):
                try:
                    supabase_records = []
                    for record in batch:
                        supabase_record = {
                            'email': record.get('Email', ''),
                            'name': record.get('Name', ''),
                            'break_type': record.get('BreakType', 'Перерыв'),
                            'start_time': record.get('StartTime', ''),
                            'end_time': record.get('EndTime', ''),
                            'duration_minutes': int(record.get('Duration', 0)) if record.get('Duration') else None,
                            'date': record.get('Date', ''),
                            'status': record.get('Status', 'Completed')
                        }
                        supabase_records.append(supabase_record)
                    
                    self.supabase.batch_insert('break_log', supabase_records)
                    self.stats['break_log']['migrated'] += len(batch)
                    
                    print(f"   Batch {batch_num}/{len(batches)}: {self.stats['break_log']['migrated']}/{len(records)}")
                    
                except Exception as e:
                    logger.error(f"Failed batch {batch_num}: {e}")
                    self.stats['break_log']['failed'] += len(batch)
            
            print(f"\n✅ Мигрировано: {self.stats['break_log']['migrated']}/{len(records)}")
            if self.stats['break_log']['failed'] > 0:
                print(f"⚠️  Ошибки: {self.stats['break_log']['failed']}")
            
            return True
            
        except Exception as e:
            print(f"\n❌ Ошибка миграции BreakLog: {e}")
            return False
    
    def verify_migration(self) -> bool:
        """Проверка миграции"""
        print("\n" + "="*80)
        print("✅ ПРОВЕРКА МИГРАЦИИ")
        print("="*80)
        
        try:
            # Проверяем количество записей
            supabase_users = self.supabase.get_users()
            print(f"\n👥 Пользователи:")
            print(f"   Google Sheets: {self.stats['users']['total']}")
            print(f"   Supabase:      {len(supabase_users)}")
            
            if len(supabase_users) == self.stats['users']['total']:
                print("   ✅ Совпадает!")
            else:
                print("   ⚠️  Расхождение!")
            
            # Можно добавить больше проверок...
            
            return True
            
        except Exception as e:
            print(f"\n❌ Ошибка проверки: {e}")
            return False
    
    def print_summary(self):
        """Вывести итоговую статистику"""
        print("\n" + "="*80)
        print("📊 ИТОГОВАЯ СТАТИСТИКА")
        print("="*80)
        
        total_migrated = sum(s['migrated'] for s in self.stats.values())
        total_failed = sum(s['failed'] for s in self.stats.values())
        
        print(f"\n{'Таблица':<20} {'Всего':<10} {'Успешно':<10} {'Ошибки':<10}")
        print("-" * 50)
        
        for table, stats in self.stats.items():
            print(f"{table:<20} {stats['total']:<10} {stats['migrated']:<10} {stats['failed']:<10}")
        
        print("-" * 50)
        print(f"{'ИТОГО:':<20} {'':<10} {total_migrated:<10} {total_failed:<10}")
        
        print("\n" + "="*80)
        
        if total_failed == 0:
            print("🎉 МИГРАЦИЯ ЗАВЕРШЕНА УСПЕШНО!")
        else:
            print(f"⚠️  МИГРАЦИЯ ЗАВЕРШЕНА С {total_failed} ОШИБКАМИ")
        
        print("="*80)
    
    def run(self):
        """Запуск полной миграции"""
        print("\n" + "="*80)
        print("🚀 МИГРАЦИЯ WORKTIMETRACKER")
        print("   Google Sheets → Supabase")
        print("="*80)
        
        # Проверяем Supabase
        if not self.connect_supabase():
            print("\n❌ Невозможно продолжить без подключения к Supabase")
            return False
        
        # Создаем backup
        print("\n⚠️  ВАЖНО: Создаем backup данных...")
        if not self.backup_sheets_data():
            response = input("\n⚠️  Backup не удался. Продолжить? (yes/no): ")
            if response.lower() != 'yes':
                print("\n❌ Миграция отменена")
                return False
        
        # Подтверждение
        print("\n" + "="*80)
        print("⚠️  ВНИМАНИЕ!")
        print("="*80)
        print("\nСейчас начнется миграция данных в Supabase.")
        print("Убедитесь что:")
        print("  1. Схема БД создана (supabase_schema.sql выполнен)")
        print("  2. У вас есть backup данных")
        print("  3. Переменные окружения настроены")
        print()
        
        response = input("Начать миграцию? (yes/no): ")
        if response.lower() != 'yes':
            print("\n❌ Миграция отменена")
            return False
        
        # Миграция
        success = True
        success = success and self.migrate_users()
        success = success and self.migrate_work_log()
        success = success and self.migrate_break_log()
        
        # Проверка
        self.verify_migration()
        
        # Итоги
        self.print_summary()
        
        return success


def main():
    """Главная функция"""
    migration = DataMigration()
    
    try:
        migration.run()
    except KeyboardInterrupt:
        print("\n\n⚠️  Миграция прервана пользователем")
    except Exception as e:
        print(f"\n\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
    
    input("\n\nНажмите Enter для выхода...")


if __name__ == "__main__":
    main()
