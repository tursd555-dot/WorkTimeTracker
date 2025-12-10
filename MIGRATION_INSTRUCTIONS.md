# Инструкция по миграции БД Supabase

## ⚠️ ВАЖНО: Требуется выполнить миграцию базы данных!

Код был обновлен для работы с правильной нормализованной структурой БД в Supabase.
Для корректной работы создания графиков перерывов необходимо добавить таблицу `break_windows`.

## Шаг 1: Выполнить миграцию в Supabase

Перейдите в ваш проект Supabase:
1. Откройте **SQL Editor** в боковом меню
2. Создайте новый запрос
3. Скопируйте и вставьте содержимое файла:

```
migrations/006_add_break_windows.sql
```

4. Нажмите **Run** для выполнения миграции

### Что делает эта миграция:
- Создает таблицу `break_windows` для хранения временных окон перерывов
- Добавляет индексы для оптимизации запросов
- Создает триггер для автоматического обновления `updated_at`

## Шаг 2: Обновить код

```bash
git pull origin claude/fix-startup-admin-display-01ANkkLfp45JoFdtXxuwpbgp
```

## Шаг 3: Проверить работу

После выполнения миграции:

1. Запустите админ-панель:
```bash
python admin_app/main_admin.py
```

2. Перейдите на вкладку "Перерывы"

3. Нажмите "Создать шаблон" и заполните форму:
   - ID шаблона (можно сгенерировать автоматически)
   - Название графика
   - Время начала и конца смены
   - Добавьте слоты перерывов (тип, длительность, окно времени)

4. Нажмите "Сохранить"

### Ожидаемый результат:
✅ Шаблон создается без ошибок
✅ Данные сохраняются в 3 таблицы: `break_schedules`, `break_limits`, `break_windows`
✅ В логах появляется: "Created schedule '{name}' (ID: {uuid}) with X limits and Y windows"

## Что было исправлено:

### Проблема 1: Неправильная структура БД
**Было:** Код пытался вставить все данные в одну таблицу `break_schedules` с колонками `break_type`, `time_minutes`, и т.д.

**Стало:** Используется правильная нормализованная структура:
- `break_schedules` - основная информация о графике (id, name, shift_start, shift_end)
- `break_limits` - лимиты по типам перерывов (schedule_id, break_type, duration_minutes, daily_count)
- `break_windows` - временные окна для перерывов (schedule_id, break_type, window_start, window_end, priority)

### Проблема 2: Ошибка с таблицей Violations
**Было:** Код искал таблицу `Violations` (с большой буквы)

**Стало:** Добавлен маппинг `'Violations' -> 'violations'` для совместимости

### Проблема 3: Несовместимость с Google Sheets API
**Было:** Метод `get_worksheet()` возвращал строку, а код вызывал `.append_row()`

**Стало:** Создан класс `WorksheetWrapper` который эмулирует поведение Google Sheets worksheet

## Структура базы данных (для справки)

```sql
-- Основная информация о графике
break_schedules (
    id UUID,
    name VARCHAR,
    description TEXT,
    shift_start TIME,
    shift_end TIME,
    is_active BOOLEAN,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
)

-- Лимиты перерывов
break_limits (
    id UUID,
    schedule_id UUID -> break_schedules(id),
    break_type VARCHAR,       -- "Перерыв", "Обед"
    duration_minutes INTEGER,
    daily_count INTEGER,
    created_at TIMESTAMPTZ
)

-- Временные окна (когда можно брать перерыв)
break_windows (
    id UUID,
    schedule_id UUID -> break_schedules(id),
    break_type VARCHAR,
    window_start TIME,
    window_end TIME,
    priority INTEGER,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
)
```

## Проверка миграции

Выполните следующий SQL запрос в Supabase SQL Editor для проверки:

```sql
-- Проверяем что таблица создана
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_name = 'break_windows'
ORDER BY ordinal_position;

-- Должно вернуть 8 строк с колонками:
-- id, schedule_id, break_type, window_start, window_end, priority, created_at, updated_at
```

## Возможные проблемы и решения

### Ошибка: "relation 'break_windows' does not exist"
**Решение:** Выполните миграцию 006_add_break_windows.sql в Supabase SQL Editor

### Ошибка: "column 'break_type' does not exist in break_schedules"
**Решение:** Убедитесь что вы обновили код (`git pull`), новый код не использует эту колонку

### Графики не отображаются в админ-панели
**Решение:** Проверьте что в таблицах `break_schedules`, `break_limits`, `break_windows` есть данные:
```sql
SELECT s.name, COUNT(DISTINCT l.id) as limits_count, COUNT(DISTINCT w.id) as windows_count
FROM break_schedules s
LEFT JOIN break_limits l ON l.schedule_id = s.id
LEFT JOIN break_windows w ON w.schedule_id = s.id
WHERE s.is_active = true
GROUP BY s.id, s.name;
```

## Контакты

Если у вас возникли проблемы с миграцией, проверьте логи приложения или обратитесь за помощью.
