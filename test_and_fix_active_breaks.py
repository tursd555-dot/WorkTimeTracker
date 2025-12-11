#!/usr/bin/env python3
"""
Тестовый скрипт для диагностики и исправления зависших активных перерывов
"""
import sys
import os
from datetime import datetime, date, timezone

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api_adapter import get_sheets_api
from admin_app.break_manager import BreakManager

def test_and_fix_active_breaks():
    """Тестирует и исправляет зависшие активные перерывы"""
    print("=" * 60)
    print("ТЕСТ: Диагностика и исправление активных перерывов")
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
            print()
        except Exception as e:
            print(f"   ❌ Ошибка при чтении таблицы: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # Получаем активные перерывы
        print("4. Получение активных перерывов через get_all_active_breaks()...")
        try:
            active_breaks = break_mgr.get_all_active_breaks()
            print(f"   ✅ Найдено активных перерывов: {len(active_breaks)}")
            print()
            
            if active_breaks:
                print("   📋 Список активных перерывов:")
                for i, br in enumerate(active_breaks, 1):
                    email = br.get('Email', 'N/A')
                    name = br.get('Name', 'N/A')
                    break_type = br.get('BreakType', 'N/A')
                    start_time = br.get('StartTime', 'N/A')
                    duration = br.get('Duration', 'N/A')
                    is_violator = br.get('is_violator', False)
                    violation_reason = br.get('violation_reason', '')
                    
                    print(f"      {i}. Email: {email}")
                    print(f"         Name: {name}")
                    print(f"         BreakType: {break_type}")
                    print(f"         StartTime: {start_time}")
                    print(f"         Duration: {duration} мин")
                    print(f"         Нарушитель: {'Да' if is_violator else 'Нет'}")
                    if violation_reason:
                        print(f"         Причина: {violation_reason}")
                    print()
                
                # Проверяем, нужно ли завершить старые перерывы
                print("5. Проверка на зависшие перерывы...")
                today = date.today().isoformat()
                old_breaks = []
                
                for br in active_breaks:
                    start_time_str = br.get('StartTime', '')
                    if start_time_str and not start_time_str.startswith(today):
                        old_breaks.append(br)
                
                if old_breaks:
                    print(f"   ⚠️  Найдено {len(old_breaks)} зависших перерывов (не за сегодня):")
                    for br in old_breaks:
                        print(f"      - {br.get('Email')}: {br.get('StartTime')}")
                    print()
                    
                    # Предлагаем завершить
                    print("6. Завершение зависших перерывов...")
                    for br in old_breaks:
                        email = br.get('Email', '')
                        break_type = br.get('BreakType', '')
                        try:
                            print(f"   Завершаем перерыв для {email} ({break_type})...")
                            success, error, duration = break_mgr.end_break(email, break_type)
                            if success:
                                print(f"   ✅ Перерыв завершен, длительность: {duration} мин")
                            else:
                                print(f"   ❌ Ошибка: {error}")
                        except Exception as e:
                            print(f"   ❌ Исключение: {e}")
                    print()
                else:
                    print("   ✅ Все активные перерывы за сегодня")
                    print()
                
                # Проверяем перерывы за сегодня, которые могут быть зависшими
                print("7. Проверка перерывов за сегодня...")
                today_breaks = [br for br in active_breaks if br.get('StartTime', '').startswith(today)]
                print(f"   Найдено перерывов за сегодня: {len(today_breaks)}")
                
                if today_breaks:
                    print("   📋 Детали перерывов за сегодня:")
                    for br in today_breaks:
                        email = br.get('Email', '')
                        start_time = br.get('StartTime', '')
                        duration = br.get('Duration', 0)
                        
                        # Проверяем, не слишком ли долго длится перерыв
                        if duration > 120:  # Больше 2 часов - подозрительно
                            print(f"      ⚠️  {email}: длительность {duration} мин (подозрительно долго)")
                            print(f"         StartTime: {start_time}")
                            
                            # Проверяем активный перерыв в БД
                            try:
                                active = break_mgr._get_active_break(email, br.get('BreakType', ''))
                                if active:
                                    print(f"         ✅ Активный перерыв найден в БД")
                                    print(f"         EndTime в БД: {active.get('EndTime') or 'None'}")
                                    print(f"         Status в БД: {active.get('Status') or 'None'}")
                                else:
                                    print(f"         ⚠️  Активный перерыв НЕ найден в БД (возможно уже завершен)")
                            except Exception as e:
                                print(f"         ❌ Ошибка проверки: {e}")
                        else:
                            print(f"      ✅ {email}: длительность {duration} мин (нормально)")
                    print()
            else:
                print("   ✅ Активных перерывов не найдено")
                print()
        
        except Exception as e:
            print(f"   ❌ Ошибка при получении активных перерывов: {e}")
            import traceback
            traceback.print_exc()
            print()
        
        # Дополнительная проверка: все записи без EndTime
        print("8. Проверка всех записей БЕЗ EndTime в базе...")
        try:
            ws = api.get_worksheet(break_mgr.USAGE_LOG_SHEET)
            all_rows = api._read_table(ws)
            
            no_end_time = []
            for row in all_rows:
                end_time = row.get('EndTime') or row.get('end_time') or None
                status = row.get('Status') or row.get('status') or ''
                has_end_time = end_time is not None and str(end_time).strip() != ''
                is_active_status = status == 'Active' or status == '' or status is None or not status
                
                if not has_end_time and is_active_status:
                    no_end_time.append(row)
            
            print(f"   Всего записей БЕЗ EndTime: {len(no_end_time)}")
            
            if no_end_time:
                print("   📋 Записи БЕЗ EndTime:")
                for i, row in enumerate(no_end_time[:10], 1):  # Показываем первые 10
                    email = row.get('Email') or row.get('email') or 'N/A'
                    break_type = row.get('BreakType') or row.get('break_type') or 'N/A'
                    start_time = row.get('StartTime') or row.get('start_time') or 'N/A'
                    status = row.get('Status') or row.get('status') or 'N/A'
                    
                    print(f"      {i}. Email: {email}")
                    print(f"         BreakType: {break_type}")
                    print(f"         StartTime: {start_time}")
                    print(f"         Status: {status}")
                    print()
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
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
    success = test_and_fix_active_breaks()
    sys.exit(0 if success else 1)
