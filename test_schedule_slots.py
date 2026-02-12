#!/usr/bin/env python3
"""
Тестовый скрипт для проверки сохранения и чтения слотов в шаблонах
"""
import sys
import os
from datetime import datetime

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api_adapter import get_sheets_api
from admin_app.break_manager import BreakManager

def test_schedule_slots():
    """Тестирует сохранение и чтение слотов в шаблонах"""
    print("=" * 60)
    print("ТЕСТ: Сохранение и чтение слотов в шаблонах")
    print("=" * 60)
    print()
    
    try:
        # Инициализация API
        print("1. Инициализация API...")
        api = get_sheets_api()
        print(f"   ✅ API тип: {type(api).__name__}")
        print()
        
        # Инициализация BreakManager
        print("2. Инициализация BreakManager...")
        break_mgr = BreakManager(api)
        print()
        
        # Проверка таблицы break_schedules
        print("3. Проверка таблицы break_schedules...")
        try:
            ws = api.get_worksheet(break_mgr.SCHEDULES_SHEET)
            print(f"   ✅ Worksheet получен: {ws.table_name if hasattr(ws, 'table_name') else 'N/A'}")
            
            # Читаем все записи
            rows = api._read_table(ws)
            print(f"   ✅ Всего записей в таблице: {len(rows)}")
            
            if rows:
                print(f"   📋 Первая запись (ключи): {list(rows[0].keys())}")
                print(f"   📋 Первая запись (данные): {rows[0]}")
                print()
                
                # Группируем по name для Supabase
                schedules_by_name = {}
                for row in rows:
                    name = row.get('Name') or row.get('name') or ''
                    if name:
                        if name not in schedules_by_name:
                            schedules_by_name[name] = []
                        schedules_by_name[name].append(row)
                
                print(f"   📋 Уникальных шаблонов (по name): {len(schedules_by_name)}")
                for name, schedule_rows in list(schedules_by_name.items())[:3]:
                    print(f"      - {name}: {len(schedule_rows)} строк(и)")
                    for i, row in enumerate(schedule_rows[:2], 1):
                        slot_type = row.get('SlotType') or row.get('slot_type') or 'N/A'
                        duration = row.get('Duration') or row.get('duration') or 'N/A'
                        window_start = row.get('WindowStart') or row.get('window_start') or 'N/A'
                        window_end = row.get('WindowEnd') or row.get('window_end') or 'N/A'
                        print(f"         Слот {i}: тип={slot_type}, длительность={duration}, окно={window_start}-{window_end}")
                print()
        except Exception as e:
            print(f"   ❌ Ошибка при чтении таблицы: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # Тест: создание шаблона с несколькими слотами
        print("4. Тест создания шаблона с несколькими слотами...")
        test_schedule_id = f"TEST_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        test_name = f"Тестовый шаблон {datetime.now().strftime('%H:%M:%S')}"
        
        limits = [
            {"break_type": "Перерыв", "daily_count": 3, "time_minutes": 15},
            {"break_type": "Обед", "daily_count": 1, "time_minutes": 60}
        ]
        
        windows = [
            {"break_type": "Перерыв", "start": "10:00", "end": "12:00", "priority": 1},
            {"break_type": "Перерыв", "start": "14:00", "end": "16:00", "priority": 2},
            {"break_type": "Обед", "start": "12:00", "end": "14:00", "priority": 1}
        ]
        
        try:
            print(f"   Создаём шаблон: {test_name}")
            print(f"   Лимиты: {limits}")
            print(f"   Окна: {windows}")
            
            success = break_mgr.create_schedule(
                schedule_id=test_schedule_id,
                name=test_name,
                shift_start="09:00",
                shift_end="18:00",
                limits=limits,
                windows=windows
            )
            
            if success:
                print(f"   ✅ Шаблон создан успешно")
            else:
                print(f"   ❌ Ошибка при создании шаблона")
                return False
            print()
        except Exception as e:
            print(f"   ❌ Исключение при создании: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # Проверяем, что шаблон сохранился
        print("5. Проверка сохраненного шаблона...")
        try:
            # Читаем все записи снова
            rows_after = api._read_table(ws)
            print(f"   Всего записей после создания: {len(rows_after)}")
            
            # Ищем наш шаблон
            test_rows = [r for r in rows_after if r.get('Name') == test_name]
            print(f"   Найдено записей с именем '{test_name}': {len(test_rows)}")
            
            if test_rows:
                print(f"   📋 Записи шаблона:")
                for i, row in enumerate(test_rows, 1):
                    slot_type = row.get('SlotType') or row.get('slot_type') or 'N/A'
                    duration = row.get('Duration') or row.get('duration') or 'N/A'
                    window_start = row.get('WindowStart') or row.get('window_start') or 'N/A'
                    window_end = row.get('WindowEnd') or row.get('window_end') or 'N/A'
                    print(f"      {i}. Слот: тип={slot_type}, длительность={duration}, окно={window_start}-{window_end}")
                print()
            else:
                print(f"   ⚠️  Шаблон не найден в таблице!")
                print()
        except Exception as e:
            print(f"   ❌ Ошибка при проверке: {e}")
            import traceback
            traceback.print_exc()
        
        # Проверяем чтение через list_schedules
        print("6. Проверка чтения через list_schedules()...")
        try:
            schedules = break_mgr.list_schedules()
            test_schedule = next((s for s in schedules if s.get('name') == test_name), None)
            
            if test_schedule:
                print(f"   ✅ Шаблон найден через list_schedules")
                print(f"      schedule_id: {test_schedule.get('schedule_id')}")
                print(f"      name: {test_schedule.get('name')}")
                print(f"      shift_start: {test_schedule.get('shift_start')}")
                print(f"      shift_end: {test_schedule.get('shift_end')}")
                slots_data = test_schedule.get('slots_data', [])
                print(f"      slots_data: {len(slots_data)} слотов")
                
                if slots_data:
                    print(f"      📋 Слоты:")
                    for i, slot in enumerate(slots_data, 1):
                        print(f"         {i}. Порядок={slot.get('order')}, Тип={slot.get('type')}, "
                              f"Длительность={slot.get('duration')}, Окно={slot.get('window_start')}-{slot.get('window_end')}")
                else:
                    print(f"      ⚠️  Слоты не загружены!")
                
                # Дополнительная диагностика: проверяем сырые данные из таблицы
                print(f"\n   📋 Диагностика: проверяем сырые данные из таблицы...")
                ws = break_mgr.sheets.get_worksheet(break_mgr.SCHEDULES_SHEET)
                raw_rows = break_mgr.sheets._read_table(ws)
                template_rows = [r for r in raw_rows if r.get('Name') == test_name]
                print(f"      Найдено записей с именем '{test_name}': {len(template_rows)}")
                for idx, row in enumerate(template_rows[:4], 1):  # Показываем первые 4
                    print(f"      Запись {idx}:")
                    print(f"         ScheduleID: {row.get('ScheduleID')}")
                    print(f"         Name: {row.get('Name')}")
                    print(f"         Description: {row.get('Description')}")
                    print(f"         SlotType: {row.get('SlotType')}")
                    print(f"         Duration: {row.get('Duration')}")
                    print(f"         WindowStart: {row.get('WindowStart')}")
                    print(f"         WindowEnd: {row.get('WindowEnd')}")
                    print(f"         Order: {row.get('Order')}")
                print()
            else:
                print(f"   ⚠️  Шаблон не найден через list_schedules")
                print()
        except Exception as e:
            print(f"   ❌ Ошибка при чтении: {e}")
            import traceback
            traceback.print_exc()
        
        print("=" * 60)
        print("ТЕСТ ЗАВЕРШЕН")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = test_schedule_slots()
    sys.exit(0 if success else 1)
