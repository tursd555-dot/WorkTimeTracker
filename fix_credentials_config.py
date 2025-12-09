#!/usr/bin/env python3
"""
Автоматическое исправление конфигурации credentials
Находит service_account.json и обновляет .env
"""

import os
import sys
from pathlib import Path

def find_service_account():
    """Поиск service_account.json в проекте"""
    possible_locations = [
        'credentials/service_account.json',
        'service_account.json',
        'credentials/secret_creds/service_account.json',
        '../service_account.json'
    ]
    
    for loc in possible_locations:
        path = Path(loc)
        if path.exists():
            return path.absolute()
    
    return None

def update_env_file(service_account_path):
    """Обновляет .env файл с правильным путем"""
    env_path = Path('.env')
    env_example_path = Path('.env.example')
    
    # Читаем существующий .env или создаем из .env.example
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    elif env_example_path.exists():
        with open(env_example_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    else:
        lines = []
    
    # Обновляем или добавляем GOOGLE_CREDENTIALS_FILE
    found = False
    new_lines = []
    
    for line in lines:
        if line.strip().startswith('GOOGLE_CREDENTIALS_FILE='):
            # Заменяем существующую строку
            new_lines.append(f'GOOGLE_CREDENTIALS_FILE={service_account_path}\n')
            found = True
        elif line.strip().startswith('#GOOGLE_CREDENTIALS_FILE=') or line.strip().startswith('# GOOGLE_CREDENTIALS_FILE='):
            # Раскомментируем и обновляем
            new_lines.append(f'GOOGLE_CREDENTIALS_FILE={service_account_path}\n')
            found = True
        else:
            new_lines.append(line)
    
    # Если не нашли, добавляем в конец
    if not found:
        new_lines.append(f'\n# Автоматически добавлено fix_credentials_config.py\n')
        new_lines.append(f'GOOGLE_CREDENTIALS_FILE={service_account_path}\n')
    
    # Записываем обновленный .env
    with open(env_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    return env_path

def validate_env():
    """Проверяет минимальные требования в .env"""
    env_path = Path('.env')
    if not env_path.exists():
        return False, [".env файл не найден"]
    
    required_vars = ['GOOGLE_CREDENTIALS_FILE', 'SPREADSHEET_ID']
    missing = []
    
    with open(env_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    for var in required_vars:
        if f'{var}=' not in content or f'{var}=your_' in content or f'{var}=""' in content:
            missing.append(var)
    
    if missing:
        return False, missing
    
    return True, []

def main():
    print("="*70)
    print("WorkTimeTracker - Автоматическое исправление конфигурации")
    print("="*70)
    print()
    
    # Шаг 1: Поиск service_account.json
    print("🔍 Шаг 1: Поиск service_account.json...")
    service_account = find_service_account()
    
    if not service_account:
        print("❌ service_account.json не найден!")
        print()
        print("Пожалуйста, поместите файл service_account.json в одну из папок:")
        print("  - credentials/")
        print("  - корень проекта")
        print()
        print("Затем запустите этот скрипт снова.")
        return 1
    
    print(f"✅ Найден: {service_account}")
    print()
    
    # Шаг 2: Обновление .env
    print("📝 Шаг 2: Обновление .env файла...")
    
    try:
        env_file = update_env_file(service_account)
        print(f"✅ Обновлен: {env_file}")
        print(f"   GOOGLE_CREDENTIALS_FILE={service_account}")
    except Exception as e:
        print(f"❌ Ошибка при обновлении .env: {e}")
        return 1
    
    print()
    
    # Шаг 3: Валидация
    print("✔️  Шаг 3: Проверка конфигурации...")
    is_valid, missing = validate_env()
    
    if is_valid:
        print("✅ Конфигурация корректна!")
        print()
        print("Вы можете запустить приложение:")
        print("  python user_app/main.py")
        print()
        return 0
    else:
        print("⚠️  Конфигурация неполная. Не хватает:")
        for var in missing:
            print(f"   - {var}")
        print()
        print("Пожалуйста, отредактируйте .env файл и заполните эти значения.")
        print()
        
        # Показываем пример
        if 'SPREADSHEET_ID' in missing:
            print("Пример SPREADSHEET_ID:")
            print("  SPREADSHEET_ID=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms")
            print("  (найдите в URL вашей Google таблицы)")
            print()
        
        return 1

if __name__ == '__main__':
    try:
        # Проверяем, что мы в корне проекта
        if not Path('user_app').exists():
            print("❌ Запустите скрипт из корня проекта WorkTimeTracker")
            sys.exit(1)
        
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n❌ Прервано пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Неожиданная ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
