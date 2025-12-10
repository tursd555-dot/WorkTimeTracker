"""
Тест для отладки отображения перерывов в админке
"""
import os
from datetime import date

# Загружаем переменные окружения из .env файла
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from api_adapter import get_sheets_api

# Проверяем переменные окружения
if not os.getenv('SUPABASE_KEY'):
    print("⚠️ SUPABASE_KEY не установлен!")
    print("Установите переменные окружения или создайте .env файл")
    exit(1)

print("=" * 60)
print("ТЕСТ: Проверка данных о перерывах в Supabase")
print("=" * 60)

try:
    # Получаем API
    api = get_sheets_api()
    print(f"✅ API подключен: {type(api).__name__}")

    # 1. Проверяем таблицу break_log
    print("\n📊 Проверка таблицы break_log...")
    ws = api.get_worksheet('BreakUsageLog')
    rows = api._read_table(ws)
    print(f"   Всего записей в break_log: {len(rows)}")

    if rows:
        print(f"\n   Первая запись (пример):")
        first = rows[0]
        for key, value in first.items():
            print(f"      {key}: {value}")

    # 2. Проверяем активные перерывы (без EndTime)
    print(f"\n🔍 Поиск активных перерывов за сегодня ({date.today().isoformat()})...")
    today = date.today().isoformat()

    active_breaks = []
    for row in rows:
        start_time = row.get('StartTime', '')
        end_time = row.get('EndTime', '')

        if not end_time and start_time.startswith(today):
            active_breaks.append({
                'Email': row.get('Email'),
                'Name': row.get('Name'),
                'BreakType': row.get('BreakType'),
                'StartTime': start_time,
            })

    print(f"   Найдено активных перерывов: {len(active_breaks)}")

    if active_breaks:
        print("\n   Активные перерывы:")
        for i, brk in enumerate(active_breaks, 1):
            print(f"   {i}. {brk['Name']} ({brk['Email']})")
            print(f"      Тип: {brk['BreakType']}")
            print(f"      Начало: {brk['StartTime']}")
    else:
        print("   ❌ Активные перерывы не найдены!")
        print("\n   Возможные причины:")
        print("   - Пользователь не брал перерыв сегодня")
        print("   - Данные не записываются в break_log")
        print("   - Перерыв уже завершён (есть EndTime)")

    # 3. Проверяем view active_breaks (если есть)
    print(f"\n🔍 Проверка view active_breaks...")
    try:
        active_view = api.get_active_breaks()
        print(f"   Записей в active_breaks view: {len(active_view)}")
        if active_view:
            print("\n   Данные из view:")
            for item in active_view:
                print(f"      {item}")
    except Exception as e:
        print(f"   ⚠️ View active_breaks недоступен: {e}")
        print("   Это нормально, view может не существовать в Supabase")

    # 4. Показываем последние записи
    print(f"\n📝 Последние 5 записей в break_log:")
    for i, row in enumerate(rows[-5:] if len(rows) >= 5 else rows, 1):
        print(f"\n   {i}. {row.get('Name')} ({row.get('Email')})")
        print(f"      Тип: {row.get('BreakType')}")
        print(f"      Начало: {row.get('StartTime')}")
        print(f"      Конец: {row.get('EndTime') or 'Не завершён'}")

    print("\n" + "=" * 60)
    print("✅ Тест завершён")
    print("=" * 60)

except Exception as e:
    print(f"\n❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
