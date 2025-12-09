#!/usr/bin/env python3
# coding: utf-8
"""
Диагностика Telegram-уведомлений
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

print("=" * 80)
print("ДИАГНОСТИКА TELEGRAM-УВЕДОМЛЕНИЙ")
print("=" * 80)
print()

# 1. Проверка config.py
print("1. КОНФИГУРАЦИЯ TELEGRAM:")
print("-" * 80)
try:
    import config
    
    # Проверяем наличие настроек
    attrs = [
        'TELEGRAM_BOT_TOKEN',
        'TELEGRAM_ADMIN_CHAT_ID',
        'TELEGRAM_MONITORING_CHAT_ID',
        'BOT_TOKEN',
        'ADMIN_CHAT_ID',
        'MONITORING_CHAT_ID'
    ]
    
    found = {}
    for attr in attrs:
        if hasattr(config, attr):
            value = getattr(config, attr)
            # Скрываем токен
            if 'TOKEN' in attr and value:
                display = f"{value[:10]}...{value[-5:]}" if len(value) > 15 else "***"
            else:
                display = value
            found[attr] = display
            print(f"  ✓ {attr}: {display}")
    
    if not found:
        print("  ❌ Нет настроек Telegram в config.py!")
    
    print()
    
except Exception as e:
    print(f"  ❌ Ошибка загрузки config.py: {e}")
    print()

# 2. Проверка модулей
print("2. УСТАНОВЛЕННЫЕ МОДУЛИ:")
print("-" * 80)

modules_to_check = [
    ('telegram', 'python-telegram-bot'),
    ('telegram_api', 'telegram_api (custom)'),
    ('telebot', 'pyTelegramBotAPI'),
]

for module_name, package_name in modules_to_check:
    try:
        __import__(module_name)
        print(f"  ✓ {package_name} установлен")
    except ImportError:
        print(f"  ❌ {package_name} НЕ установлен")

print()

# 3. Проверка break_notifications.py
print("3. ФАЙЛ УВЕДОМЛЕНИЙ:")
print("-" * 80)

notif_file = Path("shared/break_notifications.py")
if notif_file.exists():
    print(f"  ✓ Файл найден: {notif_file}")
    print()
    print("  Импорты:")
    with open(notif_file, 'r', encoding='utf-8') as f:
        for line in f:
            if 'import' in line and 'telegram' in line.lower():
                print(f"    {line.strip()}")
else:
    print(f"  ❌ Файл НЕ найден: {notif_file}")

print()

# 4. Проверка telegram_bot
print("4. TELEGRAM BOT:")
print("-" * 80)

bot_main = Path("telegram_bot/main.py")
if bot_main.exists():
    print(f"  ✓ Бот найден: {bot_main}")
else:
    print(f"  ❌ Бот НЕ найден: {bot_main}")

print()

# 5. Рекомендации
print("=" * 80)
print("РЕКОМЕНДАЦИИ:")
print("=" * 80)
print()

if not found:
    print("📌 Добавь в config.py:")
    print()
    print("TELEGRAM_BOT_TOKEN = 'your_bot_token'")
    print("TELEGRAM_ADMIN_CHAT_ID = 'admin_chat_id'")
    print("TELEGRAM_MONITORING_CHAT_ID = 'monitoring_chat_id'")
    print()

missing_modules = []
for module_name, package_name in modules_to_check:
    try:
        __import__(module_name)
    except ImportError:
        missing_modules.append(package_name)

if missing_modules:
    print("📌 Установи модули:")
    print()
    for pkg in missing_modules:
        if 'python-telegram-bot' in pkg:
            print(f"  pip install python-telegram-bot --break-system-packages")
        elif 'pyTelegram' in pkg:
            print(f"  pip install pyTelegramBotAPI --break-system-packages")

print()
print("📌 Проверь логи на ошибки:")
print()
print("  Get-Content \"$env:APPDATA\\WorkTimeTracker\\logs\\wtt-user.log\" -Tail 50 | Select-String telegram")
print()