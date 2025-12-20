#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для загрузки credentials в Supabase

Использование:
    python tools/upload_credentials_to_supabase.py service_account.json
    
Или интерактивно:
    python tools/upload_credentials_to_supabase.py
"""

import sys
import os
import json
from pathlib import Path

# Добавляем корень проекта в путь
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Загружаем переменные окружения из .env ПЕРЕД импортом модулей
try:
    from dotenv import load_dotenv
    # Ищем .env файл
    env_candidates = [
        PROJECT_ROOT / ".env",
        Path.cwd() / ".env",
    ]
    for env_path in env_candidates:
        if env_path.exists():
            load_dotenv(env_path, override=False)
            break
    else:
        load_dotenv()
except ImportError:
    pass

# Устанавливаем переменные Supabase из config.py если они не заданы
try:
    # Импортируем config - он установит переменные через os.environ.setdefault
    import config
    
    # Убеждаемся что переменные установлены
    if not os.getenv("SUPABASE_URL"):
        os.environ["SUPABASE_URL"] = "https://jtgaobxbwibjcvasefzi.supabase.co"
    
    # SUPABASE_KEY должен быть установлен в config.py или .env
    # Если нет - будет проверка в main()
except Exception as e:
    print(f"⚠️  Предупреждение при загрузке config: {e}")

from shared.credentials_storage import save_credentials_json_to_supabase


def validate_credentials_json(file_path: Path) -> bool:
    """Проверка валидности credentials JSON"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Проверяем обязательные поля
        required_fields = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email']
        missing = [field for field in required_fields if field not in data]
        
        if missing:
            print(f"❌ Отсутствуют обязательные поля: {', '.join(missing)}")
            return False
        
        if data.get('type') != 'service_account':
            print("❌ Тип credentials должен быть 'service_account'")
            return False
        
        print("✓ Credentials файл валиден")
        return True
    except json.JSONDecodeError as e:
        print(f"❌ Ошибка парсинга JSON: {e}")
        return False
    except Exception as e:
        print(f"❌ Ошибка чтения файла: {e}")
        return False


def main():
    """Главная функция"""
    print("=" * 60)
    print("Загрузка credentials в Supabase")
    print("=" * 60)
    
    # Проверяем переменные Supabase ПЕРЕД загрузкой файла
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url:
        print("\n❌ SUPABASE_URL не настроен!")
        print("   Установите через PowerShell:")
        print("   $env:SUPABASE_URL='https://jtgaobxbwibjcvasefzi.supabase.co'")
        print("   Или добавьте в .env: SUPABASE_URL=https://jtgaobxbwibjcvasefzi.supabase.co")
        return 1
    
    if not supabase_key:
        print("\n❌ SUPABASE_KEY не настроен!")
        print("\nВарианты решения:")
        print("1. Создайте файл .env в корне проекта со строкой:")
        print("   SUPABASE_KEY=ваш_ключ_из_supabase_dashboard")
        print("\n2. Или установите через PowerShell:")
        print("   $env:SUPABASE_KEY='ваш_ключ'")
        print("\n3. Где взять ключ:")
        print("   Supabase Dashboard → Project Settings → API → anon public key")
        return 1
    
    print(f"\n✓ SUPABASE_URL: {supabase_url}")
    print(f"✓ SUPABASE_KEY: {'*' * 20}...{supabase_key[-10:] if len(supabase_key) > 10 else '*' * len(supabase_key)}")
    
    # Получаем путь к файлу
    if len(sys.argv) > 1:
        creds_path = Path(sys.argv[1])
    else:
        # Интерактивный режим
        print("\nВведите путь к файлу service_account.json:")
        print("(или нажмите Enter для поиска в текущей папке)")
        user_input = input("> ").strip()
        
        if user_input:
            creds_path = Path(user_input)
        else:
            # Ищем в текущей папке
            candidates = list(Path.cwd().glob("service_account.json"))
            if candidates:
                creds_path = candidates[0]
                print(f"Найден файл: {creds_path}")
            else:
                print("❌ Файл service_account.json не найден")
                return 1
    
    # Проверяем существование файла
    if not creds_path.exists():
        print(f"❌ Файл не найден: {creds_path}")
        return 1
    
    # Валидация
    if not validate_credentials_json(creds_path):
        return 1
    
    # Читаем JSON
    try:
        with open(creds_path, 'r', encoding='utf-8') as f:
            credentials_json = f.read()
    except Exception as e:
        print(f"❌ Ошибка чтения файла: {e}")
        return 1
    
    # Сохраняем в Supabase
    print("\nЗагрузка в Supabase...")
    if save_credentials_json_to_supabase(credentials_json):
        print("\n✅ Credentials успешно загружены в Supabase!")
        print("\nТеперь можно:")
        print("  - Удалить локальный файл service_account.json")
        print("  - Удалить secret_creds.zip (если был)")
        print("  - Удалить CREDENTIALS_ZIP_PASSWORD из .env")
        print("\nПриложение будет автоматически загружать credentials из Supabase")
        return 0
    else:
        print("\n❌ Не удалось загрузить credentials в Supabase")
        print("\nПроверьте:")
        print("  - Подключение к Supabase (SUPABASE_URL, SUPABASE_KEY)")
        print("  - Существование таблицы credentials (запустите миграцию 006_credentials_table.sql)")
        print("  - Или настройте Supabase Storage bucket")
        return 1


if __name__ == "__main__":
    sys.exit(main())
