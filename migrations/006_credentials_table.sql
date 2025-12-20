-- Миграция для создания таблицы credentials в Supabase
-- Позволяет хранить credentials JSON напрямую в базе данных

CREATE TABLE IF NOT EXISTS credentials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    credentials_json TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- RLS политики (только для авторизованных пользователей)
ALTER TABLE credentials ENABLE ROW LEVEL SECURITY;

-- Политика: только авторизованные пользователи могут читать
CREATE POLICY "Users can read credentials"
    ON credentials FOR SELECT
    USING (auth.role() = 'authenticated');

-- Политика: только авторизованные пользователи могут обновлять
CREATE POLICY "Users can update credentials"
    ON credentials FOR UPDATE
    USING (auth.role() = 'authenticated');

-- Политика: только авторизованные пользователи могут вставлять
CREATE POLICY "Users can insert credentials"
    ON credentials FOR INSERT
    WITH CHECK (auth.role() = 'authenticated');

-- Триггер для обновления updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_credentials_updated_at
    BEFORE UPDATE ON credentials
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Комментарии
COMMENT ON TABLE credentials IS 'Хранилище credentials для WorkTimeTracker';
COMMENT ON COLUMN credentials.credentials_json IS 'JSON строка с service_account credentials';
