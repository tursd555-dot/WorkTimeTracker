#!/usr/bin/env python3
"""
Скрипт для удаления тестового пользователя test_session@example.com
и всех связанных с ним записей из базы данных.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

import logging
from admin_app.repo import AdminRepo
from api_adapter import get_sheets_api

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TEST_EMAIL = "test_session@example.com"


def delete_test_user():
    """Удаляет тестового пользователя и все связанные записи"""
    
    repo = AdminRepo()
    api = get_sheets_api()
    
    logger.info(f"🔍 Начинаем удаление пользователя {TEST_EMAIL}...")
    
    deleted_count = 0
    
    try:
        # 1. Удаляем из ActiveSessions
        logger.info("1. Удаление из ActiveSessions...")
        try:
            if hasattr(api, 'client') and hasattr(api.client, 'table'):
                # Получаем все сессии этого пользователя
                sessions = api.client.table('active_sessions')\
                    .select('*')\
                    .eq('email', TEST_EMAIL)\
                    .execute()
                
                if sessions.data:
                    logger.info(f"   Найдено {len(sessions.data)} активных сессий")
                    for session in sessions.data:
                        session_id = session.get('session_id')
                        if session_id:
                            # Удаляем сессию
                            api.client.table('active_sessions')\
                                .delete()\
                                .eq('email', TEST_EMAIL)\
                                .eq('session_id', session_id)\
                                .execute()
                            deleted_count += 1
                            logger.info(f"   ✅ Удалена сессия {session_id}")
                else:
                    logger.info("   Нет активных сессий")
        except Exception as e:
            logger.warning(f"   ⚠️ Ошибка при удалении из ActiveSessions: {e}")
        
        # 2. Удаляем из work_log (используем метод API если есть)
        logger.info("2. Удаление из work_log...")
        try:
            if hasattr(api, 'client') and hasattr(api.client, 'table'):
                # Сначала проверяем количество записей
                work_logs = api.client.table('work_log')\
                    .select('id', count='exact')\
                    .eq('email', TEST_EMAIL)\
                    .execute()
                
                count = work_logs.count if hasattr(work_logs, 'count') else len(work_logs.data) if work_logs.data else 0
                
                if count > 0:
                    logger.info(f"   Найдено {count} записей в work_log")
                    result = api.client.table('work_log')\
                        .delete()\
                        .eq('email', TEST_EMAIL)\
                        .execute()
                    deleted_count += count
                    logger.info(f"   ✅ Удалено {count} записей из work_log")
                else:
                    logger.info("   Нет записей в work_log")
        except Exception as e:
            logger.warning(f"   ⚠️ Ошибка при удалении из work_log: {e}")
        
        # 3. Удаляем из break_log (если есть такая таблица)
        logger.info("3. Удаление из break_log...")
        try:
            if hasattr(api, 'client') and hasattr(api.client, 'table'):
                # Пробуем разные варианты названия таблицы
                for table_name in ['break_log', 'break_logs', 'breaks', 'usage_log']:
                    try:
                        breaks = api.client.table(table_name)\
                            .select('id', count='exact')\
                            .eq('email', TEST_EMAIL)\
                            .execute()
                        
                        count = breaks.count if hasattr(breaks, 'count') else len(breaks.data) if breaks.data else 0
                        
                        if count > 0:
                            logger.info(f"   Найдено {count} записей в {table_name}")
                            api.client.table(table_name)\
                                .delete()\
                                .eq('email', TEST_EMAIL)\
                                .execute()
                            deleted_count += count
                            logger.info(f"   ✅ Удалено {count} записей из {table_name}")
                            break
                    except Exception as e:
                        logger.debug(f"   Таблица {table_name} не найдена или ошибка: {e}")
                        continue
                else:
                    logger.info("   Таблица break_log не найдена или пуста")
        except Exception as e:
            logger.warning(f"   ⚠️ Ошибка при удалении из break_log: {e}")
        
        # 4. Удаляем из user_break_assignments (если есть)
        logger.info("4. Удаление из user_break_assignments...")
        try:
            if hasattr(api, 'client') and hasattr(api.client, 'table'):
                assignments = api.client.table('user_break_assignments')\
                    .select('id')\
                    .eq('email', TEST_EMAIL)\
                    .execute()
                
                if assignments.data:
                    logger.info(f"   Найдено {len(assignments.data)} назначений")
                    api.client.table('user_break_assignments')\
                        .delete()\
                        .eq('email', TEST_EMAIL)\
                        .execute()
                    deleted_count += len(assignments.data)
                    logger.info(f"   ✅ Удалено {len(assignments.data)} назначений")
                else:
                    logger.info("   Нет назначений")
        except Exception as e:
            logger.warning(f"   ⚠️ Ошибка при удалении из user_break_assignments: {e}")
        
        # 5. Физически удаляем из Users (последним, чтобы не было проблем с внешними ключами)
        logger.info("5. Удаление из Users...")
        try:
            if hasattr(api, 'client') and hasattr(api.client, 'table'):
                # Проверяем, есть ли пользователь
                user_check = api.client.table('users')\
                    .select('id')\
                    .eq('email', TEST_EMAIL)\
                    .execute()
                
                if user_check.data:
                    logger.info(f"   Найден пользователь в Users")
                    # Физически удаляем (не помечаем как неактивного)
                    api.client.table('users')\
                        .delete()\
                        .eq('email', TEST_EMAIL)\
                        .execute()
                    deleted_count += 1
                    logger.info("   ✅ Пользователь физически удален из Users")
                else:
                    logger.info("   Пользователь не найден в Users (возможно, уже удален)")
        except Exception as e:
            logger.warning(f"   ⚠️ Ошибка при удалении из Users: {e}")
        
        # 6. Проверяем другие возможные таблицы
        logger.info("6. Проверка других таблиц...")
        other_tables = ['violations', 'notifications', 'audit_log']
        for table_name in other_tables:
            try:
                if hasattr(api, 'client') and hasattr(api.client, 'table'):
                    records = api.client.table(table_name)\
                        .select('id')\
                        .eq('email', TEST_EMAIL)\
                        .execute()
                    
                    if records.data:
                        logger.info(f"   Найдено {len(records.data)} записей в {table_name}")
                        api.client.table(table_name)\
                            .delete()\
                            .eq('email', TEST_EMAIL)\
                            .execute()
                        deleted_count += len(records.data)
                        logger.info(f"   ✅ Удалено {len(records.data)} записей из {table_name}")
            except Exception:
                continue
        
        logger.info(f"\n✅ Готово! Всего удалено записей: {deleted_count}")
        logger.info(f"Пользователь {TEST_EMAIL} и все связанные данные удалены.")
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
        return False
    
    return True


if __name__ == "__main__":
    print(f"\n{'='*60}")
    print(f"УДАЛЕНИЕ ТЕСТОВОГО ПОЛЬЗОВАТЕЛЯ: {TEST_EMAIL}")
    print(f"{'='*60}\n")
    
    confirm = input(f"Вы уверены, что хотите удалить {TEST_EMAIL}? (yes/no): ")
    if confirm.lower() != 'yes':
        print("Отменено.")
        sys.exit(0)
    
    success = delete_test_user()
    
    if success:
        print("\n✅ Операция завершена успешно!")
        sys.exit(0)
    else:
        print("\n❌ Произошли ошибки при удалении. Проверьте логи выше.")
        sys.exit(1)
