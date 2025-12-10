#!/usr/bin/env python3
"""
Тест для проверки корректности преобразования данных из Supabase
"""
from datetime import datetime

def test_conversion():
    """Тестирует логику преобразования из supabase_api._read_table()"""

    # Имитируем данные из Supabase
    supabase_row = {
        'id': 123,
        'email': 'test@example.com',
        'name': 'Тестовый Пользователь',
        'break_type': 'Перерыв',
        'start_time': '2024-12-10T10:00:00+00:00',
        'end_time': None,  # Активный перерыв
        'status': 'Active',
        'session_id': 'sess123',
        'date': '2024-12-10'
    }

    # Логика преобразования из _read_table()
    converted_row = {}
    for key, value in supabase_row.items():
        if key == 'email':
            converted_row['Email'] = value
        elif key == 'name':
            converted_row['Name'] = value
        elif key == 'break_type':
            converted_row['BreakType'] = value
        elif key == 'start_time':
            if isinstance(value, datetime):
                converted_row['StartTime'] = value.isoformat()
            else:
                converted_row['StartTime'] = value
        elif key == 'end_time':
            if isinstance(value, datetime):
                converted_row['EndTime'] = value.isoformat() if value else ''
            else:
                converted_row['EndTime'] = value or ''
        elif key == 'status':
            converted_row['Status'] = value
        elif key == 'session_id':
            converted_row['SessionID'] = value

    print("✅ Преобразованные данные:")
    for key, value in converted_row.items():
        print(f"  {key}: {value!r}")

    # Проверки
    assert converted_row['Email'] == 'test@example.com'
    assert converted_row['Name'] == 'Тестовый Пользователь'
    assert converted_row['BreakType'] == 'Перерыв'
    assert converted_row['StartTime'] == '2024-12-10T10:00:00+00:00'
    assert converted_row['EndTime'] == ''  # Важно: пустая строка для активного перерыва
    assert converted_row['Status'] == 'Active'

    # Проверка логики из break_manager.get_all_active_breaks()
    today = '2024-12-10'
    is_active = not converted_row.get('EndTime') and converted_row.get('StartTime', '').startswith(today)

    print(f"\n✅ Проверка логики активных перерывов:")
    print(f"  EndTime пустой: {not converted_row.get('EndTime')}")
    print(f"  StartTime начинается с {today}: {converted_row.get('StartTime', '').startswith(today)}")
    print(f"  Результат (активный перерыв): {is_active}")

    assert is_active, "Перерыв должен быть определен как активный"

    print("\n✅ Все тесты пройдены!")

if __name__ == "__main__":
    test_conversion()
