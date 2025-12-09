#!/usr/bin/env python3
# coding: utf-8
"""
Диагностический скрипт для системы перерывов v2.0

Проверяет:
- Запись в BreakUsageLog
- Запись в BreakViolations
- Правильность расчёта длительности
- Корректность временных меток
- Работу методов break_manager
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta
import time

# Добавляем корень проекта
ROOT = Path(__file__).parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api_adapter import get_sheets_api
from admin_app.break_manager import BreakManager

print("=" * 80)
print("ДИАГНОСТИКА СИСТЕМЫ ПЕРЕРЫВОВ V2.0")
print("=" * 80)
print()

# Инициализация
print("1. Инициализация...")
try:
    sheets = get_sheets_api()
    break_mgr = BreakManager(sheets)
    print("   ✓ BreakManager инициализирован")
except Exception as e:
    print(f"   ✗ ОШИБКА инициализации: {e}")
    sys.exit(1)

print()

# Параметры теста
TEST_EMAIL = "9@ya.ru"
TEST_SESSION = f"diag_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
TEST_BREAK_TYPE = "Перерыв"

print("=" * 80)
print("ПАРАМЕТРЫ ТЕСТА:")
print("=" * 80)
print(f"Email: {TEST_EMAIL}")
print(f"Session ID: {TEST_SESSION}")
print(f"Break Type: {TEST_BREAK_TYPE}")
print()

# Проверка назначения графика
print("=" * 80)
print("2. Проверка назначенного графика...")
print("=" * 80)
try:
    schedule = break_mgr.get_user_schedule(TEST_EMAIL)
    if schedule:
        print(f"   ✓ График найден: {schedule.name} (ID: {schedule.schedule_id})")
        print(f"   Смена: {schedule.shift_start} - {schedule.shift_end}")
        print(f"   Лимиты:")
        for limit in schedule.limits:
            print(f"     - {limit.break_type}: {limit.daily_count}x{limit.time_minutes} мин")
        print(f"   Окна:")
        for window in schedule.windows:
            print(f"     - {window.break_type}: {window.start_time} - {window.end_time} (приоритет {window.priority})")
    else:
        print(f"   ⚠ График не назначен для {TEST_EMAIL}")
        print("   Тест продолжится, но нарушения могут быть другими")
except Exception as e:
    print(f"   ✗ ОШИБКА: {e}")

print()

# ТЕСТ 1: Начало перерыва
print("=" * 80)
print("3. ТЕСТ: Начало перерыва")
print("=" * 80)
print(f"Вызываем: break_mgr.start_break('{TEST_EMAIL}', '{TEST_BREAK_TYPE}', '{TEST_SESSION}')")
print()

start_time = datetime.now()
print(f"Время начала (Python): {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

try:
    success, error = break_mgr.start_break(TEST_EMAIL, TEST_BREAK_TYPE, TEST_SESSION)
    if success:
        print("✓ start_break() вернул success=True")
    else:
        print(f"✗ start_break() вернул success=False, error={error}")
except Exception as e:
    print(f"✗ ИСКЛЮЧЕНИЕ в start_break(): {e}")
    import traceback
    traceback.print_exc()

print()

# Проверяем запись в BreakUsageLog
print("Проверка записи в BreakUsageLog...")
try:
    ws = sheets.get_worksheet("BreakUsageLog")
    rows = sheets._read_table(ws)
    
    # Ищем нашу запись
    found = False
    for row in rows:
        if (row.get("SessionID") == TEST_SESSION and 
            row.get("Email", "").lower() == TEST_EMAIL.lower()):
            found = True
            print("✓ Запись найдена:")
            print(f"  Email: {row.get('Email')}")
            print(f"  SessionID: {row.get('SessionID')}")
            print(f"  BreakType: {row.get('BreakType')}")
            print(f"  StartTime: {row.get('StartTime')}")
            print(f"  EndTime: {row.get('EndTime', '(пусто)')}")
            print(f"  ExpectedDuration: {row.get('ExpectedDuration')}")
            print(f"  ActualDuration: {row.get('ActualDuration', '(пусто)')}")
            break
    
    if not found:
        print("✗ Запись НЕ найдена в BreakUsageLog")
        print("  Возможные причины:")
        print("    - Ошибка при записи")
        print("    - Неправильное название листа")
        print("    - Задержка синхронизации")

except Exception as e:
    print(f"✗ ОШИБКА чтения BreakUsageLog: {e}")

print()

# Проверяем запись в BreakViolations
print("Проверка записи в BreakViolations...")
try:
    ws = sheets.get_worksheet("BreakViolations")
    rows = sheets._read_table(ws)
    
    # Ищем нарушения для нашей сессии
    violations = [r for r in rows if r.get("SessionID") == TEST_SESSION]
    
    if violations:
        print(f"✓ Найдено нарушений: {len(violations)}")
        for v in violations:
            print(f"  - {v.get('ViolationType')}: {v.get('Details')}")
    else:
        print("✓ Нарушений не найдено (или перерыв в окне)")

except Exception as e:
    print(f"✗ ОШИБКА чтения BreakViolations: {e}")

print()

# Ждём 10 секунд
print("=" * 80)
print("4. ОЖИДАНИЕ 10 СЕКУНД...")
print("=" * 80)
for i in range(10, 0, -1):
    print(f"   {i}...", end="", flush=True)
    time.sleep(1)
print(" Готово!")
print()

# ТЕСТ 2: Завершение перерыва
print("=" * 80)
print("5. ТЕСТ: Завершение перерыва")
print("=" * 80)

end_time = datetime.now()
expected_duration = int((end_time - start_time).total_seconds() / 60)
print(f"Время окончания (Python): {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Ожидаемая длительность: {expected_duration} минут (~10 секунд)")
print()

print(f"Вызываем: break_mgr.end_break('{TEST_EMAIL}', '{TEST_BREAK_TYPE}')")
print()

try:
    success, error, duration = break_mgr.end_break(TEST_EMAIL, TEST_BREAK_TYPE)
    if success:
        print(f"✓ end_break() вернул success=True")
        print(f"  Длительность по расчёту BreakManager: {duration} минут")
        
        if duration != expected_duration:
            print(f"  ⚠ НЕСООТВЕТСТВИЕ!")
            print(f"    Python расчёт: {expected_duration} мин")
            print(f"    BreakManager расчёт: {duration} мин")
            print(f"    Разница: {abs(duration - expected_duration)} мин")
    else:
        print(f"✗ end_break() вернул success=False, error={error}")
except Exception as e:
    print(f"✗ ИСКЛЮЧЕНИЕ в end_break(): {e}")
    import traceback
    traceback.print_exc()

print()

# Проверяем обновлённую запись
print("Проверка обновлённой записи в BreakUsageLog...")
try:
    ws = sheets.get_worksheet("BreakUsageLog")
    rows = sheets._read_table(ws)
    
    for row in rows:
        if (row.get("SessionID") == TEST_SESSION and 
            row.get("Email", "").lower() == TEST_EMAIL.lower()):
            print("✓ Запись найдена:")
            print(f"  StartTime: {row.get('StartTime')}")
            print(f"  EndTime: {row.get('EndTime')}")
            print(f"  ExpectedDuration: {row.get('ExpectedDuration')}")
            print(f"  ActualDuration: {row.get('ActualDuration')}")
            
            # Проверяем корректность
            start_str = row.get('StartTime')
            end_str = row.get('EndTime')
            actual_dur = row.get('ActualDuration')
            
            if start_str and end_str:
                try:
                    # Парсим время
                    start_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
                    end_dt = datetime.strptime(end_str, "%Y-%m-%d %H:%M:%S")
                    
                    # Считаем разницу
                    delta = end_dt - start_dt
                    delta_minutes = int(delta.total_seconds() / 60)
                    delta_seconds = int(delta.total_seconds())
                    
                    print()
                    print("АНАЛИЗ ДЛИТЕЛЬНОСТИ:")
                    print(f"  Start: {start_dt}")
                    print(f"  End:   {end_dt}")
                    print(f"  Разница (сек): {delta_seconds}")
                    print(f"  Разница (мин): {delta_minutes}")
                    print(f"  ActualDuration в таблице: {actual_dur}")
                    
                    if actual_dur and int(actual_dur) != delta_minutes:
                        print()
                        print("  ⚠ ОШИБКА РАСЧЁТА!")
                        print(f"    Правильно должно быть: {delta_minutes} минут")
                        print(f"    Записано в таблице: {actual_dur} минут")
                        print(f"    Ошибка на: {abs(int(actual_dur) - delta_minutes)} минут")
                        print()
                        print("  ПРИЧИНА: Метод end_break() неправильно считает длительность")
                        print("  РЕШЕНИЕ: Проверить расчёт в break_manager.py, метод end_break()")
                    else:
                        print()
                        print("  ✓ Длительность рассчитана корректно!")
                    
                except Exception as e:
                    print(f"  ✗ Ошибка парсинга времени: {e}")
            
            break

except Exception as e:
    print(f"✗ ОШИБКА чтения BreakUsageLog: {e}")

print()

# Итоговая статистика
print("=" * 80)
print("6. ИТОГОВАЯ СТАТИСТИКА")
print("=" * 80)
try:
    stats = break_mgr.get_usage_stats(TEST_EMAIL, datetime.now().date().isoformat())
    print(f"Использовано сегодня:")
    print(f"  Перерывов: {stats['breaks_used']} ({stats['total_break_minutes']} мин)")
    print(f"  Обедов: {stats['lunches_used']} ({stats['total_lunch_minutes']} мин)")
except Exception as e:
    print(f"✗ ОШИБКА получения статистики: {e}")

print()

# Проверка статуса перерыва
print("=" * 80)
print("7. ПРОВЕРКА СТАТУСА ПЕРЕРЫВА")
print("=" * 80)
try:
    status = break_mgr.get_break_status(TEST_EMAIL)
    if status:
        print("Текущий статус:")
        if status.get("active_break"):
            active = status["active_break"]
            print(f"  ⚠ АКТИВНЫЙ ПЕРЕРЫВ:")
            print(f"    Тип: {active.get('break_type')}")
            print(f"    Начало: {active.get('start_time')}")
            print(f"    Длительность: {active.get('duration')} мин")
            print(f"    Лимит: {active.get('limit')} мин")
        else:
            print("  ✓ Нет активных перерывов")
        
        if status.get("schedule"):
            print(f"  График: {status['schedule']['name']}")
        
        if status.get("used_today"):
            print(f"  Использовано сегодня:")
            for break_type, count in status["used_today"].items():
                limit = status.get("limits", {}).get(break_type, {}).get("count", 0)
                print(f"    {break_type}: {count}/{limit}")
    else:
        print("  ⚠ Не удалось получить статус")
except Exception as e:
    print(f"  ✗ ОШИБКА: {e}")

print()
print("=" * 80)
print("ДИАГНОСТИКА ЗАВЕРШЕНА")
print("=" * 80)
print()
print(f"Тестовая запись SessionID: {TEST_SESSION}")
print("Можете найти её в BreakUsageLog и проверить вручную")
print()