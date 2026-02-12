# Диагностика ошибок в пользовательском приложении

## Шаг 1: Запустите приложение и скопируйте полный текст ошибки

```powershell
python user_app/main.py
```

**Важно:** Скопируйте весь текст ошибки, включая:
- Traceback (полный стек вызовов)
- Название ошибки (AttributeError, TypeError, KeyError и т.д.)
- Номер строки, где произошла ошибка
- Название метода/атрибута, который отсутствует

## Шаг 2: Проверьте, какие методы используются

Выполните проверку наличия методов в SupabaseAPI:

```powershell
# Проверить основные методы
Select-String -Path supabase_api.py -Pattern "def set_active_session"
Select-String -Path supabase_api.py -Pattern "def finish_active_session"
Select-String -Path supabase_api.py -Pattern "def check_user_session_status"
Select-String -Path supabase_api.py -Pattern "def log_user_actions"
Select-String -Path supabase_api.py -Pattern "def get_all_active_sessions"
Select-String -Path supabase_api.py -Pattern "def get_user_by_email"
```

Все эти команды должны найти определения методов.

## Шаг 3: Проверьте синтаксис файла

```powershell
python -m py_compile supabase_api.py
```

Если есть ошибки синтаксиса - исправьте их.

## Шаг 4: Проверьте импорты

Убедитесь, что используется правильный API:

```powershell
# Проверить, какой бэкенд используется
Select-String -Path config.py -Pattern "USE_SUPABASE|USE_BACKEND"
```

## Частые ошибки и решения

### Ошибка: AttributeError: 'SupabaseAPI' object has no attribute 'XXX'

**Решение:** Добавить недостающий метод в `supabase_api.py`

### Ошибка: TypeError: XXX() missing required positional argument

**Решение:** Проверить сигнатуру метода и исправить вызов

### Ошибка: KeyError или ошибка доступа к данным

**Решение:** Проверить структуру данных в Supabase таблицах

## Отправьте информацию

После выполнения диагностики отправьте:
1. Полный текст ошибки
2. Результаты проверки методов (шаг 2)
3. Результат проверки синтаксиса (шаг 3)
4. Какой бэкенд используется (Supabase или Sheets)
