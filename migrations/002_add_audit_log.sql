-- ============================================================================
-- Migration 002: Audit Log Table
-- Description: Добавление таблицы для аудита действий администратора
-- Author: WorkTimeTracker DB Team
-- Date: 2025-11-24
-- ============================================================================

-- Таблица для audit логов (действия администратора)
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    admin_email TEXT NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT,
    before_state TEXT,          -- JSON: состояние до изменения
    after_state TEXT,            -- JSON: состояние после изменения
    ip_address TEXT,
    hostname TEXT,
    success INTEGER DEFAULT 1,  -- 1 = успех, 0 = ошибка
    error_message TEXT
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Индекс по timestamp для сортировки
CREATE INDEX IF NOT EXISTS idx_audit_timestamp 
ON audit_log(timestamp);

-- Индекс по администратору и времени
CREATE INDEX IF NOT EXISTS idx_audit_admin 
ON audit_log(admin_email, timestamp);

-- Индекс по сущности для получения истории
CREATE INDEX IF NOT EXISTS idx_audit_entity 
ON audit_log(entity_type, entity_id, timestamp);

-- Индекс по типу действия
CREATE INDEX IF NOT EXISTS idx_audit_action 
ON audit_log(action, timestamp);

-- ============================================================================
-- NOTES
-- ============================================================================
-- Эта миграция добавляет систему аудита:
-- - Все действия администратора логируются
-- - Сохраняется состояние до и после изменений
-- - Фиксируется IP адрес и hostname для безопасности
-- - Индексы оптимизированы для поиска и фильтрации
-- 
-- Использование:
-- - Отслеживание всех изменений данных
-- - Расследование инцидентов
-- - Compliance и регуляторные требования
-- ============================================================================
