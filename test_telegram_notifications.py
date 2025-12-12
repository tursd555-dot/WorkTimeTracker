#!/usr/bin/env python3
"""
Скрипт для тестирования уведомлений в Telegram

Проверяет:
1. Уведомления в личку при превышении лимита на 1 минуту (с дебаунсингом 5 минут)
2. Уведомления в группу при различных нарушениях (одно за нарушение)
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_overtime_notification():
    """Тест уведомления о превышении лимита"""
    print("\n" + "="*60)
    print("ТЕСТ 1: Уведомление о превышении лимита")
    print("="*60)
    
    try:
        from shared.break_notifications_v2 import send_overtime_notification
        
        # Тест 1: Превышение перерыва на 2 минуты
        print("\n1. Отправка уведомления о превышении перерыва на 2 минуты...")
        result = send_overtime_notification(
            email="test@example.com",  # Замените на реальный email
            break_type="Перерыв",
            duration=17,  # 17 минут при лимите 15
            limit=15,
            overtime=2
        )
        print(f"   Результат: {'✅ Отправлено' if result else '❌ Ошибка'}")
        
        # Тест 2: Превышение обеда на 5 минут
        print("\n2. Отправка уведомления о превышении обеда на 5 минут...")
        result = send_overtime_notification(
            email="test@example.com",
            break_type="Обед",
            duration=65,  # 65 минут при лимите 60
            limit=60,
            overtime=5
        )
        print(f"   Результат: {'✅ Отправлено' if result else '❌ Ошибка'}")
        
        print("\n⚠️  Проверьте Telegram:")
        print("   - В личку должно прийти уведомление (раз в 5 минут)")
        print("   - В группу должно прийти одно уведомление за нарушение")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


def test_out_of_window_notification():
    """Тест уведомления о перерыве вне окна"""
    print("\n" + "="*60)
    print("ТЕСТ 2: Уведомление о перерыве вне временного окна")
    print("="*60)
    
    try:
        from shared.break_notifications_v2 import send_out_of_window_notification
        
        print("\nОтправка уведомления о перерыве вне окна...")
        result = send_out_of_window_notification(
            email="test@example.com",  # Замените на реальный email
            break_type="Перерыв",
            current_time="14:30"  # Вне окна
        )
        print(f"Результат: {'✅ Отправлено' if result else '❌ Ошибка'}")
        
        print("\n⚠️  Проверьте Telegram группу:")
        print("   - Должно прийти одно уведомление за нарушение")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


def test_quota_notification():
    """Тест уведомления о превышении количества"""
    print("\n" + "="*60)
    print("ТЕСТ 3: Уведомление о превышении количества перерывов")
    print("="*60)
    
    try:
        from shared.break_notifications_v2 import send_quota_exceeded_notification
        
        print("\nОтправка уведомления о превышении количества...")
        result = send_quota_exceeded_notification(
            email="test@example.com",  # Замените на реальный email
            break_type="Перерыв",
            used_count=4,  # Использовано 4 при лимите 3
            limit_count=3
        )
        print(f"Результат: {'✅ Отправлено' if result else '❌ Ошибка'}")
        
        print("\n⚠️  Проверьте Telegram группу:")
        print("   - Должно прийти одно уведомление за нарушение")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


def test_debounce():
    """Тест дебаунсинга личных уведомлений"""
    print("\n" + "="*60)
    print("ТЕСТ 4: Дебаунсинг личных уведомлений (5 минут)")
    print("="*60)
    
    try:
        from shared.break_notifications_v2 import send_overtime_notification, reset_user_notifications
        
        email = "test@example.com"  # Замените на реальный email
        
        print("\n1. Первое уведомление (должно отправиться)...")
        result1 = send_overtime_notification(
            email=email,
            break_type="Перерыв",
            duration=16,
            limit=15,
            overtime=1
        )
        print(f"   Результат: {'✅ Отправлено' if result1 else '❌ Ошибка'}")
        
        print("\n2. Второе уведомление сразу (должно быть пропущено из-за дебаунсинга)...")
        result2 = send_overtime_notification(
            email=email,
            break_type="Перерыв",
            duration=17,
            limit=15,
            overtime=2
        )
        print(f"   Результат: {'⏭️  Пропущено (дебаунсинг)' if not result2 else '⚠️  Отправлено (не должно было)'}")
        
        print("\n3. Сброс дебаунсинга...")
        reset_user_notifications(email, "Перерыв")
        print("   ✅ Дебаунсинг сброшен")
        
        print("\n4. Третье уведомление после сброса (должно отправиться)...")
        result3 = send_overtime_notification(
            email=email,
            break_type="Перерыв",
            duration=18,
            limit=15,
            overtime=3
        )
        print(f"   Результат: {'✅ Отправлено' if result3 else '❌ Ошибка'}")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n" + "="*60)
    print("ТЕСТИРОВАНИЕ TELEGRAM УВЕДОМЛЕНИЙ")
    print("="*60)
    print("\n⚠️  ВАЖНО: Замените 'test@example.com' на реальный email для тестирования!")
    print("⚠️  Убедитесь, что Telegram бот настроен и работает.")
    
    input("\nНажмите Enter для начала тестирования...")
    
    # Запускаем тесты
    test_overtime_notification()
    input("\nНажмите Enter для следующего теста...")
    
    test_out_of_window_notification()
    input("\nНажмите Enter для следующего теста...")
    
    test_quota_notification()
    input("\nНажмите Enter для следующего теста...")
    
    test_debounce()
    
    print("\n" + "="*60)
    print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("="*60)
    print("\nПроверьте:")
    print("1. ✅ Уведомления в личку приходят раз в 5 минут")
    print("2. ✅ Уведомления в группу приходят одно за нарушение")
    print("3. ✅ Дебаунсинг работает корректно")
    print("4. ✅ Сброс дебаунсинга при изменении статуса работает")
