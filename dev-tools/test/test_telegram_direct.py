#!/usr/bin/env python3
# coding: utf-8
"""
Прямой тест отправки сообщения в Telegram группу
"""
import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_MONITORING_CHAT_ID

print("=" * 80)
print("ТЕСТ ОТПРАВКИ В TELEGRAM ГРУППУ")
print("=" * 80)
print()

token = TELEGRAM_BOT_TOKEN
chat_id = TELEGRAM_MONITORING_CHAT_ID

print(f"Токен: {token[:20]}...{token[-10:]}")
print(f"Chat ID: {chat_id}")
print()

# Тест 1: getMe (проверка токена)
print("1. ПРОВЕРКА ТОКЕНА (getMe):")
print("-" * 80)
try:
    url = f"https://api.telegram.org/bot{token}/getMe"
    response = requests.get(url, timeout=10)
    data = response.json()
    
    if data.get("ok"):
        bot = data.get("result", {})
        print(f"✓ Бот активен:")
        print(f"  Имя: {bot.get('first_name')}")
        print(f"  Username: @{bot.get('username')}")
        print(f"  ID: {bot.get('id')}")
    else:
        print(f"✗ Ошибка: {data}")
        exit(1)
except Exception as e:
    print(f"✗ Ошибка: {e}")
    exit(1)

print()

# Тест 2: getChat (проверка доступа к группе)
print("2. ПРОВЕРКА ДОСТУПА К ГРУППЕ (getChat):")
print("-" * 80)
try:
    url = f"https://api.telegram.org/bot{token}/getChat"
    response = requests.post(url, json={"chat_id": chat_id}, timeout=10)
    data = response.json()
    
    if data.get("ok"):
        chat = data.get("result", {})
        print(f"✓ Группа найдена:")
        print(f"  Название: {chat.get('title')}")
        print(f"  Тип: {chat.get('type')}")
        print(f"  ID: {chat.get('id')}")
    else:
        print(f"✗ Ошибка: {data.get('description')}")
        print(f"  Код: {data.get('error_code')}")
        print()
        print("ПРИЧИНЫ:")
        if "chat not found" in str(data.get('description', '')).lower():
            print("  • Бот не добавлен в группу")
            print("  • Или ID группы неправильный")
        print()
        print("РЕШЕНИЕ:")
        print("  1. Убедись что бот добавлен в группу")
        print("  2. Отправь /start боту в личку")
        print("  3. Добавь бота в группу заново")
        exit(1)
except Exception as e:
    print(f"✗ Ошибка: {e}")
    exit(1)

print()

# Тест 3: Отправка сообщения
print("3. ОТПРАВКА ТЕСТОВОГО СООБЩЕНИЯ:")
print("-" * 80)
try:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    test_message = """🧪 <b>ТЕСТ УВЕДОМЛЕНИЙ</b>

Это тестовое сообщение из системы WorkTimeTracker.
Если вы видите это - уведомления работают! ✅

Время отправки: сейчас"""
    
    payload = {
        "chat_id": chat_id,
        "text": test_message,
        "parse_mode": "HTML",
        "disable_notification": False
    }
    
    print(f"Отправка в {chat_id}...")
    response = requests.post(url, json=payload, timeout=10)
    data = response.json()
    
    if data.get("ok"):
        print("✓ СООБЩЕНИЕ ОТПРАВЛЕНО!")
        print()
        print("=" * 80)
        print("✅ ВСЁ РАБОТАЕТ!")
        print("=" * 80)
        print()
        print("Проверьте группу в Telegram - должно быть тестовое сообщение")
    else:
        print(f"✗ Ошибка отправки: {data.get('description')}")
        print(f"  Полный ответ: {data}")
        print()
        
        if "bot was blocked by the user" in str(data.get('description', '')):
            print("ПРИЧИНА: Бот заблокирован пользователем")
        elif "chat not found" in str(data.get('description', '')):
            print("ПРИЧИНА: Группа не найдена или бот не добавлен")
        elif "bot is not a member" in str(data.get('description', '')):
            print("ПРИЧИНА: Бот не является участником группы")
        
except Exception as e:
    print(f"✗ Ошибка: {e}")
    import traceback
    traceback.print_exc()

print()
