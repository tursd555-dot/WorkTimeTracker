"""
Telegram Bot Monitor для WorkTimeTracker
Работает 24/7, мониторит Supabase и отправляет уведомления

Использование:
    python telegram_bot/monitor_bot.py
    или
    WorkTimeTracker_Bot.exe (если собран)
"""
from __future__ import annotations

import sys
import os
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Set, Optional, List
from collections import defaultdict

# Добавляем корень проекта в sys.path
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.chdir(ROOT_DIR)

# Импорты
from config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_ADMIN_CHAT_ID,
    TELEGRAM_MONITORING_CHAT_ID,
)
from telegram_bot.notifier import TelegramNotifier
from supabase_api import get_supabase_api
from shared.time_utils import format_datetime_moscow, format_time_moscow, now_moscow

# Настройка логирования
from logging_setup import setup_logging
from config import LOG_DIR

log_path = setup_logging(app_name="wtt-monitor-bot", log_dir=LOG_DIR)
logger = logging.getLogger(__name__)
logger.info("Telegram Monitor Bot started (log: %s)", log_path)

# Константы
CHECK_INTERVAL = 30  # Проверка каждые 30 секунд
VIOLATIONS_CHECK_INTERVAL = 60  # Проверка нарушений каждую минуту
BREAKS_CHECK_INTERVAL = 30  # Проверка перерывов каждые 30 секунд

# Отслеживание уже отправленных уведомлений
_sent_violations: Set[str] = set()  # violation_id или ключ
_sent_break_warnings: Dict[str, datetime] = {}  # email_break_type -> last_sent
_last_check_time: Optional[datetime] = None


