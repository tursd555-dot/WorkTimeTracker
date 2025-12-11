# Решение конфликта в PowerShell (Windows)

## Проблема

Конфликт слияния в файле `supabase_api.py`. Нужно принять версию с исправлениями.

## Решение (пошагово)

### Шаг 1: Отменить текущий merge (если еще не сделано)

```powershell
git merge --abort
```

### Шаг 2: Использовать версию с исправлениями из удаленного репозитория

```powershell
# Получить изменения
git fetch origin cursor/are-you-there-3152

# Использовать версию из удаленного репозитория
git checkout origin/cursor/are-you-there-3152 -- supabase_api.py

# Добавить файл в staging
git add supabase_api.py

# Проверить статус
git status
```

### Шаг 3: Проверить, что методы добавлены

В PowerShell используйте `Select-String` вместо `grep`:

```powershell
Select-String -Path supabase_api.py -Pattern "def kick_active_session"
Select-String -Path supabase_api.py -Pattern "def check_user_session_status"
Select-String -Path supabase_api.py -Pattern "def finish_active_session"
```

Должны увидеть строки с определениями методов.

### Шаг 4: Закоммитить изменения

```powershell
git commit -m "Принята версия с исправлениями разлогинивания из cursor/are-you-there-3152"
```

### Шаг 5: Проверить, что все в порядке

```powershell
git status
```

Должно быть "nothing to commit, working tree clean" или "Your branch is ahead of..."

## Альтернативный способ: через VS Code

1. **Откройте файл `supabase_api.py` в VS Code**

2. **VS Code автоматически покажет конфликт** с кнопками:
   - "Accept Incoming Change" (принять входящие изменения) ← **НАЖМИТЕ ЭТО**
   - "Accept Current Change" (оставить текущие)
   - "Accept Both Changes" (принять оба)

3. **Нажмите "Accept Incoming Change"** для всех конфликтов

4. **Сохраните файл** (Ctrl+S)

5. **В терминале PowerShell**:
   ```powershell
   git add supabase_api.py
   git commit -m "Разрешен конфликт: принята версия с исправлениями"
   ```

## Проверка успешного разрешения

После разрешения конфликта выполните:

```powershell
# Проверить наличие методов
Select-String -Path supabase_api.py -Pattern "def kick_active_session"
Select-String -Path supabase_api.py -Pattern "def check_user_session_status"

# Проверить статус git
git status

# Посмотреть последний коммит
git log --oneline -1
```

## Если что-то пошло не так

Если нужно начать заново:

```powershell
# Отменить все изменения в файле
git checkout HEAD -- supabase_api.py

# Или полностью сбросить локальные изменения
git reset --hard HEAD

# Затем повторить шаги выше
```
