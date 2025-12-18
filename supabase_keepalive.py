"""
Supabase Keep-Alive Script
===========================

Скрипт для поддержания активности Supabase проекта на бесплатном тарифе.
Supabase приостанавливает неактивные проекты через 7 дней бездействия.

Этот скрипт выполняет легкий запрос к БД, чтобы предотвратить приостановку.

Использование:
    python supabase_keepalive.py

Автоматический запуск:
    - GitHub Actions (рекомендуется): см. .github/workflows/supabase-keepalive.yml
    - Windows Task Scheduler: запускать каждые 3 дня
    - Linux cron: 0 0 */3 * * python /path/to/supabase_keepalive.py
"""

import os
import sys
import logging
from datetime import datetime, timezone
from typing import Optional

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_env_file():
    """Загрузить переменные из .env файла"""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        logger.info("✅ Загружены переменные из .env")
    except ImportError:
        logger.warning("⚠️ python-dotenv не установлен, используем системные переменные")


def get_supabase_config() -> tuple[Optional[str], Optional[str]]:
    """Получить конфигурацию Supabase из переменных окружения"""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        logger.error("❌ SUPABASE_URL и SUPABASE_KEY должны быть установлены!")
        logger.error("   Установите переменные окружения или создайте .env файл")
        return None, None

    return url, key


def ping_supabase(url: str, key: str) -> bool:
    """
    Выполнить легкий запрос к Supabase для поддержания активности

    Args:
        url: URL проекта Supabase
        key: API ключ (anon/public)

    Returns:
        True если успешно, False иначе
    """
    try:
        from supabase import create_client

        logger.info(f"🔌 Подключение к Supabase: {url}")
        client = create_client(url, key)

        # Выполняем минимальный запрос - просто проверяем подключение
        # Используем limit(1) чтобы минимизировать нагрузку
        response = client.table('users').select('id').limit(1).execute()

        logger.info(f"✅ Supabase активен! Запрос выполнен успешно")
        logger.info(f"   Время: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

        # Опционально: записать в таблицу keepalive_log (если существует)
        try:
            client.table('keepalive_log').insert({
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'status': 'success'
            }).execute()
            logger.info("   Запись в keepalive_log добавлена")
        except Exception as e:
            # Таблица может не существовать - это нормально
            logger.debug(f"   keepalive_log недоступен: {e}")

        return True

    except ImportError:
        logger.error("❌ Библиотека 'supabase' не установлена!")
        logger.error("   Установите: pip install supabase")
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка при выполнении запроса: {e}")
        return False


def main():
    """Главная функция"""
    logger.info("=" * 70)
    logger.info("🔄 SUPABASE KEEP-ALIVE SCRIPT")
    logger.info("=" * 70)

    # Загрузить .env если доступен
    load_env_file()

    # Получить конфигурацию
    url, key = get_supabase_config()
    if not url or not key:
        sys.exit(1)

    # Выполнить ping
    success = ping_supabase(url, key)

    logger.info("=" * 70)
    if success:
        logger.info("✅ ГОТОВО! Supabase проект активен")
        logger.info("   Следующий запуск: через 3 дня")
        sys.exit(0)
    else:
        logger.error("❌ ОШИБКА! Не удалось активировать Supabase")
        logger.error("   Проверьте настройки и повторите попытку")
        sys.exit(1)


if __name__ == "__main__":
    main()
