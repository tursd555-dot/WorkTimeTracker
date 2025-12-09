#!/usr/bin/env python3
"""
Создание листов для системы перерывов в Google Sheets
"""
from api_adapter import get_sheets_api

def create_break_sheets():
    """Создает необходимые листы для системы перерывов"""
    print("=" * 70)
    print("Создание листов для системы перерывов")
    print("=" * 70)
    print()
    
    # Инициализация API
    print("Подключение к Google Sheets...")
    sheets = get_sheets_api()
    
    # Получить spreadsheet через client
    spreadsheet = sheets.client.open_by_key(sheets._sheet_id)
    
    # Получить список существующих листов
    existing_sheets = [ws.title for ws in spreadsheet.worksheets()]
    print(f"Существующие листы: {', '.join(existing_sheets)}")
    print()
    
    # Определение листов для создания
    sheets_to_create = [
        {
            "name": "BreakSchedules",
            "headers": [
                "ScheduleID",
                "Name",
                "ShiftStart",
                "ShiftEnd",
                "SlotType",
                "Duration",
                "WindowStart",
                "WindowEnd",
                "Order"
            ]
        },
        {
            "name": "UserBreakAssignments",
            "headers": [
                "Email",
                "ScheduleID",
                "AssignedDate",
                "AssignedBy"
            ]
        },
        {
            "name": "BreakUsageLog",
            "headers": [
                "Email",
                "SessionID",
                "BreakType",
                "SlotOrder",
                "StartTime",
                "EndTime",
                "ExpectedDuration",
                "ActualDuration"
            ]
        },
        {
            "name": "BreakViolations",
            "headers": [
                "Timestamp",
                "Email",
                "SessionID",
                "ViolationType",
                "Details",
                "Status"
            ]
        }
    ]
    
    # Создание листов
    created = 0
    skipped = 0
    
    for sheet_def in sheets_to_create:
        name = sheet_def["name"]
        headers = sheet_def["headers"]
        
        if name in existing_sheets:
            print(f"⏭️  Лист '{name}' уже существует - пропускаем")
            skipped += 1
            continue
        
        try:
            print(f"📝 Создание листа '{name}'...")
            
            # Создать новый лист
            worksheet = spreadsheet.add_worksheet(
                title=name,
                rows=100,
                cols=len(headers)
            )
            
            # Добавить заголовки
            worksheet.append_row(headers)
            
            # Форматирование заголовков (жирный шрифт)
            worksheet.format('A1:' + chr(64 + len(headers)) + '1', {
                "textFormat": {"bold": True},
                "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}
            })
            
            print(f"   ✅ Создан с заголовками: {', '.join(headers)}")
            created += 1
            
        except Exception as e:
            print(f"   ❌ Ошибка при создании '{name}': {e}")
    
    print()
    print("=" * 70)
    print(f"Результат: создано {created}, пропущено {skipped}")
    print("=" * 70)
    
    if created > 0:
        print()
        print("✅ Листы успешно созданы!")
        print("🚀 Теперь можно создавать шаблоны перерывов в admin_app")
    elif skipped > 0:
        print()
        print("ℹ️  Все необходимые листы уже существуют")
    
    return created > 0 or skipped == len(sheets_to_create)


if __name__ == "__main__":
    try:
        success = create_break_sheets()
        exit(0 if success else 1)
    except Exception as e:
        print()
        print(f"❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        exit(1)