class MonitorBot:
    """Бот-монитор для отслеживания событий в Supabase"""
    
    def __init__(self):
        """Инициализация бота"""
        try:
            # Проверяем наличие токена
            if not TELEGRAM_BOT_TOKEN:
                raise ValueError("TELEGRAM_BOT_TOKEN не задан в config.py или .env")
            
            # Инициализируем TelegramNotifier
            self.notifier = TelegramNotifier(
                token=TELEGRAM_BOT_TOKEN,
                admin_chat_id=TELEGRAM_ADMIN_CHAT_ID,
                monitoring_chat_id=TELEGRAM_MONITORING_CHAT_ID,
            )
            
            # Инициализируем Supabase API
            self.supabase = get_supabase_api()
            
            logger.info("✅ Monitor Bot initialized successfully")
            logger.info(f"   Admin chat: {TELEGRAM_ADMIN_CHAT_ID}")
            logger.info(f"   Monitoring chat: {TELEGRAM_MONITORING_CHAT_ID}")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Monitor Bot: {e}", exc_info=True)
            raise
    
    def check_violations(self):
        """Проверяет новые нарушения в Supabase"""
        try:
            # Получаем нарушения за последний час (используем московское время)
            now = now_moscow()
            hour_ago = now - timedelta(hours=1)
            date_from = hour_ago.isoformat()
            date_to = now.isoformat()
            
            # Получаем нарушения из Supabase
            violations = self.supabase.client.table('violations').select('*').gte(
                'timestamp', date_from
            ).lte('timestamp', date_to).execute()
            
            violations_data = violations.data if hasattr(violations, 'data') else []
            
            new_violations = []
            for violation in violations_data:
                # Создаем уникальный ключ для нарушения
                violation_id = violation.get('id') or f"{violation.get('email')}_{violation.get('timestamp')}_{violation.get('violation_type')}"
                
                if violation_id not in _sent_violations:
                    _sent_violations.add(violation_id)
                    new_violations.append(violation)
            
            # Отправляем уведомления о новых нарушениях
            for violation in new_violations:
                self._send_violation_notification(violation)
            
            # Очищаем старые записи (старше 24 часов)
            if len(_sent_violations) > 1000:
                _sent_violations.clear()
                logger.info("Cleared violations cache")
            
            return len(new_violations)
            
        except Exception as e:
            logger.error(f"Error checking violations: {e}", exc_info=True)
            return 0
    
    def _send_violation_notification(self, violation: Dict):
        """Отправляет уведомление о нарушении"""
        try:
            email = violation.get('email', 'Unknown')
            violation_type = violation.get('violation_type', 'UNKNOWN')
            timestamp = violation.get('timestamp', '')
            details = violation.get('details', '')
            
            # Форматируем время
            time_str = format_datetime_moscow(timestamp) if timestamp else "N/A"
            
            # Типы нарушений
            violation_names = {
                'OUT_OF_WINDOW': 'Вне временного окна',
                'OVER_LIMIT': 'Превышен лимит времени',
                'QUOTA_EXCEEDED': 'Превышено количество перерывов',
            }
            violation_name = violation_names.get(violation_type, violation_type)
            
            # Формируем сообщение
            message = (
                f"⚠️ НАРУШЕНИЕ ПРАВИЛ ПЕРЕРЫВОВ\n\n"
                f"Сотрудник: {email}\n"
                f"Тип: {violation_name}\n"
                f"Время: {time_str}\n"
            )
            
            if details:
                message += f"Детали: {details}\n"
            
            # Отправляем в группу мониторинга
            self.notifier.send_monitoring(message, silent=False)
            
            logger.info(f"Sent violation notification: {email} - {violation_type}")
            
        except Exception as e:
            logger.error(f"Error sending violation notification: {e}", exc_info=True)
    
    def check_active_breaks(self):
        """Проверяет активные перерывы на превышение лимитов"""
        try:
            # Получаем активные перерывы из break_log
            # Ищем перерывы, которые начались недавно и еще не закончились
            now = now_moscow()
            recent_time = now - timedelta(hours=2)
            
            # Получаем активные перерывы (без end_time или с недавним start_time)
            breaks = self.supabase.client.table('break_log').select('*').gte(
                'start_time', recent_time.isoformat()
            ).is_('end_time', 'null').execute()
            
            breaks_data = breaks.data if hasattr(breaks, 'data') else []
            
            warnings_sent = 0
            for break_entry in breaks_data:
                email = break_entry.get('email', '')
                break_type = break_entry.get('break_type', '')
                start_time_str = break_entry.get('start_time', '')
                
                if not email or not start_time_str:
                    continue
                
                # Парсим время начала
                try:
                    if 'T' in start_time_str:
                        start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                    else:
                        start_time = datetime.strptime(start_time_str[:19], '%Y-%m-%d %H:%M:%S')
                    
                    # Вычисляем длительность (конвертируем start_time в московское время для правильного расчета)
                    if start_time.tzinfo is None:
                        # Если время без timezone, считаем что это UTC и конвертируем в московское
                        from shared.time_utils import to_moscow
                        start_time_moscow = to_moscow(start_time)
                    else:
                        # Если есть timezone, конвертируем в московское
                        from shared.time_utils import to_moscow
                        start_time_moscow = to_moscow(start_time)
                    
                    # Вычисляем длительность в московском времени
                    duration = (now - start_time_moscow).total_seconds() / 60  # в минутах
                    
                    # Лимиты (из config.py)
                    limit_minutes = 15 if break_type == 'Перерыв' else 60  # Перерыв: 15 мин, Обед: 60 мин
                    
                    # Проверяем превышение
                    if duration > limit_minutes:
                        # Проверяем дебаунсинг (раз в 5 минут)
                        key = f"{email}_{break_type}"
                        last_sent = _sent_break_warnings.get(key)
                        
                        if last_sent is None or (now - last_sent).total_seconds() >= 300:  # 5 минут
                            overtime = int(duration - limit_minutes)
                            self._send_break_warning(email, break_type, duration, limit_minutes, overtime)
                            _sent_break_warnings[key] = now
                            warnings_sent += 1
                
                except Exception as e:
                    logger.warning(f"Error processing break entry: {e}")
                    continue
            
            # Очищаем старые записи
            if len(_sent_break_warnings) > 500:
                cutoff = now - timedelta(hours=24)
                _sent_break_warnings = {
                    k: v for k, v in _sent_break_warnings.items() 
                    if v > cutoff
                }
            
            return warnings_sent
            
        except Exception as e:
            logger.error(f"Error checking active breaks: {e}", exc_info=True)
            return 0
    
    def _send_break_warning(self, email: str, break_type: str, duration: float, limit: int, overtime: int):
        """Отправляет предупреждение о превышении лимита перерыва"""
        try:
            current_time = format_time_moscow(now_moscow(), '%H:%M:%S')
            
            message = (
                f"⏰ ПРЕВЫШЕНИЕ ЛИМИТА ПЕРЕРЫВА\n\n"
                f"Сотрудник: {email}\n"
                f"Тип: {break_type}\n"
                f"Длительность: {int(duration)} мин (лимит {limit} мин)\n"
                f"Превышение: +{overtime} мин\n"
                f"Время: {current_time}"
            )
            
            # Отправляем в группу мониторинга
            self.notifier.send_monitoring(message, silent=False)
            
            logger.info(f"Sent break warning: {email} - {break_type} ({int(duration)} мин)")
            
        except Exception as e:
            logger.error(f"Error sending break warning: {e}", exc_info=True)
    
    def run(self):
        """Основной цикл работы бота"""
        logger.info("🚀 Starting Monitor Bot main loop...")
        logger.info(f"   Check interval: {CHECK_INTERVAL}s")
        logger.info(f"   Violations check: {VIOLATIONS_CHECK_INTERVAL}s")
        logger.info(f"   Breaks check: {BREAKS_CHECK_INTERVAL}s")
        
        last_violations_check = now_moscow()
        last_breaks_check = now_moscow()
        
        # Отправляем стартовое сообщение
        try:
            self.notifier.send_service(
                "🤖 Monitor Bot запущен и работает 24/7\n"
                "Мониторинг нарушений и перерывов активен.",
                silent=True
            )
        except Exception as e:
            logger.warning(f"Could not send startup message: {e}")
        
        try:
            while True:
                now = now_moscow()
                
                # Проверяем нарушения
                if (now - last_violations_check).total_seconds() >= VIOLATIONS_CHECK_INTERVAL:
                    violations_count = self.check_violations()
                    if violations_count > 0:
                        logger.info(f"Found {violations_count} new violations")
                    last_violations_check = now
                
                # Проверяем активные перерывы
                if (now - last_breaks_check).total_seconds() >= BREAKS_CHECK_INTERVAL:
                    warnings_count = self.check_active_breaks()
                    if warnings_count > 0:
                        logger.info(f"Sent {warnings_count} break warnings")
                    last_breaks_check = now
                
                # Ждем перед следующей проверкой
                time.sleep(CHECK_INTERVAL)
                
        except KeyboardInterrupt:
            logger.info("Monitor Bot stopped by user")
            try:
                self.notifier.send_service(
                    "🛑 Monitor Bot остановлен",
                    silent=True
                )
            except:
                pass
        except Exception as e:
            logger.error(f"Fatal error in main loop: {e}", exc_info=True)
            raise


def main():
    """Точка входа"""
    try:
        bot = MonitorBot()
        bot.run()
    except Exception as e:
        logger.critical(f"Failed to start Monitor Bot: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
