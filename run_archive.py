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

from archive_manager import main

if __name__ == "__main__":
    main()
