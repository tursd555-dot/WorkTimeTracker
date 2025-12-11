#!/usr/bin/env python3
"""
Тестовый скрипт для диагностики отображения активных перерывов в дашборде
"""
import sys
import os
from datetime import datetime, date

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api_adapter import get_sheets_api
from admin_app.break_manager import BreakManager

def test_active_breaks():
    """Тестирует получение активных перерывов"""
    print("=" * 60)
    print("ТЕСТ: Отображение активных перерывов в дашборде")
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
        print(f"   ✅ USAGE_LOG_SHEET: {break_mgr.USAGE_LOG_SHEET}")
        print()
        
        # Проверка таблицы break_log
        print("3. Проверка таблицы break_log...")
        try:
            ws = api.get_worksheet(break_mgr.USAGE_LOG_SHEET)
            print(f"   ✅ Worksheet получен: {ws.table_name if hasattr(ws, 'table_name') else 'N/A'}")
            
            # Читаем все записи
            rows = api._read_table(ws)
            print(f"   ✅ Всего записей в таблице: {len(rows)}")
            
            if rows:
                print(f"   📋 Первая запись (ключи): {list(rows[0].keys())}")
                print(f"   📋 Первая запись (данные): {rows[0]}")
            print()
        except Exception as e:
            print(f"   ❌ Ошибка при чтении таблицы: {e}")
            import traceback
            traceback.print_exc()
            print()
        
        # Получаем активные перерывы
        print("4. Получение активных перерывов через get_all_active_breaks()...")
        try:
            active_breaks = break_mgr.get_all_active_breaks()
            print(f"   ✅ Найдено активных перерывов: {len(active_breaks)}")
            
            if active_breaks:
                print("   📋 Список активных перерывов:")
                for i, br in enumerate(active_breaks, 1):
                    print(f"      {i}. Email: {br.get('Email', 'N/A')}")
                    print(f"         Name: {br.get('Name', 'N/A')}")
                    print(f"         BreakType: {br.get('BreakType', 'N/A')}")
                    print(f"         StartTime: {br.get('StartTime', 'N/A')}")
                    print(f"         Duration: {br.get('Duration', 'N/A')} мин")
                    print(f"         is_over_limit: {br.get('is_over_limit', False)}")
                    print()
            else:
                print("   ⚠️  Активных перерывов не найдено")
                print()
                
                # Проверяем все записи за сегодня
                print("   5. Проверка всех записей за сегодня...")
                today = date.today().isoformat()
                print(f"      Сегодня: {today}")
                
                ws = api.get_worksheet(break_mgr.USAGE_LOG_SHEET)
                all_rows = api._read_table(ws)
                
                today_rows = [
                    r for r in all_rows 
                    if (r.get('StartTime') or r.get('start_time') or '').startswith(today)
                ]
                print(f"      Всего записей за сегодня: {len(today_rows)}")
                
                if today_rows:
                    print("      📋 Записи за сегодня:")
                    for i, row in enumerate(today_rows[:5], 1):  # Показываем первые 5
                        email = row.get('Email') or row.get('email') or 'N/A'
                        break_type = row.get('BreakType') or row.get('break_type') or 'N/A'
                        start_time = row.get('StartTime') or row.get('start_time') or 'N/A'
                        end_time = row.get('EndTime') or row.get('end_time') or None
                        status = row.get('Status') or row.get('status') or 'N/A'
                        
                        has_end_time = end_time is not None and str(end_time).strip() != ''
                        is_active_status = status == 'Active' or status == '' or status is None or not status
                        is_active_check = not has_end_time and is_active_status
                        
                        print(f"         {i}. Email: {email}")
                        print(f"            BreakType: {break_type}")
                        print(f"            StartTime: {start_time}")
                        print(f"            EndTime: {end_time} {'(пусто)' if not has_end_time else '(есть)'}")
                        print(f"            Status: {status}")
                        print(f"            Активен? {is_active_check} (has_end_time={has_end_time}, is_active_status={is_active_status})")
                        print()
                
                # Проверяем все записи БЕЗ EndTime (не только за сегодня)
                print("   6. Проверка всех записей БЕЗ EndTime (все даты)...")
                active_rows_all = [
                    r for r in all_rows 
                    if not (r.get('EndTime') or r.get('end_time')) or str(r.get('EndTime') or r.get('end_time') or '').strip() == ''
                ]
                print(f"      Всего записей БЕЗ EndTime: {len(active_rows_all)}")
                if active_rows_all:
                    print("      📋 Записи БЕЗ EndTime:")
                    for i, row in enumerate(active_rows_all[:5], 1):
                        email = row.get('Email') or row.get('email') or 'N/A'
                        break_type = row.get('BreakType') or row.get('break_type') or 'N/A'
                        start_time = row.get('StartTime') or row.get('start_time') or 'N/A'
                        status = row.get('Status') or row.get('status') or 'N/A'
                        print(f"         {i}. Email: {email}, BreakType: {break_type}, StartTime: {start_time}, Status: {status}")
                print()
        except Exception as e:
            print(f"   ❌ Ошибка при получении активных перерывов: {e}")
            import traceback
            traceback.print_exc()
            print()
        
        # Тест: проверяем метод _get_active_break для конкретного пользователя
        print("6. Тест _get_active_break() для конкретного email...")
        if rows:
            # Берем первый email из записей
            test_email = rows[0].get('Email') or rows[0].get('email') or None
            if test_email:
                print(f"   Тестируем для email: {test_email}")
                try:
                    active_break = break_mgr._get_active_break(test_email, "Перерыв")
                    if active_break:
                        print(f"   ✅ Найден активный перерыв:")
                        print(f"      {active_break}")
                    else:
                        print(f"   ⚠️  Активный перерыв не найден")
                        
                    # Пробуем "Обед"
                    active_lunch = break_mgr._get_active_break(test_email, "Обед")
                    if active_lunch:
                        print(f"   ✅ Найден активный обед:")
                        print(f"      {active_lunch}")
                except Exception as e:
                    print(f"   ❌ Ошибка: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print("   ⚠️  Не удалось найти email в записях")
        print()
        
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
    success = test_active_breaks()
    sys.exit(0 if success else 1)
