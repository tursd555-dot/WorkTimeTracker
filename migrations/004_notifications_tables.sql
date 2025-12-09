-- ============================================================================
-- Migration 004: Notifications Tables
-- Description: Таблицы для системы уведомлений и логирования приложения
-- Author: WorkTimeTracker DB Team
-- Date: 2025-11-24
-- ============================================================================

-- ============================================================================
-- ТАБЛИЦА ДЛЯ ОТСЛЕЖИВАНИЯ УВЕДОМЛЕНИЙ
-- ============================================================================

-- Таблица для отслеживания последних отправленных уведомлений
-- Используется для предотвращения спама (cooldown между уведомлениями)
CREATE TABLE IF NOT EXISTS rule_last_sent (
    rule_id TEXT PRIMARY KEY,           -- ID правила уведомления
    user_email TEXT NOT NULL,           -- Email пользователя
    last_sent_timestamp TEXT NOT NULL   -- Время последней отправки
);

-- Индекс для быстрого поиска по пользователю
CREATE INDEX IF NOT EXISTS idx_rule_last_sent_user 
ON rule_last_sent(user_email);

-- ============================================================================
-- ТАБЛИЦА ДЛЯ ЛОГОВ ПРИЛОЖЕНИЯ
-- ============================================================================

-- Таблица для хранения application logs
-- Используется для debugging и мониторинга
CREATE TABLE IF NOT EXISTS app_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,          -- Timestamp
    level TEXT NOT NULL,       -- DEBUG, INFO, WARNING, ERROR, CRITICAL
    message TEXT NOT NULL      -- Сообщение лога
);

-- Индекс по timestamp для сортировки и фильтрации
CREATE INDEX IF NOT EXISTS idx_app_logs_ts 
ON app_logs(ts);

-- ============================================================================
-- NOTES
-- ============================================================================
-- Эта миграция добавляет поддержку уведомлений:
--
-- 1. rule_last_sent таблица:
--    - Отслеживает когда последний раз отправлялось уведомление
--    - Предотвращает спам (например, не чаще 1 раза в 5 минут)
--    - Используется notifications engine
--
--    Пример использования:
--    ```python
--    # Проверить, можно ли отправить уведомление
--    last_sent = get_last_sent(rule_id, user_email)
--    if not last_sent or (now() - last_sent) > cooldown:
--        send_notification()
--        update_last_sent(rule_id, user_email, now())
--    ```
--
-- 2. app_logs таблица:
--    - Хранит application logs в БД
--    - Полезно для debugging в production
--    - Можно анализировать логи SQL запросами
--
--    Пример использования:
--    ```python
--    # Логирование в БД
--    log_to_db("ERROR", "Sync failed: connection timeout")
--    
--    # Поиск ошибок за последний час
--    SELECT * FROM app_logs 
--    WHERE level = 'ERROR' 
--    AND ts > datetime('now', '-1 hour')
--    ORDER BY ts DESC;
--    ```
--
-- Features:
-- - Cooldown для предотвращения спама уведомлениями
-- - Централизованное логирование в БД
-- - Легкий поиск и анализ логов через SQL
-- ============================================================================
