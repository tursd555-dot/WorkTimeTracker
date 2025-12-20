#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для сборки отдельного компонента WorkTimeTracker

Использование:
    python build_single.py user      # Пользовательская часть
    python build_single.py admin      # Админка
    python build_single.py monitor    # Реал тайм монитор
    python build_single.py bot        # Телеграм бот
"""

import sys
import os
from pathlib import Path

# Импортируем функции из главного скрипта
sys.path.insert(0, str(Path(__file__).parent))
from build_windows import (
    build_user_app,
    build_admin_app,
    build_monitor_app,
    build_bot_app,
    check_required_files,
    ROOT_DIR
)

def main():
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python build_single.py user      # Пользовательская часть")
        print("  python build_single.py admin      # Админка")
        print("  python build_single.py monitor    # Реал тайм монитор")
        print("  python build_single.py bot       # Телеграм бот")
        sys.exit(1)
    
    component = sys.argv[1].lower()
    os.chdir(ROOT_DIR)
    
    if not check_required_files():
        print("❌ Проверка файлов не пройдена")
        sys.exit(1)
    
    success = False
    if component == 'user':
        success = build_user_app()
    elif component == 'admin':
        success = build_admin_app()
    elif component == 'monitor':
        success = build_monitor_app()
    elif component == 'bot':
        success = build_bot_app()
    else:
        print(f"❌ Неизвестный компонент: {component}")
        print("Доступные: user, admin, monitor, bot")
        sys.exit(1)
    
    if success:
        print(f"✅ Компонент '{component}' успешно собран!")
        print(f"📁 Результат в: dist/WorkTimeTracker_{component.capitalize()}/")
    else:
        print(f"❌ Ошибка сборки компонента '{component}'")
        sys.exit(1)

if __name__ == "__main__":
    main()
