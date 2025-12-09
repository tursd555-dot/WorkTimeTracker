"""
Создание пустых листов BreakSchedules и UserBreakAssignments
Устраняет проблему лишних API запросов
"""
import sys
sys.path.insert(0, 'D:\\proj vs code\\WorkTimeTracker')

from api_adapter import SheetsAPI

def create_empty_schedule_sheets():
    """Создает пустые листы графиков перерывов"""
    print("="*80)
    print("📝 СОЗДАНИЕ ПУСТЫХ ЛИСТОВ ГРАФИКОВ")
    print("="*80)
    print()
    
    print("Эти листы нужны для работы BreakManager,")
    print("но могут быть пустыми если вы используете дефолтные лимиты.")
    print()
    
    # Подключение
    print("Подключение к Google Sheets...")
    api = SheetsAPI()
    spreadsheet = api.client.open_by_key(api._sheet_id)
    print(f"✅ Подключено: {spreadsheet.title}")
    print()
    
    # Проверяем существующие листы
    existing_sheets = {ws.title for ws in spreadsheet.worksheets()}
    
    sheets_to_create = {
        'BreakSchedules': [
            'ScheduleID',
            'Name',
            'Description',
            'CreatedDate',
            'CreatedBy',
            'IsActive'
        ],
        'UserBreakAssignments': [
            'Email',
            'ScheduleID',
            'AssignedDate',
            'AssignedBy',
            'IsActive'
        ]
    }
    
    created = 0
    skipped = 0
    
    for sheet_name, headers in sheets_to_create.items():
        if sheet_name in existing_sheets:
            print(f"⏭️  {sheet_name}: уже существует, пропускаем")
            skipped += 1
            continue
        
        try:
            # Создаем лист
            ws = spreadsheet.add_worksheet(
                title=sheet_name,
                rows=100,
                cols=len(headers)
            )
            
            # Добавляем заголовки
            ws.append_row(headers, value_input_option='USER_ENTERED')
            
            # Форматируем заголовки
            ws.format('A1:{}1'.format(chr(65 + len(headers) - 1)), {
                'textFormat': {'bold': True},
                'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
            })
            
            print(f"✅ {sheet_name}: создан ({len(headers)} колонок)")
            created += 1
            
        except Exception as e:
            print(f"❌ {sheet_name}: ОШИБКА - {e}")
    
    print()
    print("="*80)
    print("📊 РЕЗУЛЬТАТ")
    print("="*80)
    print()
    print(f"Создано: {created}")
    print(f"Пропущено (уже существуют): {skipped}")
    print()
    
    if created > 0:
        print("✅ ГОТОВО!")
        print()
        print("Теперь Admin App не будет делать лишние retry.")
        print("Листы пустые, но это нормально - система использует дефолтные лимиты.")
        print()
        print("💡 ОПЦИОНАЛЬНО:")
        print("Вы можете добавить данные в эти листы если хотите")
        print("настроить индивидуальные графики перерывов.")
    else:
        print("ℹ️  Все листы уже существуют.")
        print("Проблема НЕ в отсутствии листов.")
        print()
        print("Возможные причины превышения лимита API:")
        print("  1. Слишком много retry на другие операции")
        print("  2. Много одновременных запросов")
        print("  3. Другое приложение использует ту же квоту")
        print()
        print("Рекомендация:")
        print("  - Подождите 5 минут")
        print("  - Установите кэширование (data_cache.py)")

if __name__ == "__main__":
    try:
        create_empty_schedule_sheets()
    except KeyboardInterrupt:
        print("\n\n⚠️  Прервано пользователем")
    except Exception as e:
        print(f"\n\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
    
    input("\n\nНажмите Enter для выхода...")
