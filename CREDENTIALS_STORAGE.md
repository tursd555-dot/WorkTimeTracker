# Безопасное хранение Credentials

## Варианты хранения

### 1. ✅ Рекомендуется: Windows Credential Manager (keyring)

**Преимущества:**
- Пароль хранится в защищенном системном хранилище Windows
- Не нужно указывать пароль в `.env` файле
- Автоматическая защита системой Windows

**Настройка:**

```bash
# Установите keyring (уже в requirements.txt)
pip install keyring

# Настройте хранение пароля
python -c "from shared.credentials_storage import setup_credentials_storage; setup_credentials_storage()"
```

Или программно:
```python
from shared.credentials_storage import setup_credentials_storage, save_password_to_keyring

# Сохранить пароль в Windows Credential Manager
save_password_to_keyring("ваш_пароль")

# Или настроить автоматически
setup_credentials_storage()
```

**Использование:**
- Положите `secret_creds.zip` в папку с EXE
- Пароль будет автоматически загружен из Windows Credential Manager
- Не нужно указывать `CREDENTIALS_ZIP_PASSWORD` в `.env`

### 2. Supabase Storage (для архива)

**Преимущества:**
- Архив не хранится локально
- Доступен с любого компьютера
- Централизованное управление

**Настройка:**

1. Создайте bucket в Supabase Storage:
   ```sql
   -- В Supabase SQL Editor
   INSERT INTO storage.buckets (id, name, public)
   VALUES ('credentials', 'credentials', false);
   ```

2. Загрузите архив в Storage через Supabase Dashboard или API

3. Настройте переменные окружения:
   ```env
   SUPABASE_STORAGE_BUCKET=credentials
   SUPABASE_STORAGE_FILE=secret_creds.zip
   ```

4. Используйте:
   ```python
   from shared.credentials_storage import get_credentials_from_supabase_storage
   
   zip_data = get_credentials_from_supabase_storage()
   if zip_data:
       # Сохранить локально для использования
       with open("secret_creds.zip", "wb") as f:
           f.write(zip_data)
   ```

### 3. Комбинированный подход (лучший)

**Архив в Supabase Storage + Пароль в Windows Credential Manager**

```python
from shared.credentials_storage import (
    get_credentials_from_supabase_storage,
    get_password_from_keyring
)

# Загрузить архив из Supabase
zip_data = get_credentials_from_supabase_storage()
if zip_data:
    # Сохранить локально
    with open("secret_creds.zip", "wb") as f:
        f.write(zip_data)
    
    # Пароль из keyring
    password = get_password_from_keyring()
    # Использовать для расшифровки
```

## Текущий подход (улучшенный)

**Локальный ZIP + Пароль в keyring**

1. Положите `secret_creds.zip` в папку с проектом/EXE
2. Сохраните пароль в Windows Credential Manager:
   ```python
   from shared.credentials_storage import save_password_to_keyring
   save_password_to_keyring("ваш_пароль")
   ```
3. Удалите `CREDENTIALS_ZIP_PASSWORD` из `.env` файла
4. Готово! Пароль будет автоматически загружаться из keyring

## Безопасность

### ✅ Что безопасно:
- Windows Credential Manager (keyring) - защищено системой Windows
- Supabase Storage с RLS политиками - доступ только для авторизованных пользователей
- Зашифрованный ZIP архив - даже если украдут, нужен пароль

### ⚠️ Что менее безопасно:
- Пароль в `.env` файле - может быть прочитан
- Пароль в переменных окружения - виден в процессах
- Незашифрованный JSON файл - открытый доступ к credentials

## Миграция

### Из .env в keyring:

```python
from shared.credentials_storage import save_password_to_keyring
import os
from dotenv import load_dotenv

load_dotenv()
password = os.getenv("CREDENTIALS_ZIP_PASSWORD")

if password:
    save_password_to_keyring(password)
    print("✓ Пароль сохранен в Windows Credential Manager")
    print("  Теперь можно удалить CREDENTIALS_ZIP_PASSWORD из .env")
```

### Из локального файла в Supabase Storage:

```python
from shared.credentials_storage import save_credentials_to_supabase_storage
from pathlib import Path

zip_path = Path("secret_creds.zip")
if zip_path.exists():
    with open(zip_path, "rb") as f:
        zip_data = f.read()
    
    if save_credentials_to_supabase_storage(zip_data):
        print("✓ Credentials сохранены в Supabase Storage")
        print("  Можно удалить локальный файл (после проверки)")
```

## Проверка текущей конфигурации

```python
from shared.credentials_storage import (
    get_password_from_keyring,
    get_credentials_from_supabase_storage
)

# Проверка пароля
password = get_password_from_keyring()
if password:
    print("✓ Пароль найден в Windows Credential Manager")
else:
    print("⚠ Пароль не найден в keyring, используется из .env")

# Проверка архива в Supabase
zip_data = get_credentials_from_supabase_storage()
if zip_data:
    print("✓ Архив найден в Supabase Storage")
else:
    print("⚠ Архив не найден в Supabase Storage, используется локальный")
```
