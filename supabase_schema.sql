-- ============================================================================
-- WorkTimeTracker Database Schema для Supabase (PostgreSQL)
-- Версия: 1.0
-- Дата: 09.12.2025
-- ============================================================================

-- Включаем расширения
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm"; -- Для полнотекстового поиска

-- ============================================================================
-- ТАБЛИЦА: users
-- Пользователи системы
-- ============================================================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    role VARCHAR(100),
    telegram_id VARCHAR(100),
    group_name VARCHAR(100),
    notify_telegram BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Индексы для быстрого поиска
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_group ON users(group_name);
CREATE INDEX idx_users_telegram ON users(telegram_id);
CREATE INDEX idx_users_name_trgm ON users USING gin(name gin_trgm_ops); -- Полнотекстовый поиск

-- ============================================================================
-- ТАБЛИЦА: groups
-- Группы пользователей
-- ============================================================================
CREATE TABLE groups (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_groups_name ON groups(name);

-- ============================================================================
-- ТАБЛИЦА: work_sessions
-- Рабочие сессии (логин/логаут)
-- ============================================================================
CREATE TABLE work_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(100) UNIQUE NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    login_time TIMESTAMPTZ NOT NULL,
    logout_time TIMESTAMPTZ,
    duration_minutes INTEGER,
    status VARCHAR(50) DEFAULT 'active', -- active, completed, forced_logout
    logout_type VARCHAR(50), -- manual, auto, forced
    comment TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_sessions_user ON work_sessions(user_id);
CREATE INDEX idx_sessions_email ON work_sessions(email);
CREATE INDEX idx_sessions_session_id ON work_sessions(session_id);
CREATE INDEX idx_sessions_status ON work_sessions(status);
CREATE INDEX idx_sessions_login_time ON work_sessions(login_time DESC);

-- ============================================================================
-- ТАБЛИЦА: work_log
-- Детальный лог всех действий
-- ============================================================================
CREATE TABLE work_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    timestamp TIMESTAMPTZ NOT NULL,
    action_type VARCHAR(100) NOT NULL, -- LOGIN, LOGOUT, STATUS_CHANGE, etc.
    status VARCHAR(100),
    details TEXT,
    session_id VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_worklog_user ON work_log(user_id);
CREATE INDEX idx_worklog_email ON work_log(email);
CREATE INDEX idx_worklog_timestamp ON work_log(timestamp DESC);
CREATE INDEX idx_worklog_action ON work_log(action_type);
CREATE INDEX idx_worklog_session ON work_log(session_id);

-- ============================================================================
-- ТАБЛИЦА: break_schedules
-- Графики перерывов
-- ============================================================================
CREATE TABLE break_schedules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    shift_start TIME,
    shift_end TIME,
    is_active BOOLEAN DEFAULT true,
    created_by VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_schedules_name ON break_schedules(name);
CREATE INDEX idx_schedules_active ON break_schedules(is_active);

-- ============================================================================
-- ТАБЛИЦА: break_limits
-- Лимиты перерывов для графиков
-- ============================================================================
CREATE TABLE break_limits (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    schedule_id UUID REFERENCES break_schedules(id) ON DELETE CASCADE,
    break_type VARCHAR(50) NOT NULL, -- Перерыв, Обед
    duration_minutes INTEGER NOT NULL,
    daily_count INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_limits_schedule ON break_limits(schedule_id);
CREATE INDEX idx_limits_type ON break_limits(break_type);

-- ============================================================================
-- ТАБЛИЦА: user_break_assignments
-- Назначение графиков пользователям
-- ============================================================================
CREATE TABLE user_break_assignments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    schedule_id UUID REFERENCES break_schedules(id) ON DELETE CASCADE,
    assigned_date TIMESTAMPTZ DEFAULT NOW(),
    assigned_by VARCHAR(255),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_assignments_user ON user_break_assignments(user_id);
CREATE INDEX idx_assignments_email ON user_break_assignments(email);
CREATE INDEX idx_assignments_schedule ON user_break_assignments(schedule_id);

-- ============================================================================
-- ТАБЛИЦА: break_log
-- Лог перерывов
-- ============================================================================
CREATE TABLE break_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    break_type VARCHAR(50) NOT NULL, -- Перерыв, Обед
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ,
    duration_minutes INTEGER,
    date DATE NOT NULL,
    status VARCHAR(50) DEFAULT 'Active', -- Active, Completed
    is_over_limit BOOLEAN DEFAULT false,
    session_id VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_breaklog_user ON break_log(user_id);
CREATE INDEX idx_breaklog_email ON break_log(email);
CREATE INDEX idx_breaklog_date ON break_log(date DESC);
CREATE INDEX idx_breaklog_status ON break_log(status);
CREATE INDEX idx_breaklog_start ON break_log(start_time DESC);
CREATE INDEX idx_breaklog_type ON break_log(break_type);

-- ============================================================================
-- ТАБЛИЦА: violations
-- Нарушения (превышение лимитов перерывов и т.д.)
-- ============================================================================
CREATE TABLE violations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    violation_type VARCHAR(100) NOT NULL, -- break_overtime, unauthorized_break, etc.
    break_type VARCHAR(50),
    timestamp TIMESTAMPTZ NOT NULL,
    expected_duration INTEGER,
    actual_duration INTEGER,
    excess_minutes INTEGER,
    date DATE NOT NULL,
    details TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_violations_user ON violations(user_id);
CREATE INDEX idx_violations_email ON violations(email);
CREATE INDEX idx_violations_date ON violations(date DESC);
CREATE INDEX idx_violations_type ON violations(violation_type);

-- ============================================================================
-- ТАБЛИЦА: sync_log
-- Лог синхронизации с Google Sheets
-- ============================================================================
CREATE TABLE sync_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sync_type VARCHAR(50) NOT NULL, -- export_to_sheets, import_from_sheets
    table_name VARCHAR(100) NOT NULL,
    records_processed INTEGER DEFAULT 0,
    records_success INTEGER DEFAULT 0,
    records_failed INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'running', -- running, completed, failed
    error_message TEXT,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_seconds INTEGER
);

CREATE INDEX idx_synclog_type ON sync_log(sync_type);
CREATE INDEX idx_synclog_table ON sync_log(table_name);
CREATE INDEX idx_synclog_started ON sync_log(started_at DESC);

-- ============================================================================
-- ФУНКЦИИ И ТРИГГЕРЫ
-- ============================================================================

-- Функция обновления updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Триггеры для updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_groups_updated_at BEFORE UPDATE ON groups
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_sessions_updated_at BEFORE UPDATE ON work_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_schedules_updated_at BEFORE UPDATE ON break_schedules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_breaklog_updated_at BEFORE UPDATE ON break_log
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Функция автоматического расчета duration при завершении сессии
CREATE OR REPLACE FUNCTION calculate_session_duration()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.logout_time IS NOT NULL AND OLD.logout_time IS NULL THEN
        NEW.duration_minutes = EXTRACT(EPOCH FROM (NEW.logout_time - NEW.login_time)) / 60;
        NEW.status = 'completed';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER calc_session_duration BEFORE UPDATE ON work_sessions
    FOR EACH ROW EXECUTE FUNCTION calculate_session_duration();

-- Функция автоматического расчета duration при завершении перерыва
CREATE OR REPLACE FUNCTION calculate_break_duration()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.end_time IS NOT NULL AND OLD.end_time IS NULL THEN
        NEW.duration_minutes = EXTRACT(EPOCH FROM (NEW.end_time - NEW.start_time)) / 60;
        NEW.status = 'Completed';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER calc_break_duration BEFORE UPDATE ON break_log
    FOR EACH ROW EXECUTE FUNCTION calculate_break_duration();

-- ============================================================================
-- ПРЕДСТАВЛЕНИЯ (VIEWS)
-- ============================================================================

-- Активные сессии
CREATE VIEW active_sessions AS
SELECT 
    s.id,
    s.session_id,
    s.email,
    u.name,
    u.group_name,
    s.login_time,
    EXTRACT(EPOCH FROM (NOW() - s.login_time)) / 60 AS duration_minutes,
    s.status
FROM work_sessions s
LEFT JOIN users u ON s.user_id = u.id
WHERE s.status = 'active'
ORDER BY s.login_time DESC;

-- Активные перерывы
CREATE VIEW active_breaks AS
SELECT 
    b.id,
    b.email,
    b.name,
    b.break_type,
    b.start_time,
    EXTRACT(EPOCH FROM (NOW() - b.start_time)) / 60 AS duration_minutes,
    b.is_over_limit
FROM break_log b
WHERE b.status = 'Active'
ORDER BY b.start_time DESC;

-- Статистика пользователей за сегодня
CREATE VIEW daily_user_stats AS
SELECT 
    u.email,
    u.name,
    COUNT(DISTINCT s.id) FILTER (WHERE s.login_time::date = CURRENT_DATE) AS sessions_today,
    SUM(s.duration_minutes) FILTER (WHERE s.login_time::date = CURRENT_DATE) AS work_minutes_today,
    COUNT(DISTINCT b.id) FILTER (WHERE b.date = CURRENT_DATE) AS breaks_today,
    SUM(b.duration_minutes) FILTER (WHERE b.date = CURRENT_DATE) AS break_minutes_today,
    COUNT(DISTINCT v.id) FILTER (WHERE v.date = CURRENT_DATE) AS violations_today
FROM users u
LEFT JOIN work_sessions s ON u.id = s.user_id
LEFT JOIN break_log b ON u.id = b.user_id
LEFT JOIN violations v ON u.id = v.user_id
WHERE u.is_active = true
GROUP BY u.email, u.name
ORDER BY u.name;

-- ============================================================================
-- ROW LEVEL SECURITY (RLS)
-- Включаем для безопасности
-- ============================================================================

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE work_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE work_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE break_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE violations ENABLE ROW LEVEL SECURITY;

-- Политики доступа (пример - нужно настроить под ваши роли)
-- Все пользователи могут читать свои данные
CREATE POLICY "Users can view own data" ON users
    FOR SELECT USING (email = current_user);

-- Админы могут всё
CREATE POLICY "Admins can do everything" ON users
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM users 
            WHERE email = current_user 
            AND role = 'admin'
        )
    );

