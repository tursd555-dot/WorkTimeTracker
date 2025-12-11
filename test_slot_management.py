#!/usr/bin/env python3
"""
Тестовый скрипт для диагностики проблем с управлением слотами:
1. Проблема с отображением 3 перерывов вместо 1 перерыва + 1 обеда
2. Проблема с удалением слотов
"""
import sys
import os
from datetime import datetime
import json

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api_adapter import get_sheets_api
from admin_app.break_manager import BreakManager

def test_slot_management():
    """Тестирует создание, чтение и обновление слотов"""
    print("=" * 70)
    print("ТЕСТ: Управление слотами в шаблонах")
    print("=" * 70)
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
        
        # Тестовый шаблон
        test_name = f"Тест слотов {datetime.now().strftime('%H:%M:%S')}"
        test_schedule_id = f"TEST_SLOTS_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # ШАГ 1: Создание шаблона с 1 перерывом
        print("=" * 70)
        print("ШАГ 1: Создание шаблона с 1 слотом (Перерыв)")
        print("=" * 70)
        
        slots_data_1 = [
            {
                "order": "1",
                "type": "Перерыв",
                "duration": "15",
                "window_start": "10:00",
                "window_end": "12:00"
            }
        ]
        
        print(f"   Создаём шаблон: {test_name}")
        print(f"   Слоты: {json.dumps(slots_data_1, ensure_ascii=False, indent=2)}")
        
        success = break_mgr.create_schedule_template(
            schedule_id=test_schedule_id,
            name=test_name,
            shift_start="09:00",
            shift_end="18:00",
            slots_data=slots_data_1
        )
        
        if not success:
            print("   ❌ Ошибка при создании шаблона")
            return False
        
        print("   ✅ Шаблон создан")
        
        # Проверяем, что сохранилось
        print("\n   📋 Проверка сохраненных данных:")
        ws = break_mgr.sheets.get_worksheet(break_mgr.SCHEDULES_SHEET)
        rows = break_mgr.sheets._read_table(ws)
        template_rows = [r for r in rows if r.get('Name') == test_name]
        print(f"      Найдено записей: {len(template_rows)}")
        for idx, row in enumerate(template_rows, 1):
            desc = row.get('Description') or ''
            slot_type = row.get('SlotType') or 'N/A'
            if desc:
                try:
                    slot_info = json.loads(desc)
                    slot_type = slot_info.get('slot_type', 'N/A')
                except:
                    pass
            print(f"      Запись {idx}: ScheduleID={row.get('ScheduleID')}, "
                  f"Description={'JSON' if desc else 'None'}, SlotType={slot_type}")
        
        # Проверяем через list_schedules
        schedules = break_mgr.list_schedules()
        test_schedule = next((s for s in schedules if s.get('name') == test_name), None)
        if test_schedule:
            print(f"\n   📋 Через list_schedules():")
            print(f"      schedule_id: {test_schedule.get('schedule_id')}")
            print(f"      name: {test_schedule.get('name')}")
            print(f"      slots_data: {len(test_schedule.get('slots_data', []))} слотов")
            for slot in test_schedule.get('slots_data', []):
                print(f"         - {slot.get('type')}: {slot.get('window_start')}-{slot.get('window_end')}")
        else:
            print(f"\n   ⚠️  Шаблон не найден через list_schedules()")
        
        # ШАГ 2: Добавление слота "Обед"
        print("\n" + "=" * 70)
        print("ШАГ 2: Добавление слота 'Обед' (обновление шаблона)")
        print("=" * 70)
        
        slots_data_2 = [
            {
                "order": "1",
                "type": "Перерыв",
                "duration": "15",
                "window_start": "10:00",
                "window_end": "12:00"
            },
            {
                "order": "2",
                "type": "Обед",
                "duration": "60",
                "window_start": "12:00",
                "window_end": "14:00"
            }
        ]
        
        print(f"   Обновляем шаблон: {test_name}")
        print(f"   Новые слоты: {json.dumps(slots_data_2, ensure_ascii=False, indent=2)}")
        
        success = break_mgr.update_schedule_template(
            schedule_id=test_schedule_id,
            name=test_name,
            shift_start="09:00",
            shift_end="18:00",
            slots_data=slots_data_2
        )
        
        if not success:
            print("   ❌ Ошибка при обновлении шаблона")
            return False
        
        print("   ✅ Шаблон обновлен")
        
        # Проверяем, что сохранилось
        print("\n   📋 Проверка сохраненных данных после обновления:")
        rows_after = break_mgr.sheets._read_table(ws)
        template_rows_after = [r for r in rows_after if r.get('Name') == test_name]
        print(f"      Найдено записей: {len(template_rows_after)}")
        for idx, row in enumerate(template_rows_after, 1):
            desc = row.get('Description') or ''
            slot_type = row.get('SlotType') or 'N/A'
            if desc:
                try:
                    slot_info = json.loads(desc)
                    slot_type = slot_info.get('slot_type', 'N/A')
                except:
                    pass
            print(f"      Запись {idx}: ScheduleID={row.get('ScheduleID')}, "
                  f"Description={'JSON' if desc else 'None'}, SlotType={slot_type}")
        
        # Проверяем через list_schedules
        schedules_after = break_mgr.list_schedules()
        test_schedule_after = next((s for s in schedules_after if s.get('name') == test_name), None)
        if test_schedule_after:
            print(f"\n   📋 Через list_schedules() после обновления:")
            print(f"      schedule_id: {test_schedule_after.get('schedule_id')}")
            print(f"      name: {test_schedule_after.get('name')}")
            slots_count = len(test_schedule_after.get('slots_data', []))
            print(f"      slots_data: {slots_count} слотов")
            
            if slots_count != 2:
                print(f"      ⚠️  ОЖИДАЛОСЬ 2 слота, получено {slots_count}!")
            
            for slot in test_schedule_after.get('slots_data', []):
                print(f"         - {slot.get('type')}: {slot.get('window_start')}-{slot.get('window_end')}")
            
            # Проверяем типы слотов
            slot_types = [s.get('type') for s in test_schedule_after.get('slots_data', [])]
            if slot_types.count('Перерыв') != 1:
                print(f"      ⚠️  ПРОБЛЕМА: Найдено {slot_types.count('Перерыв')} перерывов вместо 1!")
            if slot_types.count('Обед') != 1:
                print(f"      ⚠️  ПРОБЛЕМА: Найдено {slot_types.count('Обед')} обедов вместо 1!")
        else:
            print(f"\n   ⚠️  Шаблон не найден через list_schedules()")
        
        # ШАГ 3: Удаление слота (оставляем только Обед)
        print("\n" + "=" * 70)
        print("ШАГ 3: Удаление слота 'Перерыв' (оставляем только 'Обед')")
        print("=" * 70)
        
        slots_data_3 = [
            {
                "order": "1",
                "type": "Обед",
                "duration": "60",
                "window_start": "12:00",
                "window_end": "14:00"
            }
        ]
        
        print(f"   Обновляем шаблон: {test_name}")
        print(f"   Новые слоты: {json.dumps(slots_data_3, ensure_ascii=False, indent=2)}")
        
        success = break_mgr.update_schedule_template(
            schedule_id=test_schedule_id,
            name=test_name,
            shift_start="09:00",
            shift_end="18:00",
            slots_data=slots_data_3
        )
        
        if not success:
            print("   ❌ Ошибка при обновлении шаблона")
            return False
        
        print("   ✅ Шаблон обновлен")
        
        # Проверяем через list_schedules
        schedules_final = break_mgr.list_schedules()
        test_schedule_final = next((s for s in schedules_final if s.get('name') == test_name), None)
        if test_schedule_final:
            print(f"\n   📋 Через list_schedules() после удаления слота:")
            print(f"      schedule_id: {test_schedule_final.get('schedule_id')}")
            print(f"      name: {test_schedule_final.get('name')}")
            slots_count = len(test_schedule_final.get('slots_data', []))
            print(f"      slots_data: {slots_count} слотов")
            
            if slots_count != 1:
                print(f"      ⚠️  ОЖИДАЛОСЬ 1 слот, получено {slots_count}!")
            
            for slot in test_schedule_final.get('slots_data', []):
                print(f"         - {slot.get('type')}: {slot.get('window_start')}-{slot.get('window_end')}")
            
            # Проверяем тип слота
            slot_types = [s.get('type') for s in test_schedule_final.get('slots_data', [])]
            if 'Обед' not in slot_types:
                print(f"      ⚠️  ПРОБЛЕМА: Слот 'Обед' не найден!")
            if 'Перерыв' in slot_types:
                print(f"      ⚠️  ПРОБЛЕМА: Слот 'Перерыв' не был удален!")
        else:
            print(f"\n   ⚠️  Шаблон не найден через list_schedules()")
        
        print("\n" + "=" * 70)
        print("ТЕСТ ЗАВЕРШЕН")
        print("=" * 70)
        
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = test_slot_management()
    sys.exit(0 if success else 1)
