#!/usr/bin/env python3
"""
Скрипт для автоматического запуска архивации данных из Supabase в Google Таблицы
Можно запускать вручную или настроить как cron job / scheduled task
"""
import sys
import os
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

# Загружаем переменные окружения из .env файла
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        load_dotenv()  # Стандартная загрузка
except ImportError:
    pass  # dotenv не установлен

from archive_manager import main

if __name__ == "__main__":
    main()
