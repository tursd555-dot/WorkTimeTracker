#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Упрощенный скрипт для загрузки credentials в Supabase
"""

import sys
import os
import json
from pathlib import Path

# Добавляем корень проекта в путь
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Загружаем .env
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
    load_dotenv()
except ImportError:
    pass

# Импортируем config для установки переменных
try:
    import config
except:
    pass

def main():
    """Главная функция"""
    print("=" * 60)
    print("Загрузка credentials в Supabase")
    print("=" * 60)
    
    # Проверяем переменные
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url:
        print("\n❌ SUPABASE_URL не настроен!")
        print("   Установите: $env:SUPABASE_URL='https://jtgaobxbwibjcvasefzi.supabase.co'")
        return 1
    
    if not supabase_key:
        print("\n❌ SUPABASE_KEY не настроен!")
        print("   Установите: $env:SUPABASE_KEY='ваш_ключ'")
        print("   Или создайте .env файл с SUPABASE_KEY=...")
        return 1
    
    print(f"\n✓ SUPABASE_URL: {supabase_url}")
    print(f"✓ SUPABASE_KEY: {'*' * 20}...{supabase_key[-10:]}")
    
    # Получаем путь к файлу
    if len(sys.argv) > 1:
        creds_path = Path(sys.argv[1])
    else:
        creds_path = Path("service_account.json")
    
    if not creds_path.exists():
        print(f"\n❌ Файл не найден: {creds_path}")
        return 1
    
    # Валидация
    try:
        with open(creds_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if data.get('type') != 'service_account':
            print("❌ Тип credentials должен быть 'service_account'")
            return 1
        
        credentials_json = json.dumps(data)
    except Exception as e:
        print(f"❌ Ошибка чтения файла: {e}")
        return 1
    
    print("✓ Credentials файл валиден")
    
    # Загружаем в Supabase
    try:
        from shared.credentials_storage import save_credentials_json_to_supabase
        
        print("\nЗагрузка в Supabase...")
        if save_credentials_json_to_supabase(credentials_json):
            print("\n✅ Credentials успешно загружены в Supabase!")
            print("\nТеперь можно удалить локальный файл service_account.json")
            return 0
        else:
            print("\n❌ Не удалось загрузить credentials в Supabase")
            print("Проверьте:")
            print("  - Таблица credentials создана? (миграция 006_credentials_table.sql)")
            print("  - Правильность SUPABASE_URL и SUPABASE_KEY")
            return 1
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
