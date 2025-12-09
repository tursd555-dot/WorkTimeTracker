#!/usr/bin/env python3
# coding: utf-8
"""
Тест отправки Telegram-уведомлений
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

print("=" * 80)
print("ТЕСТ TELEGRAM-УВЕДОМЛЕНИЙ")
print("=" * 80)
print()

# 1. Тест импорта
print("1. Импорт модуля...")
try:
    from telegram_api import TelegramAPI
    print("   ✓ telegram_api импортирован")
except Exception as e:
    print(f"   ✗ Ошибка импорта: {e}")
    exit(1)

# 2. Инициализация
print()
print("2. Инициализация TelegramAPI...")
try:
    api = TelegramAPI()
    print("   ✓ TelegramAPI инициализирован")
    print(f"   - Admin chat: {api.notifier.admin_chat or 'не настроен'}")
    print(f"   - Monitoring chat: {api.notifier.monitoring_chat or 'не настроен'}")
    print(f"   - Broadcast chat: {api.notifier.broadcast_chat or 'не настроен'}")
except Exception as e:
    print(f"   ✗ Ошибка инициализации: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# 3. Тест отправки в мониторинг
print()
print("3. Отправка тестового сообщения в МОНИТОРИНГ...")
test_message = (
    "🧪 ТЕСТОВОЕ УВЕДОМЛЕНИЕ\n"
    "\n"
    "Это проверка системы уведомлений о превышении лимитов перерывов.\n"
    "Если вы видите это сообщение - система работает! ✅"
)

try:
    result = api.send_to_monitoring(test_message, silent=False)
    if result:
        print("   ✓ Сообщение отправлено успешно!")
        print("   Проверьте группу мониторинга в Telegram")
    else:
        print("   ✗ Отправка не удалась (вернула False)")
except Exception as e:
    print(f"   ✗ Ошибка отправки: {e}")
    import traceback
    traceback.print_exc()

# 4. Тест уведомления о превышении лимита
print()
print("4. Тест уведомления о превышении лимита...")
try:
    from shared.break_notifications import send_overtime_notification
    
    result = send_overtime_notification(
        email="9@ya.ru",  # Замени на реальный email из таблицы Users
        break_type="Перерыв",
        duration=20,
        limit=15,
        overtime=5
    )
    
    if result:
        print("   ✓ Уведомление отправлено!")
    else:
        print("   ✗ Уведомление не отправлено")
        
except Exception as e:
    print(f"   ✗ Ошибка: {e}")
    import traceback
    traceback.print_exc()

# 5. Тест персонального уведомления
print()
print("5. Тест персонального уведомления...")
email_input = input("Введи email для теста (Enter = пропустить): ").strip()

if email_input:
    test_personal_message = (
        "🧪 Тестовое персональное уведомление\n"
        "\n"
        "Если вы видите это сообщение - привязка email к Telegram работает!"
    )
    
    try:
        result = api.send_to_user(email_input, test_personal_message)
        if result:
            print(f"   ✓ Сообщение отправлено пользователю {email_input}")
        else:
            print(f"   ✗ Не удалось отправить (возможно chat_id не найден)")
            print(f"   Убедитесь что пользователь написал боту и привязал email")
    except Exception as e:
        print(f"   ✗ Ошибка: {e}")
else:
    print("   Пропущено")

print()
print("=" * 80)
print("РЕЗУЛЬТАТЫ:")
print("=" * 80)
print()
print("✅ Если сообщения пришли - система работает!")
print("❌ Если нет:")
print("   1. Проверь TELEGRAM_MONITORING_CHAT_ID в config.py")
print("   2. Проверь что бот добавлен в группу")
print("   3. Проверь что у бота права на отправку сообщений")
print()
