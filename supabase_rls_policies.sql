-- ============================================================================
-- Row Level Security (RLS) Policies для WorkTimeTracker
-- ============================================================================
-- Эти политики разрешают чтение/запись данных для приложений
-- без необходимости аутентификации пользователей
-- ============================================================================

-- ============================================================================
-- ВАРИАНТ 1: Отключить RLS (для разработки)
-- ============================================================================
-- ВНИМАНИЕ: Используйте только для разработки/тестирования!
-- В production лучше использовать политики (Вариант 2)

ALTER TABLE users DISABLE ROW LEVEL SECURITY;
ALTER TABLE work_sessions DISABLE ROW LEVEL SECURITY;
ALTER TABLE work_log DISABLE ROW LEVEL SECURITY;
ALTER TABLE break_log DISABLE ROW LEVEL SECURITY;

-- ============================================================================
-- ВАРИАНТ 2: Настроить RLS политики (рекомендуется для production)
-- ============================================================================
-- Раскомментируйте эти строки если хотите использовать RLS:

/*
-- Включаем RLS
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE work_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE work_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE break_log ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- Политики для таблицы users
-- ============================================================================

-- Разрешить чтение всех пользователей
CREATE POLICY "Allow public read access on users"
ON users FOR SELECT
TO public
USING (true);

-- Разрешить вставку и обновление для service role
CREATE POLICY "Allow service role full access on users"
ON users FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- ============================================================================
-- Политики для таблицы work_sessions
-- ============================================================================

-- Разрешить чтение всех сессий
CREATE POLICY "Allow public read access on work_sessions"
ON work_sessions FOR SELECT
TO public
USING (true);

-- Разрешить вставку и обновление для service role
CREATE POLICY "Allow service role full access on work_sessions"
ON work_sessions FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- Разрешить пользователям читать свои сессии
CREATE POLICY "Users can read their own sessions"
ON work_sessions FOR SELECT
TO public
USING (true);

-- Разрешить пользователям создавать свои сессии
CREATE POLICY "Users can insert their own sessions"
ON work_sessions FOR INSERT
TO public
WITH CHECK (true);

-- Разрешить пользователям обновлять свои сессии
CREATE POLICY "Users can update their own sessions"
ON work_sessions FOR UPDATE
TO public
USING (true)
WITH CHECK (true);

-- ============================================================================
-- Политики для таблицы work_log
-- ============================================================================

-- Разрешить чтение всех записей
CREATE POLICY "Allow public read access on work_log"
ON work_log FOR SELECT
TO public
USING (true);

-- Разрешить вставку для всех
CREATE POLICY "Allow public insert on work_log"
ON work_log FOR INSERT
TO public
WITH CHECK (true);

-- Разрешить service role полный доступ
CREATE POLICY "Allow service role full access on work_log"
ON work_log FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- ============================================================================
-- Политики для таблицы break_log
-- ============================================================================

-- Разрешить чтение всех перерывов
CREATE POLICY "Allow public read access on break_log"
ON break_log FOR SELECT
TO public
USING (true);

-- Разрешить вставку и обновление
CREATE POLICY "Allow public insert and update on break_log"
ON break_log FOR INSERT
TO public
WITH CHECK (true);

CREATE POLICY "Allow public update on break_log"
ON break_log FOR UPDATE
TO public
USING (true)
WITH CHECK (true);

-- Разрешить service role полный доступ
CREATE POLICY "Allow service role full access on break_log"
ON break_log FOR ALL
TO service_role
USING (true)
WITH CHECK (true);
*/

-- ============================================================================
-- ПРОВЕРКА
-- ============================================================================

-- Проверка статуса RLS для всех таблиц
SELECT
    schemaname,
    tablename,
    rowsecurity as rls_enabled
FROM pg_tables
WHERE schemaname = 'public'
AND tablename IN ('users', 'work_sessions', 'work_log', 'break_log')
ORDER BY tablename;

-- Проверка существующих политик
SELECT
    schemaname,
    tablename,
    policyname,
    permissive,
    roles,
    cmd,
    qual,
    with_check
FROM pg_policies
WHERE schemaname = 'public'
AND tablename IN ('users', 'work_sessions', 'work_log', 'break_log')
ORDER BY tablename, policyname;
