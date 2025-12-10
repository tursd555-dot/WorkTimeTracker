-- ============================================================================
-- Migration: Add break_windows table
-- Date: 2025-12-10
-- Description: Добавляет таблицу для хранения временных окон перерывов
-- ============================================================================

-- ТАБЛИЦА: break_windows
-- Временные окна для перерывов (когда можно брать перерыв)
CREATE TABLE IF NOT EXISTS break_windows (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    schedule_id UUID REFERENCES break_schedules(id) ON DELETE CASCADE,
    break_type VARCHAR(50) NOT NULL, -- Перерыв, Обед
    window_start TIME NOT NULL,
    window_end TIME NOT NULL,
    priority INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_windows_schedule ON break_windows(schedule_id);
CREATE INDEX idx_windows_type ON break_windows(break_type);
CREATE INDEX idx_windows_priority ON break_windows(priority);

-- Триггер для updated_at
CREATE TRIGGER update_windows_updated_at BEFORE UPDATE ON break_windows
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

COMMENT ON TABLE break_windows IS 'Временные окна для перерывов (когда можно брать перерыв)';
