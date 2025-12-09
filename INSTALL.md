# 🔧 Инструкция по установке зависимостей

## ❌ Ошибка: ModuleNotFoundError: No module named 'pyzipper'

Эта ошибка означает, что в вашем виртуальном окружении не установлены необходимые пакеты.

---

## ✅ РЕШЕНИЕ: Установка зависимостей

### Вариант 1: Установить все зависимости из requirements.txt (РЕКОМЕНДУЕТСЯ)

```powershell
# Убедитесь что виртуальное окружение активировано (должно быть (.venv) в начале строки)
# Если активировано - выполните:

pip install -r requirements.txt
```

### Вариант 2: Установить только необходимые пакеты

```powershell
# Минимальный набор для работы:
pip install pyzipper python-dotenv supabase PyQt5 gspread google-auth requests cryptography
```

---

## 📋 Пошаговая инструкция

### 1. Убедитесь что виртуальное окружение активировано

В начале строки PowerShell должно быть `(.venv)`:

```powershell
(.venv) PS D:\proj vs code\WorkTimeTracker>
```

Если нет - активируйте:

```powershell
# Активация виртуального окружения
.\.venv\Scripts\Activate.ps1
```

### 2. Обновите pip (рекомендуется)

```powershell
python -m pip install --upgrade pip
```

### 3. Установите зависимости

```powershell
pip install -r requirements.txt
```

**Ожидаемый вывод:**
```
Collecting pyzipper>=0.3.6
Collecting python-dotenv>=1.0.1
Collecting supabase>=2.0.0
...
Successfully installed ...
```

### 4. Проверьте установку

```powershell
# Проверка что все пакеты установлены
pip list | Select-String -Pattern "pyzipper|dotenv|supabase"
```

**Должно вывести:**
```
pyzipper          0.3.6
python-dotenv     1.0.1
supabase          2.x.x
```

### 5. Тест загрузки конфигурации

```powershell
python -c "import config; print('✓ Конфигурация загружена успешно')"
```

**Ожидаемый вывод:**
```
✅ Использование: Supabase
✓ Конфигурация успешно проверена
✓ Конфигурация загружена успешно
```

---

## 🚀 Запуск приложения

После успешной установки зависимостей:

```powershell
# Пользовательское приложение
python user_app/main.py

# ИЛИ административная панель
python admin_app/main_admin.py

# ИЛИ Telegram бот
python telegram_bot/main.py
```

---

## 🐛 Возможные проблемы

### Проблема: "Execution of scripts is disabled"

```powershell
# Разрешите выполнение скриптов (запустите PowerShell от администратора):
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Проблема: pip не найден

```powershell
# Используйте python -m pip вместо pip:
python -m pip install -r requirements.txt
```

### Проблема: "ERROR: Could not install packages"

```powershell
# Установите каждый пакет отдельно:
pip install pyzipper
pip install python-dotenv
pip install supabase
pip install PyQt5
pip install gspread
pip install google-auth
pip install requests
pip install cryptography
```

### Проблема: PyQt5 не устанавливается

```powershell
# Для Windows скачайте wheel файл:
# https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyqt5
# Затем установите:
pip install PyQt5-5.15.9-cp311-cp311-win_amd64.whl
```

### Проблема: "module 'cryptography' has no attribute..."

```powershell
# Переустановите cryptography:
pip uninstall cryptography
pip install cryptography>=41.0.0
```

---

## ✅ Полный список зависимостей

Файл `requirements.txt` содержит:

```
# Google Sheets
gspread>=6.0.0
google-auth>=2.28.0
requests>=2.31.0

# Supabase
supabase>=2.0.0

# Desktop UI
PyQt5>=5.15.11

# Config & Secrets
python-dotenv>=1.0.1
pyzipper>=0.3.6

# Security
cryptography>=41.0.0
keyring>=24.0.0

# CLI utility
click>=8.1.0
```

---

## 📊 Проверка версий

После установки проверьте версии ключевых пакетов:

```powershell
python -c "import sys; print(f'Python: {sys.version}')"
python -c "import PyQt5.QtCore; print(f'PyQt5: {PyQt5.QtCore.PYQT_VERSION_STR}')"
python -c "import gspread; print(f'gspread: {gspread.__version__}')"
python -c "import supabase; print(f'supabase: {supabase.__version__}')"
```

---

## 🔄 Если нужно пересоздать виртуальное окружение

```powershell
# 1. Деактивируйте текущее окружение
deactivate

# 2. Удалите старое окружение
Remove-Item -Recurse -Force .venv

# 3. Создайте новое
python -m venv .venv

# 4. Активируйте
.\.venv\Scripts\Activate.ps1

# 5. Обновите pip
python -m pip install --upgrade pip

# 6. Установите зависимости
pip install -r requirements.txt
```

---

## 🎯 Быстрая установка (скопируйте все команды)

```powershell
# Активировать окружение
.\.venv\Scripts\Activate.ps1

# Обновить pip
python -m pip install --upgrade pip

# Установить зависимости
pip install -r requirements.txt

# Проверка
python -c "import config; print('✓ OK')"

# Запуск
python user_app/main.py
```

---

## 📚 Дополнительная информация

- **Python версия:** Требуется Python 3.10 или выше
- **Виртуальное окружение:** Рекомендуется использовать `.venv`
- **Платформа:** Windows, Linux, macOS

---

## 💡 Советы

1. **Всегда активируйте виртуальное окружение** перед запуском
2. **Используйте `requirements.txt`** для установки всех зависимостей
3. **Обновляйте pip** регулярно: `pip install --upgrade pip`
4. **Проверяйте версию Python:** `python --version` (нужно 3.10+)

---

## ✅ Готово!

После установки зависимостей все приложения должны запускаться без ошибок.

**Следующий шаг:** Запустите приложение:
```powershell
python user_app/main.py
```

Если возникнут другие ошибки - смотрите файл `SETUP_COMPLETE.md` для дополнительной информации.
