#!/usr/bin/env python3
"""
Комплексная проверка Telegram уведомлений
Проверяет отправку в общий чат, в личку, при разных условиях
"""
import os
import sys
import logging
from datetime import datetime
from typing import Optional, Dict, List, Tuple

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)

# Загрузка переменных окружения
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    log.warning("python-dotenv не установлен, используем системные переменные окружения")


class TelegramNotificationTester:
    """Тестер для проверки всех типов Telegram уведомлений"""
    
    def __init__(self):
        self.results: List[Dict[str, any]] = []
        self.notifier = None
        
    def check_config(self) -> Tuple[bool, Dict[str, any]]:
        """Проверяет конфигурацию Telegram"""
        log.info("=" * 60)
        log.info("ПРОВЕРКА КОНФИГУРАЦИИ")
        log.info("=" * 60)
        
        config_status = {}
        
        # Проверка токена (из разных источников)
        token = (
            os.getenv("TELEGRAM_BOT_TOKEN") 
            or os.getenv("TELEGRAM_TOKEN")
        )
        
        # Также проверяем config.py
        if not token:
            try:
                import config
                token = getattr(config, 'TELEGRAM_BOT_TOKEN', None)
            except:
                pass
        
        config_status['token'] = {
            'value': token[:20] + "..." if token and len(token) > 20 else token,
            'exists': bool(token),
            'status': 'OK' if token else 'MISSING'
        }
        
        # Проверка chat_id для админа
        admin_chat = os.getenv("TELEGRAM_ADMIN_CHAT_ID")
        if not admin_chat:
            try:
                import config
                admin_chat = getattr(config, 'TELEGRAM_ADMIN_CHAT_ID', None)
            except:
                pass
        
        config_status['admin_chat'] = {
            'value': admin_chat,
            'exists': bool(admin_chat),
            'status': 'OK' if admin_chat else 'MISSING'
        }
        
        # Проверка chat_id для broadcast
        broadcast_chat = os.getenv("TELEGRAM_BROADCAST_CHAT_ID")
        if not broadcast_chat:
            try:
                import config
                broadcast_chat = getattr(config, 'TELEGRAM_BROADCAST_CHAT_ID', None)
            except:
                pass
        
        config_status['broadcast_chat'] = {
            'value': broadcast_chat,
            'exists': bool(broadcast_chat),
            'status': 'OK' if broadcast_chat else 'MISSING'
        }
        
        # Проверка chat_id для мониторинга
        monitoring_chat = os.getenv("TELEGRAM_MONITORING_CHAT_ID")
        if not monitoring_chat:
            try:
                import config
                monitoring_chat = getattr(config, 'TELEGRAM_MONITORING_CHAT_ID', None)
            except:
                pass
        
        config_status['monitoring_chat'] = {
            'value': monitoring_chat,
            'exists': bool(monitoring_chat),
            'status': 'OK' if monitoring_chat else 'MISSING'
        }
        
        # Вывод результатов
        for key, info in config_status.items():
            status_icon = "✓" if info['status'] == 'OK' else "✗"
            value_display = info['value'] if info['value'] else '(не задано)'
            log.info(f"{status_icon} {key}: {info['status']} - {value_display}")
        
        # Проверяем минимальные требования (токен обязателен)
        has_token = config_status['token']['exists']
        has_at_least_one_chat = any([
            config_status['admin_chat']['exists'],
            config_status['broadcast_chat']['exists'],
            config_status['monitoring_chat']['exists']
        ])
        
        if not has_token:
            log.error("\n❌ TELEGRAM_BOT_TOKEN обязателен для работы!")
            log.info("   Установите переменную окружения или в config.py")
        
        if not has_at_least_one_chat:
            log.warning("\n⚠️  Не настроен ни один chat_id. Уведомления не будут отправляться.")
            log.info("   Настройте хотя бы один из:")
            log.info("   - TELEGRAM_ADMIN_CHAT_ID")
            log.info("   - TELEGRAM_BROADCAST_CHAT_ID")
            log.info("   - TELEGRAM_MONITORING_CHAT_ID")
        
        return has_token and has_at_least_one_chat, config_status
    
    def init_notifier(self) -> bool:
        """Инициализирует TelegramNotifier"""
        try:
            from telegram_bot.notifier import TelegramNotifier
            self.notifier = TelegramNotifier()
            log.info("✓ TelegramNotifier инициализирован успешно")
            log.info(f"  - Admin chat: {self.notifier.admin_chat or 'не настроен'}")
            log.info(f"  - Broadcast chat: {self.notifier.broadcast_chat or 'не настроен'}")
            log.info(f"  - Monitoring chat: {self.notifier.monitoring_chat or 'не настроен'}")
            log.info(f"  - Min interval: {self.notifier.min_interval} сек")
            log.info(f"  - Default silent: {self.notifier.default_silent}")
            return True
        except RuntimeError as e:
            if "TELEGRAM_BOT_TOKEN" in str(e):
                log.error(f"✗ Ошибка: {e}")
                log.info("   Установите TELEGRAM_BOT_TOKEN в переменных окружения или config.py")
            else:
                log.error(f"✗ Ошибка инициализации TelegramNotifier: {e}")
            return False
        except Exception as e:
            log.error(f"✗ Ошибка инициализации TelegramNotifier: {e}")
            import traceback
            log.debug(traceback.format_exc())
            return False
    
    def test_service_notification(self, silent: bool = False) -> bool:
        """Тест отправки служебного уведомления админу"""
        log.info("\n" + "=" * 60)
        log.info(f"ТЕСТ 1: Служебное уведомление (silent={silent})")
        log.info("=" * 60)
        
        if not self.notifier:
            log.error("TelegramNotifier не инициализирован")
            return False
        
        message = (
            f"🧪 Тестовое служебное уведомление\n"
            f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Тип: service notification\n"
            f"Silent: {silent}"
        )
        
        try:
            result = self.notifier.send_service(message, silent=silent)
            status = "✓ УСПЕШНО" if result else "✗ ОШИБКА"
            log.info(f"{status}: Отправка в админский чат")
            
            self.results.append({
                'test': 'service',
                'silent': silent,
                'success': result,
                'message': message[:50] + "..."
            })
            
            return result
        except Exception as e:
            log.error(f"✗ Исключение при отправке: {e}")
            self.results.append({
                'test': 'service',
                'silent': silent,
                'success': False,
                'error': str(e)
            })
            return False
    
    def test_personal_notification(self, email: str, silent: bool = False) -> bool:
        """Тест отправки персонального уведомления"""
        log.info("\n" + "=" * 60)
        log.info(f"ТЕСТ 2: Персональное уведомление (email={email}, silent={silent})")
        log.info("=" * 60)
        
        if not self.notifier:
            log.error("TelegramNotifier не инициализирован")
            return False
        
        message = (
            f"🧪 Тестовое персональное уведомление\n"
            f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Получатель: {email}\n"
            f"Silent: {silent}"
        )
        
        try:
            result = self.notifier.send_personal(email, message, silent=silent)
            status = "✓ УСПЕШНО" if result else "✗ ОШИБКА"
            log.info(f"{status}: Отправка в личку пользователю {email}")
            
            if not result:
                log.warning("Возможные причины:")
                log.warning("  - Email не найден в таблице Users")
                log.warning("  - У пользователя не указан Telegram chat_id")
                log.warning("  - Проблема с подключением к API")
            
            self.results.append({
                'test': 'personal',
                'email': email,
                'silent': silent,
                'success': result,
                'message': message[:50] + "..."
            })
            
            return result
        except Exception as e:
            log.error(f"✗ Исключение при отправке: {e}")
            self.results.append({
                'test': 'personal',
                'email': email,
                'silent': silent,
                'success': False,
                'error': str(e)
            })
            return False
    
    def test_group_notification(self, group: Optional[str] = None, for_all: bool = False, silent: bool = False) -> bool:
        """Тест отправки группового уведомления"""
        log.info("\n" + "=" * 60)
        log.info(f"ТЕСТ 3: Групповое уведомление (group={group}, for_all={for_all}, silent={silent})")
        log.info("=" * 60)
        
        if not self.notifier:
            log.error("TelegramNotifier не инициализирован")
            return False
        
        message = (
            f"🧪 Тестовое групповое уведомление\n"
            f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Группа: {group if group else ('Все' if for_all else 'Не указана')}\n"
            f"Silent: {silent}"
        )
        
        try:
            result = self.notifier.send_group(message, group=group, for_all=for_all, silent=silent)
            status = "✓ УСПЕШНО" if result else "✗ ОШИБКА"
            log.info(f"{status}: Отправка в общий чат")
            
            if not result:
                log.warning("Возможные причины:")
                log.warning("  - TELEGRAM_BROADCAST_CHAT_ID не настроен")
                log.warning("  - Проблема с подключением к API")
            
            self.results.append({
                'test': 'group',
                'group': group,
                'for_all': for_all,
                'silent': silent,
                'success': result,
                'message': message[:50] + "..."
            })
            
            return result
        except Exception as e:
            log.error(f"✗ Исключение при отправке: {e}")
            self.results.append({
                'test': 'group',
                'group': group,
                'for_all': for_all,
                'silent': silent,
                'success': False,
                'error': str(e)
            })
            return False
    
    def test_monitoring_notification(self, silent: bool = False) -> bool:
        """Тест отправки уведомления в мониторинг"""
        log.info("\n" + "=" * 60)
        log.info(f"ТЕСТ 4: Мониторинг уведомление (silent={silent})")
        log.info("=" * 60)
        
        if not self.notifier:
            log.error("TelegramNotifier не инициализирован")
            return False
        
        message = (
            f"🧪 Тестовое мониторинг уведомление\n"
            f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Тип: monitoring notification\n"
            f"Silent: {silent}"
        )
        
        try:
            result = self.notifier.send_monitoring(message, silent=silent)
            status = "✓ УСПЕШНО" if result else "✗ ОШИБКА"
            log.info(f"{status}: Отправка в мониторинг чат")
            
            if not result:
                log.warning("Возможные причины:")
                log.warning("  - TELEGRAM_MONITORING_CHAT_ID не настроен")
                log.warning("  - Проблема с подключением к API")
            
            self.results.append({
                'test': 'monitoring',
                'silent': silent,
                'success': result,
                'message': message[:50] + "..."
            })
            
            return result
        except Exception as e:
            log.error(f"✗ Исключение при отправке: {e}")
            self.results.append({
                'test': 'monitoring',
                'silent': silent,
                'success': False,
                'error': str(e)
            })
            return False
    
    def print_summary(self):
        """Выводит итоговую сводку тестов"""
        log.info("\n" + "=" * 60)
        log.info("ИТОГОВАЯ СВОДКА")
        log.info("=" * 60)
        
        total = len(self.results)
        successful = sum(1 for r in self.results if r.get('success', False))
        failed = total - successful
        
        log.info(f"Всего тестов: {total}")
        log.info(f"Успешных: {successful} ✓")
        log.info(f"Неудачных: {failed} ✗")
        
        log.info("\nДетализация:")
        for i, result in enumerate(self.results, 1):
            status_icon = "✓" if result.get('success', False) else "✗"
            test_name = result.get('test', 'unknown')
            log.info(f"  {i}. {status_icon} {test_name}")
            if not result.get('success', False) and 'error' in result:
                log.info(f"     Ошибка: {result['error']}")
        
        log.info("\n" + "=" * 60)
        
        if successful == total:
            log.info("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        elif successful > 0:
            log.warning(f"⚠️  Частичный успех: {successful}/{total} тестов прошли")
        else:
            log.error("❌ ВСЕ ТЕСТЫ ПРОВАЛЕНЫ")


def main():
    """Главная функция для запуска тестов"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Комплексная проверка Telegram уведомлений"
    )
    parser.add_argument(
        "--email",
        help="Email для теста персональных уведомлений (если не указан, тест будет пропущен)"
    )
    parser.add_argument(
        "--skip-personal",
        action="store_true",
        help="Пропустить тест персональных уведомлений"
    )
    parser.add_argument(
        "--skip-group",
        action="store_true",
        help="Пропустить тест групповых уведомлений"
    )
    parser.add_argument(
        "--skip-service",
        action="store_true",
        help="Пропустить тест служебных уведомлений"
    )
    parser.add_argument(
        "--skip-monitoring",
        action="store_true",
        help="Пропустить тест мониторинг уведомлений"
    )
    
    args = parser.parse_args()
    
    tester = TelegramNotificationTester()
    
    # Проверка конфигурации
    config_ok, config = tester.check_config()
    
    if not config_ok:
        log.warning("\n⚠️  Конфигурация неполная, но продолжаем тестирование...")
    
    # Инициализация notifier
    if not tester.init_notifier():
        log.error("Не удалось инициализировать TelegramNotifier. Проверьте конфигурацию.")
        return 1
    
    # Запуск тестов
    log.info("\n" + "=" * 60)
    log.info("ЗАПУСК ТЕСТОВ")
    log.info("=" * 60)
    
    # Тест 1: Служебные уведомления
    if not args.skip_service:
        tester.test_service_notification(silent=False)
        tester.test_service_notification(silent=True)
    
    # Тест 2: Персональные уведомления
    if not args.skip_personal:
        if args.email:
            tester.test_personal_notification(args.email, silent=False)
            tester.test_personal_notification(args.email, silent=True)
        else:
            log.warning("\n⚠️  Пропущен тест персональных уведомлений (не указан --email)")
            log.info("   Используйте: python test_telegram_notifications.py --email user@example.com")
    
    # Тест 3: Групповые уведомления
    if not args.skip_group:
        tester.test_group_notification(group="Тест", for_all=False, silent=False)
        tester.test_group_notification(group=None, for_all=True, silent=False)
        tester.test_group_notification(group="Тест", for_all=False, silent=True)
    
    # Тест 4: Мониторинг уведомления
    if not args.skip_monitoring:
        tester.test_monitoring_notification(silent=False)
        tester.test_monitoring_notification(silent=True)
    
    # Вывод итоговой сводки
    tester.print_summary()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
