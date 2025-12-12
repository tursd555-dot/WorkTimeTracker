#!/usr/bin/env python3
"""
Скрипт запуска отдельного приложения мониторинга статусов в реальном времени
"""
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from admin_app.realtime_monitor import run_monitor

if __name__ == "__main__":
    run_monitor()
