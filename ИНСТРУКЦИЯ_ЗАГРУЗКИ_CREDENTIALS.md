# Пошаговая инструкция: Загрузка Credentials в Supabase

## Шаг 1: Подготовка файла credentials

1. Убедитесь, что у вас есть файл `service_account.json` от Google Cloud
2. Проверьте, что файл содержит все необходимые поля:
   - `type`: должен быть `"service_account"`
   - `project_id`
   - `private_key_id`
   - `private_key`
   - `client_email`

## Шаг 2: Создание таблицы в Supabase

### Вариант А: Через Supabase Dashboard (рекомендуется)

1. Откройте ваш проект в Supabase: https://supabase.com/dashboard
2. Перейдите в раздел **SQL Editor**
3. Создайте новый запрос
4. Скопируйте и выполните следующий SQL:

```sql
-- Создание таблицы credentials
CREATE TABLE IF NOT EXISTS credentials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    credentials_json TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Включение RLS (Row Level Security)
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
```

5. Нажмите **Run** для выполнения запроса
6. Убедитесь, что таблица создана (проверьте в разделе **Table Editor**)

### Вариант Б: Через файл миграции

Если у вас есть доступ к файлу миграции:

1. Откройте файл `migrations/006_credentials_table.sql`
2. Скопируйте его содержимое
3. Выполните в Supabase SQL Editor

## Шаг 3: Настройка переменных окружения

Убедитесь, что в вашем `.env` файле указаны:

```env
SUPABASE_URL=https://jtgaobxbwibjcvasefzi.supabase.co
SUPABASE_KEY=ваш_ключ_из_supabase
```

Или они уже должны быть в `config.py` (проверьте файл).

## Шаг 4: Загрузка credentials через скрипт

### Способ 1: Указать путь к файлу

```bash
python tools/upload_credentials_to_supabase.py service_account.json
```

### Способ 2: Интерактивный режим

```bash
python tools/upload_credentials_to_supabase.py
```

Скрипт попросит указать путь к файлу или найдет его автоматически в текущей папке.

## Шаг 5: Проверка загрузки

### Через Supabase Dashboard:

1. Откройте Supabase Dashboard
2. Перейдите в **Table Editor**
3. Выберите таблицу `credentials`
4. Должна быть одна запись с вашими credentials

### Через скрипт проверки:

Создайте временный скрипт для проверки:

```python
from shared.credentials_storage import get_credentials_json_from_supabase
import json

creds_json = get_credentials_json_from_supabase()
if creds_json:
    creds = json.loads(creds_json)
    print("✅ Credentials загружены из Supabase")
    print(f"Project ID: {creds.get('project_id')}")
    print(f"Client Email: {creds.get('client_email')}")
else:
    print("❌ Credentials не найдены в Supabase")
```

## Шаг 6: Удаление локальных файлов (опционально)

После успешной загрузки в Supabase можно удалить локальные файлы:

```bash
# Удалить ZIP архив (если был)
del secret_creds.zip

# Удалить JSON файл (после проверки что все работает)
del service_account.json

# Удалить пароль из .env (если был)
# Откройте .env и удалите строку CREDENTIALS_ZIP_PASSWORD=...
```

## Шаг 7: Проверка работы приложения

1. Запустите приложение:
   ```bash
   python user_app/main.py
   ```

2. Приложение должно автоматически загрузить credentials из Supabase
3. В логах должно быть сообщение: `✓ Credentials будут загружены из Supabase`

## Устранение проблем

### Ошибка: "Table credentials does not exist"

**Решение:** Выполните SQL миграцию из Шага 2

### Ошибка: "Credentials не найдены в Supabase"

**Проверьте:**
1. Таблица `credentials` создана?
2. Есть ли записи в таблице? (через Supabase Dashboard)
3. Правильно ли указаны `SUPABASE_URL` и `SUPABASE_KEY`?

### Ошибка: "Permission denied" или "RLS policy violation"

**Решение:** 
- Убедитесь, что RLS политики созданы правильно
- Или временно отключите RLS для тестирования:
  ```sql
  ALTER TABLE credentials DISABLE ROW LEVEL SECURITY;
  ```

### Ошибка при загрузке через скрипт

**Проверьте:**
1. Установлены ли зависимости: `pip install -r requirements.txt`
2. Доступен ли Supabase API: проверьте `SUPABASE_URL` и `SUPABASE_KEY`
3. Валидность JSON файла: откройте `service_account.json` и проверьте формат

## Альтернативный способ: Загрузка через Supabase Dashboard

Если скрипт не работает, можно загрузить вручную:

1. Откройте Supabase Dashboard → Table Editor → credentials
2. Нажмите **Insert row**
3. В поле `credentials_json` вставьте содержимое вашего `service_account.json`
4. Нажмите **Save**

## Безопасность

⚠️ **Важно:**
- Credentials содержат секретные ключи
- Храните их только в защищенной базе данных
- Не коммитьте credentials в git
- Используйте RLS политики для ограничения доступа
- Регулярно ротируйте ключи

## Готово!

После выполнения всех шагов ваше приложение будет автоматически загружать credentials из Supabase, и вам не нужно будет хранить файлы локально.
