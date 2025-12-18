# План исправления уязвимостей WorkTimeTracker

## 🚨 Критический приоритет (исправить сегодня)

### 1. Удалить жестко закодированные секреты

**Файлы:** `config.py:30`, `api_adapter.py:40`

**Действия:**
```bash
# 1. Удалить строку из config.py
sed -i '/os.environ.setdefault("SUPABASE_KEY"/d' config.py

# 2. Проверить, что ключ берется только из переменных окружения
grep -n "SUPABASE_KEY" config.py api_adapter.py
```

**Код:**
```python
# config.py - УДАЛИТЬ:
os.environ.setdefault("SUPABASE_KEY", "eyJhbGci...")

# ЗАМЕНИТЬ на:
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
if not SUPABASE_KEY:
    raise ValueError("SUPABASE_KEY must be set in environment variables")
```

**Проверка:**
```bash
# Убедиться, что ключ не в коде
grep -r "eyJhbGci" . --exclude-dir=.git
```

---

### 2. Добавить валидацию email

**Файл:** `user_app/login_window.py`

**Действия:**
1. Добавить функцию санитизации
2. Использовать перед всеми запросами

**Код:**
```python
def _sanitize_email(self, email: str) -> str:
    """Санитизация и валидация email"""
    email = email.strip().lower()
    
    # Проверка формата
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        raise ValueError("Invalid email format")
    
    # Проверка на опасные символы
    dangerous = [';', '--', '/*', '*/', 'union', 'select', 'drop', 'delete']
    if any(char in email.lower() for char in dangerous):
        raise ValueError("Invalid email format")
    
    return email

# Использовать в _try_login:
email = self._sanitize_email(self.email_input.text().strip())
```

---

### 3. Исправить race condition в сессиях

**Файл:** `user_app/login_window.py:192-196`

**Действия:**
1. Использовать атомарную операцию
2. Добавить блокировку

**Код:**
```python
# Вместо:
active_session = self.sheets_api.get_active_session(email)
if active_session:
    session_id = active_session.get("SessionID")
    self.sheets_api.finish_active_session(email, session_id, logout_time)

# Использовать:
def finish_existing_and_create_new(email: str, new_session_id: str):
    """Атомарно завершить старые сессии и создать новую"""
    # Использовать транзакцию или специальный метод API
    self.sheets_api.finish_all_active_sessions(email)
    self.sheets_api.set_active_session(email, name, new_session_id)
```

---

## ⚠️ Высокий приоритет (исправить на этой неделе)

### 4. Rate limiting для Telegram бота

**Файл:** `telegram_bot/main.py`

**Время:** 1-2 часа

**Код:**
```python
from collections import defaultdict
from time import time

_rate_limits = defaultdict(list)
RATE_LIMIT_MAX = 10  # запросов в минуту

def check_rate_limit(chat_id: int) -> bool:
    now = time()
    requests = _rate_limits[chat_id]
    requests[:] = [t for t in requests if now - t < 60]
    
    if len(requests) >= RATE_LIMIT_MAX:
        return False
    
    requests.append(now)
    return True

# В main():
if not check_rate_limit(chat_id):
    _send(chat_id, "⚠️ Слишком много запросов. Подождите минуту.")
    continue
```

---

### 5. Безопасное хранение временных файлов

**Файл:** `config.py:152-158`

**Время:** 30 минут

**Код:**
```python
import stat
import tempfile
import os

fd, tmp_path = tempfile.mkstemp(suffix='.json', dir=tempfile.gettempdir())
try:
    with os.fdopen(fd, 'wb') as tmp:
        tmp.write(json_bytes)
    # Установить права: только владелец
    os.chmod(tmp_path, stat.S_IRUSR | stat.S_IWUSR)  # 0o600
    yield Path(tmp_path)
finally:
    try:
        os.unlink(tmp_path)
    except OSError:
        pass
```

---

### 6. Валидация данных в Supabase API

**Файл:** `supabase_api.py`

**Время:** 2-3 часа

**Действия:**
1. Создать модуль валидации
2. Добавить валидацию для всех входных данных

