-- ============================================================================
-- Migration 001: Initial Schema
-- Description: Создание основных таблиц (logs, sessions) с индексами и триггерами
-- Author: WorkTimeTracker DB Team
-- Date: 2025-11-24
-- ============================================================================

-- Таблица для логов действий пользователей
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    email TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT,
    action_type TEXT NOT NULL,
    comment TEXT,
    timestamp TEXT NOT NULL,
    synced INTEGER DEFAULT 0,
    sync_attempts INTEGER DEFAULT 0,
    last_sync_attempt TEXT,
    priority INTEGER DEFAULT 1,
    status_start_time TEXT,
    status_end_time TEXT,
    reason TEXT,
    user_group TEXT
);

-- Таблица для сессий
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    session_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    login_time TEXT NOT NULL,
    logout_time TEXT
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Основные индексы для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_logs_email ON logs(email);
CREATE INDEX IF NOT EXISTS idx_logs_session ON logs(session_id);
CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_logs_synced ON logs(synced);
CREATE INDEX IF NOT EXISTS idx_logs_action_type ON logs(action_type);

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Триггер: проверка длины комментария
CREATE TRIGGER IF NOT EXISTS check_comment_length
BEFORE INSERT ON logs
FOR EACH ROW
WHEN length(NEW.comment) > 500
BEGIN
    SELECT RAISE(ABORT, 'Comment too long');
END;

-- Триггер: предотвращение дублирования LOGOUT
CREATE TRIGGER IF NOT EXISTS prevent_duplicate_logout
BEFORE INSERT ON logs
FOR EACH ROW
WHEN LOWER(NEW.action_type) = 'logout' AND EXISTS (
    SELECT 1 FROM logs
    WHERE session_id = NEW.session_id
    AND LOWER(action_type) = 'logout'
)
BEGIN
    SELECT RAISE(ABORT, 'Duplicate LOGOUT action');
END;

-- ============================================================================
-- NOTES
-- ============================================================================
-- Эта миграция создает базовую структуру БД:
-- - logs: хранит все действия пользователей
-- - sessions: хранит информацию о сессиях
-- - Индексы оптимизированы для частых запросов
-- - Триггеры обеспечивают целостность данных
-- ============================================================================