-- ============================================================================
-- НАЧАЛЬНЫЕ ДАННЫЕ (опционально)
-- ============================================================================

-- Создаем дефолтный график перерывов
INSERT INTO break_schedules (name, description, is_active) 
VALUES ('Default Schedule', 'Дефолтный график: 3 перерыва по 15 мин, 1 обед 60 мин', true)
ON CONFLICT DO NOTHING;

-- Дефолтные лимиты
INSERT INTO break_limits (schedule_id, break_type, duration_minutes, daily_count)
SELECT id, 'Перерыв', 15, 3 FROM break_schedules WHERE name = 'Default Schedule'
ON CONFLICT DO NOTHING;

INSERT INTO break_limits (schedule_id, break_type, duration_minutes, daily_count)
SELECT id, 'Обед', 60, 1 FROM break_schedules WHERE name = 'Default Schedule'
ON CONFLICT DO NOTHING;

-- ============================================================================
-- КОММЕНТАРИИ К ТАБЛИЦАМ
-- ============================================================================

COMMENT ON TABLE users IS 'Пользователи системы WorkTimeTracker';
COMMENT ON TABLE work_sessions IS 'Рабочие сессии (логин/логаут)';
COMMENT ON TABLE work_log IS 'Детальный лог всех действий';
COMMENT ON TABLE break_schedules IS 'Графики перерывов';
COMMENT ON TABLE break_limits IS 'Лимиты перерывов для графиков';
COMMENT ON TABLE user_break_assignments IS 'Назначение графиков пользователям';
COMMENT ON TABLE break_log IS 'Лог перерывов';
COMMENT ON TABLE violations IS 'Нарушения (превышение лимитов и т.д.)';
COMMENT ON TABLE sync_log IS 'Лог синхронизации с Google Sheets';

-- ============================================================================
-- ГОТОВО!
-- ============================================================================