**Код:**
```python
# Создать файл: supabase_api/validators.py
import re
import uuid
from datetime import datetime

def validate_email(email: str) -> str:
    email = email.strip().lower()
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        raise ValueError(f"Invalid email: {email}")
    return email

def validate_uuid(value: str) -> str:
    try:
        uuid.UUID(value)
        return value
    except ValueError:
        raise ValueError(f"Invalid UUID: {value}")

def validate_datetime(value: str) -> str:
    # Проверка ISO формата
    try:
        datetime.fromisoformat(value.replace('Z', '+00:00'))
        return value
    except ValueError:
        raise ValueError(f"Invalid datetime: {value}")
```

---

### 7. Маскировка чувствительных данных в логах

**Файлы:** Все файлы с логированием

**Время:** 1-2 часа

**Код:**
```python
# Создать файл: logging_setup.py (дополнить)
import re
import logging

class SensitiveDataFilter(logging.Filter):
    def filter(self, record):
        if hasattr(record, 'msg'):
            msg = str(record.msg)
            # Маскировать email
            msg = re.sub(
                r'([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+)\.([a-zA-Z]{2,})',
                r'\1***@\2.***',
                msg
            )
            # Маскировать session_id
            msg = re.sub(
                r'(session[_-]?id[=:]\s*)([a-zA-Z0-9_-]+)',
                r'\1***',
                msg,
                flags=re.IGNORECASE
            )
            record.msg = msg
        return True

# Добавить фильтр ко всем логгерам
logging.getLogger().addFilter(SensitiveDataFilter())
```

---

### 8. Проверка прав доступа в админке

**Файл:** `admin_app/main_admin.py`

**Время:** 2-3 часа

**Действия:**
1. Добавить проверку роли пользователя
2. Создать декоратор для защиты методов

**Код:**
```python
def require_admin(func):
    """Декоратор для проверки административных прав"""
    def wrapper(self, *args, **kwargs):
        # Получить текущего пользователя из сессии
        current_user = self.get_current_user()
        if not current_user or current_user.get('role') not in ('admin', 'руководитель'):
            QMessageBox.warning(self, "Доступ запрещен", 
                              "Требуются административные права")
            return
        return func(self, *args, **kwargs)
    return wrapper

# Использовать:
@require_admin
def on_delete_user_clicked(self):
    # ...
```

---

## 📋 Средний приоритет (исправить в следующем спринте)

### 9-12. Остальные средние риски

См. полный список в `SECURITY_ANALYSIS.md`:
- Улучшение обработки ошибок
- Валидация размера данных
- Безопасные временные файлы
- Защита от CSRF
- SQL-инъекция через ключ шифрования
- Вывод части ключа в логи

---

## 🔧 Логические ошибки (исправить при рефакторинге)

### 13-15. Логические ошибки

- Дублирование логики UUID
- Некорректная обработка пустых значений
- Отсутствие транзакций

---

## ✅ Чеклист проверки

После исправления проверить:

- [ ] Нет жестко закодированных секретов в коде
- [ ] Все входные данные валидируются
- [ ] Rate limiting работает для Telegram бота
- [ ] Временные файлы создаются с правильными правами
- [ ] Чувствительные данные маскируются в логах
- [ ] Админка проверяет права доступа
- [ ] Нет SQL-инъекций (используются параметризованные запросы)
- [ ] Race conditions исправлены

---

## 📝 Тестирование

После исправления выполнить:

```bash
# 1. Проверка на секреты
grep -r "eyJhbGci\|password\|secret\|token" . --exclude-dir=.git | grep -v "\.md\|\.example"

# 2. Запуск тестов
python -m pytest tests/

# 3. Проверка безопасности
bandit -r . -f json -o security_report.json

# 4. Проверка типов
mypy . --ignore-missing-imports
```

---

## 📊 Прогресс

- [ ] Критические (4) - 0/4
- [ ] Высокие (4) - 0/4
- [ ] Средние (6) - 0/6
- [ ] Логические (3) - 0/3

**Общий прогресс:** 0/17

---

**Дата создания:** 2025-01-27  
**Следующий пересмотр:** После исправления критических уязвимостей
