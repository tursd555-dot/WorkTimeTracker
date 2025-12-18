# Быстрый старт: Архивация данных

## Проблема
Ошибка при запуске: `GOOGLE_ARCHIVE_SHEET_ID or GOOGLE_SHEET_ID must be set`

## Решение

### Шаг 1: Проверьте .env файл

Убедитесь, что в файле `.env` есть одна из переменных:

```env
# Основная переменная (должна быть уже настроена)
SPREADSHEET_ID=your_google_sheet_id_here

# Или альтернативные варианты:
# GOOGLE_SHEET_ID=your_google_sheet_id_here
# GOOGLE_ARCHIVE_SHEET_ID=your_archive_sheet_id_here
```

### Шаг 2: Где найти ID таблицы?

ID таблицы находится в URL Google Sheets:
```
https://docs.google.com/spreadsheets/d/YOUR_ID_HERE/edit
                                    ^^^^^^^^^^^^^^^^
                                    Это и есть ID
```

### Шаг 3: Запустите архивацию

**Windows:**
```powershell
python run_archive.py
```

**Linux/Mac:**
```bash
python3 run_archive.py
```

## Проверка настроек

Перед запуском убедитесь, что в `.env` есть:

```env
# Supabase (обязательно)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key

# Google Sheets (обязательно - хотя бы одна)
SPREADSHEET_ID=your_sheet_id

# Архивация (опционально)
ARCHIVE_AGE_DAYS=90
ARCHIVE_DELETE_AFTER=1
```

## Если ошибка все еще возникает

1. Убедитесь, что файл `.env` находится в корне проекта (там же где `run_archive.py`)
2. Проверьте, что переменные записаны без пробелов:
   ```env
   # Правильно
   SPREADSHEET_ID=abc123
   
   # Неправильно
   SPREADSHEET_ID = abc123
   ```
3. Перезапустите терминал после изменения `.env`
4. Проверьте, что `python-dotenv` установлен:
   ```powershell
   pip install python-dotenv
   ```

## Пример .env файла

```env
# Google Sheets
SPREADSHEET_ID=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms

# Supabase
SUPABASE_URL=https://xxxxxx.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Архивация
ARCHIVE_AGE_DAYS=90
ARCHIVE_DELETE_AFTER=1
```
