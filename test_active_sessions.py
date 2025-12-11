#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работы активных сессий в Supabase
Проверяет:
1. Подключение к Supabase
2. Получение активных сессий
3. Формат данных
4. Сохранение сессии
5. Совместимость с админкой
"""
import sys
from pathlib import Path

# Добавляем корень проекта в путь
ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import os
from datetime import datetime, timezone
from dotenv import load_dotenv

# Загружаем .env
env_path = Path.cwd() / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"✅ Загружен .env файл: {env_path}")
else:
    print(f"⚠️  .env файл не найден: {env_path}")
    load_dotenv()

print("=" * 80)
print("ТЕСТ АКТИВНЫХ СЕССИЙ В SUPABASE")
print("=" * 80)
print()

# Проверка переменных окружения
print("1. ПРОВЕРКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ")
print("-" * 80)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
USE_BACKEND = os.getenv("USE_BACKEND", "supabase")

print(f"USE_BACKEND: {USE_BACKEND}")
print(f"SUPABASE_URL: {SUPABASE_URL}")
print(f"SUPABASE_KEY: {'SET (' + str(len(SUPABASE_KEY)) + ' символов)' if SUPABASE_KEY else 'NOT SET'}")
print()

# Импорт API
print("2. ИМПОРТ API")
print("-" * 80)
try:
    from api_adapter import get_sheets_api, USE_BACKEND as ADAPTER_BACKEND
    api = get_sheets_api()
    print(f"✅ API импортирован успешно")
    print(f"   Тип API: {type(api).__name__}")
    print(f"   Backend в адаптере: {ADAPTER_BACKEND}")
    print()
except Exception as e:
    print(f"❌ Ошибка импорта API: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Проверка методов
print("3. ПРОВЕРКА МЕТОДОВ")
print("-" * 80)
required_methods = [
    'get_active_sessions',
    'get_all_active_sessions',
    'get_active_session',
    'set_active_session',
    'check_user_session_status',
    'kick_active_session',
    'finish_active_session'
]

for method_name in required_methods:
    if hasattr(api, method_name):
        print(f"✅ {method_name} - есть")
    else:
        print(f"❌ {method_name} - ОТСУТСТВУЕТ!")
print()

# Тест получения активных сессий
print("4. ТЕСТ ПОЛУЧЕНИЯ АКТИВНЫХ СЕССИЙ")
print("-" * 80)
try:
    sessions = api.get_all_active_sessions()
    print(f"✅ Получено сессий: {len(sessions)}")
    
    if sessions:
        print("\nПервая сессия (формат данных):")
        first_session = sessions[0]
        for key, value in first_session.items():
            print(f"  {key}: {value}")
        
        print("\nПроверка ключей (должны быть в верхнем регистре для админки):")
        required_keys = ['Email', 'Status', 'SessionID', 'LoginTime']
        for key in required_keys:
            if key in first_session:
                print(f"  ✅ {key}: {first_session[key]}")
            else:
                print(f"  ❌ {key}: ОТСУТСТВУЕТ!")
    else:
        print("⚠️  Активных сессий нет")
    print()
except Exception as e:
    print(f"❌ Ошибка получения сессий: {e}")
    import traceback
    traceback.print_exc()
    print()

# Тест получения конкретной сессии
print("5. ТЕСТ ПОЛУЧЕНИЯ КОНКРЕТНОЙ СЕССИИ")
print("-" * 80)
test_email = "test@example.com"  # Замените на реальный email
try:
    session = api.get_active_session(test_email)
    if session:
        print(f"✅ Сессия для {test_email} найдена:")
        for key, value in session.items():
            print(f"  {key}: {value}")
    else:
        print(f"⚠️  Сессия для {test_email} не найдена")
    print()
except Exception as e:
    print(f"❌ Ошибка получения сессии: {e}")
    import traceback
    traceback.print_exc()
    print()

# Тест создания тестовой сессии
print("6. ТЕСТ СОЗДАНИЯ ТЕСТОВОЙ СЕССИИ")
print("-" * 80)
test_email = "test_session@example.com"
test_name = "Test User"
test_session_id = f"test_{datetime.now().isoformat()}"

try:
    result = api.set_active_session(
        email=test_email,
        name=test_name,
        session_id=test_session_id,
        login_time=datetime.now(timezone.utc).isoformat()
    )
    if result:
        print(f"✅ Тестовая сессия создана успешно")
        print(f"   Email: {test_email}")
        print(f"   SessionID: {test_session_id}")
        
        # Проверяем, что сессия появилась
        session = api.get_active_session(test_email)
        if session:
            print(f"✅ Сессия найдена после создания:")
            print(f"   Email: {session.get('Email')}")
            print(f"   Status: {session.get('Status')}")
            print(f"   SessionID: {session.get('SessionID')}")
        else:
            print(f"❌ Сессия не найдена после создания!")
    else:
        print(f"❌ Не удалось создать тестовую сессию")
    print()
except Exception as e:
    print(f"❌ Ошибка создания сессии: {e}")
    import traceback
    traceback.print_exc()
    print()

# Тест проверки статуса сессии
print("7. ТЕСТ ПРОВЕРКИ СТАТУСА СЕССИИ")
print("-" * 80)
if test_session_id:
    try:
        status = api.check_user_session_status(test_email, test_session_id)
        print(f"✅ Статус сессии: {status}")
        print()
    except Exception as e:
        print(f"❌ Ошибка проверки статуса: {e}")
        import traceback
        traceback.print_exc()
        print()

# Тест получения всех сессий после создания
print("8. ПРОВЕРКА ФОРМАТА ДАННЫХ ДЛЯ АДМИНКИ")
print("-" * 80)
try:
    all_sessions = api.get_all_active_sessions()
    print(f"Всего активных сессий: {len(all_sessions)}")
    
    if all_sessions:
        print("\nФормат данных (первая сессия):")
        first = all_sessions[0]
        print(f"  Тип: {type(first)}")
        print(f"  Ключи: {list(first.keys())}")
        
        # Проверка формата для админки
        print("\nПроверка совместимости с админкой:")
        admin_required = {
            'Email': 'email пользователя',
            'Status': 'статус сессии (active/finished/kicked)',
            'SessionID': 'ID сессии',
            'LoginTime': 'время входа'
        }
        
        for key, desc in admin_required.items():
            if key in first:
                value = first[key]
                print(f"  ✅ {key}: {value} ({desc})")
            else:
                print(f"  ❌ {key}: ОТСУТСТВУЕТ ({desc})")
        
        # Проверка фильтрации по статусу
        active_sessions = [s for s in all_sessions if str(s.get('Status', '')).strip().lower() == 'active']
        print(f"\n  Активных сессий (Status='active'): {len(active_sessions)}")
        
        if active_sessions:
            print("\n  Email активных пользователей:")
            for s in active_sessions:
                email = s.get('Email', '')
                status = s.get('Status', '')
                print(f"    - {email} (Status: {status})")
    else:
        print("⚠️  Нет активных сессий")
    print()
except Exception as e:
    print(f"❌ Ошибка проверки формата: {e}")
    import traceback
    traceback.print_exc()
    print()

# Тест прямого запроса к Supabase
print("9. ПРЯМОЙ ЗАПРОС К SUPABASE")
print("-" * 80)
try:
    if hasattr(api, 'client'):
        response = api.client.table('active_sessions').select('*').eq('status', 'active').execute()
        print(f"✅ Прямой запрос к Supabase: {len(response.data)} активных сессий")
        
        if response.data:
            print("\n  Формат данных из Supabase (первая запись):")
            first_raw = response.data[0]
            print(f"    Ключи: {list(first_raw.keys())}")
            print(f"    Email: {first_raw.get('email')}")
            print(f"    Status: {first_raw.get('status')}")
    else:
        print("⚠️  API не имеет атрибута 'client' (возможно, это не Supabase API)")
    print()
except Exception as e:
    print(f"❌ Ошибка прямого запроса: {e}")
    import traceback
    traceback.print_exc()
    print()

# Итоговая проверка
print("=" * 80)
print("ИТОГОВАЯ ПРОВЕРКА")
print("=" * 80)

try:
    all_sessions = api.get_all_active_sessions()
    active_count = len([s for s in all_sessions if str(s.get('Status', '')).strip().lower() == 'active'])
    
    print(f"Всего сессий: {len(all_sessions)}")
    print(f"Активных сессий: {active_count}")
    
    if active_count > 0:
        print("\n✅ Активные сессии найдены!")
        print("Админка должна видеть этих пользователей:")
        for s in all_sessions:
            if str(s.get('Status', '')).strip().lower() == 'active':
                email = s.get('Email', '')
                print(f"  - {email}")
    else:
        print("\n⚠️  Активных сессий не найдено")
        print("Возможные причины:")
        print("  1. Пользователь не залогинен")
        print("  2. Сессия не сохраняется при логине")
        print("  3. Статус сессии не 'active'")
        print("  4. Проблема с преобразованием данных")
    
except Exception as e:
    print(f"❌ Ошибка итоговой проверки: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 80)
print("ТЕСТ ЗАВЕРШЕН")
print("=" * 80)
