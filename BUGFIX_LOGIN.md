# 🐛 Исправление ошибки входа в систему

## ❌ Ошибка
```
Ошибка подключения: SupabaseAPI object has no attribute get_user_by_email
```

## ✅ Исправлено

Проблема была в том, что класс `SupabaseAPI` не содержал все методы, необходимые для совместимости с интерфейсом `SheetsAPI`.

### Добавленные методы:

1. **`get_user_by_email(email)`** - поиск пользователя по email для аутентификации
2. **`set_active_session(email, name, session_id, login_time)`** - создание активной сессии при входе
3. **`check_user_session_status(email, session_id)`** - проверка статуса сессии (active/kicked/finished)
4. **`finish_active_session(email, session_id)`** - завершение сессии при выходе
5. **`log_user_actions(actions, email, user_group)`** - batch-запись действий пользователя в лог

Все методы совместимы с `sheets_api.py` интерфейсом, что позволяет легко переключаться между Google Sheets и Supabase.

---

## 🚀 Как применить исправление

### 1. Получите обновления

```powershell
cd "D:\proj vs code\WorkTimeTracker"
git pull origin claude/analyze-project-repo-014htDps2c1UeCDCCYHN7UqC
```

### 2. Проверьте что изменения применились

```powershell
python -c "from supabase_api import SupabaseAPI; api = SupabaseAPI(); print('✓ Метод существует:', hasattr(api, 'get_user_by_email'))"
```

**Должно вывести:**
```
✓ Метод существует: True
```

### 3. Запустите приложение

```powershell
python user_app/main.py
```

---

## 🔍 Что было сделано

### Файл: `supabase_api.py`

#### 1. Метод `get_user_by_email`

```python
def get_user_by_email(self, email: str) -> Optional[Dict[str, str]]:
    """
    Получить пользователя по email
    Возвращает словарь с данными пользователя или None если не найден
    """
    # Запрос в таблицу users
    response = self.client.table('users')\
        .select('*')\
        .eq('email', email)\
        .eq('is_active', True)\
        .limit(1)\
        .execute()

    # Преобразование в совместимый формат
    return {
        "email": row.get('email'),
        "name": row.get('name'),
        "role": row.get('role', 'специалист'),
        "shift_hours": "8 часов",
        "telegram_login": row.get('telegram_id'),
        "group": row.get('group_name'),
    }
```

#### 2. Метод `set_active_session`

```python
def set_active_session(self, email: str, name: str, session_id: str, login_time: Optional[str] = None) -> bool:
    """
    Создать активную сессию при входе пользователя
    """
    data = {
        'session_id': session_id,
        'user_id': user_id,
        'email': email,
        'login_time': login_time or datetime.now(timezone.utc).isoformat(),
        'status': 'active'
    }

    self.client.table('work_sessions').insert(data).execute()
    return True
```

#### 3. Метод `check_user_session_status`

```python
def check_user_session_status(self, email: str, session_id: str) -> str:
    """
    Проверить статус сессии
    Возвращает: 'active', 'kicked', 'finished', 'unknown'
    """
    response = self.client.table('work_sessions')\
        .select('status')\
        .eq('email', email)\
        .eq('session_id', session_id)\
        .limit(1)\
        .execute()

    return response.data[0].get('status', 'unknown')
```

#### 4. Метод `finish_active_session`

```python
def finish_active_session(self, email: str, session_id: str) -> bool:
    """
    Завершить активную сессию при выходе
    """
    data = {
        'logout_time': datetime.now(timezone.utc).isoformat(),
        'status': 'finished'
    }

    self.client.table('work_sessions')\
        .update(data)\
        .eq('email', email)\
        .eq('session_id', session_id)\
        .execute()

    return True
```

#### 5. Метод `log_user_actions`

```python
def log_user_actions(self, actions: List[Dict[str, Any]], email: str, user_group: Optional[str] = None) -> bool:
    """
    Залогировать batch действий пользователя
    """
    records = []
    for action in actions:
        record = {
            'user_id': user_id,
            'email': email,
            'action_type': action.get('action_type'),
            'status': action.get('status'),
            'timestamp': action.get('timestamp'),
            'details': action.get('comment'),
            'session_id': action.get('session_id')
        }
        records.append(record)

    self.client.table('work_log').insert(records).execute()
    return True
```

---

## ✅ Проверка работы

### Тест 1: Проверка методов API

```powershell
python -c "
from dotenv import load_dotenv
load_dotenv()
from supabase_api import SupabaseAPI

api = SupabaseAPI()
methods = ['get_user_by_email', 'set_active_session', 'finish_active_session']

for method in methods:
    status = '✓' if hasattr(api, method) else '✗'
    print(f'{status} {method}')
"
```

**Ожидаемый вывод:**
```
✅ Supabase API initialized: https://...
✓ get_user_by_email
✓ set_active_session
✓ finish_active_session
```

### Тест 2: Запуск приложения

```powershell
python user_app/main.py
```

1. Введите ваш email
2. Нажмите "Вход"
3. Приложение должно успешно войти в систему

---

## 📊 Что теперь работает

После исправления:

- ✅ **Вход в систему** - пользователи могут авторизоваться по email
- ✅ **Создание сессии** - при входе создается активная сессия в Supabase
- ✅ **Проверка статуса** - приложение проверяет не был ли пользователь kicked
- ✅ **Выход из системы** - сессия корректно завершается
- ✅ **Логирование действий** - все действия записываются в work_log

---

## 🔄 Совместимость

Все добавленные методы **полностью совместимы** с `sheets_api.py`.

Это означает что:
- Можно переключаться между Supabase и Google Sheets без изменения кода
- Все приложения (user_app, admin_app, telegram_bot) работают одинаково
- Переключение происходит через `USE_SUPABASE = True/False` в `config.py`

---

## 🐛 Если всё ещё не работает

### Проблема: "User not found"

Убедитесь что в Supabase есть пользователи:

```powershell
python -c "
from dotenv import load_dotenv
load_dotenv()
from supabase_api import get_supabase_api

api = get_supabase_api()
users = api.get_users()
print(f'Пользователей в БД: {len(users)}')

if not users:
    print('⚠️ В базе данных нет пользователей!')
    print('Выполните миграцию: python migrate_to_supabase.py')
"
```

### Проблема: "Connection error"

Проверьте настройки Supabase в `.env`:

```powershell
python -c "
import os
from dotenv import load_dotenv
load_dotenv()

print(f'SUPABASE_URL: {os.getenv(\"SUPABASE_URL\")}')
print(f'SUPABASE_KEY: {os.getenv(\"SUPABASE_KEY\")[:20]}...')
"
```

### Проблема: "Table does not exist"

Создайте таблицы в Supabase:

```powershell
# Выполните SQL схему
# Откройте supabase_schema.sql и выполните в SQL Editor Supabase
```

---

## 📚 Дополнительная информация

- **Коммит:** `Fix: Add missing methods to SupabaseAPI for login compatibility`
- **Файлы изменены:** `supabase_api.py` (+164 строки)
- **Ветка:** `claude/analyze-project-repo-014htDps2c1UeCDCCYHN7UqC`

---

## 🎉 Готово!

Теперь вход в систему должен работать корректно.

Если возникнут другие проблемы - смотрите логи:
- Windows: `%APPDATA%/WorkTimeTracker/logs/`
- Linux: `~/.local/share/WorkTimeTracker/logs/`

Или запустите диагностику:
```powershell
python tools/doctor.py
```
