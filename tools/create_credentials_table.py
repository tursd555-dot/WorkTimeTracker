#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для создания таблицы credentials в Supabase через Python
"""

import sys
import os
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

# Импортируем config
try:
    import config
except:
    pass

def main():
    """Создание таблицы credentials"""
    print("=" * 60)
    print("Создание таблицы credentials в Supabase")
    print("=" * 60)
    
    # Проверяем переменные
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        print("\n❌ SUPABASE_URL и SUPABASE_KEY должны быть настроены!")
        return 1
    
    try:
        from supabase_api import SupabaseAPI, SupabaseConfig
        
        config_obj = SupabaseConfig(url=supabase_url, key=supabase_key)
        api = SupabaseAPI(config_obj)
        
        print("\nСоздание таблицы credentials...")
        
        # SQL для создания таблицы
        sql = """
        CREATE TABLE IF NOT EXISTS credentials (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            credentials_json TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        
        ALTER TABLE credentials ENABLE ROW LEVEL SECURITY;
        
        DROP POLICY IF EXISTS "Users can read credentials" ON credentials;
        CREATE POLICY "Users can read credentials"
            ON credentials FOR SELECT
            USING (true);
        
        DROP POLICY IF EXISTS "Users can update credentials" ON credentials;
        CREATE POLICY "Users can update credentials"
            ON credentials FOR UPDATE
            USING (true);
        
        DROP POLICY IF EXISTS "Users can insert credentials" ON credentials;
        CREATE POLICY "Users can insert credentials"
            ON credentials FOR INSERT
            WITH CHECK (true);
        """
        
        # Выполняем SQL через Supabase
        # Используем rpc или прямой SQL запрос
        try:
            # Пробуем через SQL функцию
            result = api.client.rpc('exec_sql', {'sql': sql}).execute()
            print("✅ Таблица создана через RPC")
        except:
            # Если RPC не работает, используем прямой запрос к таблице
            # Сначала проверяем существование
            try:
                test = api.client.table('credentials').select('id').limit(1).execute()
                print("✅ Таблица credentials уже существует")
            except:
                print("\n⚠️  Не удалось создать таблицу через Python API")
                print("\nВыполните SQL вручную через Supabase Dashboard:")
                print("\n1. Откройте Supabase Dashboard → SQL Editor")
                print("2. Скопируйте SQL из файла migrations/006_credentials_table.sql")
                print("3. Выполните запрос")
                return 1
        
        print("\n✅ Таблица credentials готова к использованию!")
        return 0
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        print("\nВыполните SQL вручную через Supabase Dashboard:")
        print("SQL Editor → migrations/006_credentials_table.sql")
        return 1

if __name__ == "__main__":
    sys.exit(main())
