#!/usr/bin/env python3
"""
Тестовый скрипт для диагностики нарушений
"""
import sys
import os
from datetime import datetime, date

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api_adapter import get_sheets_api
from admin_app.break_manager import BreakManager

def test_violations():
    """Тестирует запись и чтение нарушений"""
    print("=" * 70)
    print("ТЕСТ: Нарушения перерывов")
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
        
        # Проверка таблицы break_violations
        print("3. Проверка таблицы break_violations...")
        try:
            ws = api.get_worksheet("BreakViolations")
            print(f"   ✅ Worksheet получен: {ws.table_name if hasattr(ws, 'table_name') else 'N/A'}")
            
            # Читаем все записи
            rows = api._read_table(ws)
            print(f"   ✅ Всего записей в таблице: {len(rows)}")
            
            if rows:
                print(f"   📋 Первая запись (ключи): {list(rows[0].keys())}")
                print(f"   📋 Первая запись (данные): {rows[0]}")
                print()
            else:
                print(f"   ⚠️  Таблица пуста")
                print()
        except Exception as e:
            print(f"   ❌ Ошибка при чтении таблицы: {e}")
            import traceback
            traceback.print_exc()
            print()
        
        # Проверка нарушений за сегодня
        print("4. Проверка нарушений за сегодня...")
        today = date.today().isoformat()
        print(f"   Сегодня: {today}")
        
        try:
            violations = break_mgr.get_violations_report(
                date_from=today,
                date_to=today
            )
            print(f"   ✅ Найдено нарушений за сегодня: {len(violations)}")
            
            if violations:
                print(f"   📋 Нарушения:")
                for idx, v in enumerate(violations[:5], 1):  # Показываем первые 5
                    ts = v.get('Timestamp', '')
                    date_part = ts[:10] if ts else 'N/A'
                    print(f"      {idx}. Email: {v.get('Email')}, "
                          f"Тип: {v.get('ViolationType')}, "
                          f"Время: {ts}, "
                          f"Дата: {date_part}, "
                          f"Детали: {v.get('Details', '')[:50]}")
            else:
                print(f"   ⚠️  Нарушений не найдено")
                # Показываем все нарушения для диагностики
                all_v = break_mgr.get_violations_report()
                print(f"   📋 Диагностика: Всего нарушений: {len(all_v)}")
                for v in all_v[:3]:
                    ts = v.get('Timestamp', '')
                    date_part = ts[:10] if ts else 'N/A'
                    print(f"      - Дата: {date_part}, Email: {v.get('Email')}, Тип: {v.get('ViolationType')}")
            print()
        except Exception as e:
            print(f"   ❌ Ошибка при получении нарушений: {e}")
            import traceback
            traceback.print_exc()
            print()
        
        # Проверка нарушений для конкретного пользователя
        print("5. Проверка нарушений для 9@ya.ru...")
        try:
            violations_user = break_mgr.get_violations_report(
                email="9@ya.ru",
                date_from=today,
                date_to=today
            )
            print(f"   ✅ Найдено нарушений для 9@ya.ru за сегодня: {len(violations_user)}")
            
            if violations_user:
                print(f"   📋 Нарушения:")
                for idx, v in enumerate(violations_user, 1):
                    print(f"      {idx}. Тип: {v.get('ViolationType')}, "
                          f"Время: {v.get('Timestamp')}, "
                          f"Детали: {v.get('Details', '')[:50]}")
            else:
                print(f"   ⚠️  Нарушений не найдено")
            print()
        except Exception as e:
            print(f"   ❌ Ошибка при получении нарушений пользователя: {e}")
            import traceback
            traceback.print_exc()
            print()
        
        # Проверка всех нарушений (без фильтра по дате)
        print("6. Проверка всех нарушений (без фильтра по дате)...")
        try:
            all_violations = break_mgr.get_violations_report()
            print(f"   ✅ Всего нарушений в таблице: {len(all_violations)}")
            
            if all_violations:
                print(f"   📋 Последние 5 нарушений:")
                for idx, v in enumerate(all_violations[-5:], 1):
                    print(f"      {idx}. Email: {v.get('Email')}, "
                          f"Тип: {v.get('ViolationType')}, "
                          f"Время: {v.get('Timestamp')}")
            print()
        except Exception as e:
            print(f"   ❌ Ошибка при получении всех нарушений: {e}")
            import traceback
            traceback.print_exc()
            print()
        
        # Тест записи нарушения
        print("7. Тест записи нарушения...")
        try:
            test_email = "test@example.com"
            test_violation_type = "OUT_OF_WINDOW"
            test_details = "Тестовое нарушение из скрипта"
            
            print(f"   Создаём нарушение: email={test_email}, type={test_violation_type}")
            
            break_mgr._log_violation(
                email=test_email,
                session_id="test_session_123",
                violation_type=test_violation_type,
                severity="WARNING",
                details=test_details
            )
            
            print(f"   ✅ Нарушение записано")
            
            # Проверяем, что оно появилось
            import time
            time.sleep(1)  # Даём время на запись
            
            test_violations = break_mgr.get_violations_report(email=test_email)
            if test_violations:
                print(f"   ✅ Нарушение найдено в таблице: {len(test_violations)} записей")
                for v in test_violations:
                    if v.get('Details') == test_details:
                        print(f"      ✅ Тестовое нарушение найдено: {v.get('Timestamp')}")
            else:
                print(f"   ⚠️  Тестовое нарушение не найдено в таблице")
            print()
        except Exception as e:
            print(f"   ❌ Ошибка при записи нарушения: {e}")
            import traceback
            traceback.print_exc()
            print()
        
        print("=" * 70)
        print("ТЕСТ ЗАВЕРШЕН")
        print("=" * 70)
        
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = test_violations()
    sys.exit(0 if success else 1)
