# Команды Git для работы с репозиторием

## Текущая ветка
```bash
git branch
```

## Проверка статуса
```bash
git status
```

## Просмотр изменений
```bash
# Какие файлы изменены
git status --short

# Что изменено в файлах
git diff

# История коммитов
git log --oneline -10
```

## Загрузка изменений на GitHub

### 1. Добавить файлы в staging
```bash
# Все файлы
git add .

# Конкретный файл
git add archive_manager.py
```

### 2. Создать коммит
```bash
git commit -m "feat: добавлена автоматическая архивация данных"
```

### 3. Отправить на GitHub
```bash
git push origin cursor/database-storage-optimization-archive-e516
```

## Получение изменений с GitHub

```bash
# Получить изменения
git pull origin cursor/database-storage-optimization-archive-e516

# Или сначала fetch, потом merge
git fetch origin
git merge origin/cursor/database-storage-optimization-archive-e516
```

## Создание Pull Request

1. Перейдите на GitHub: https://github.com/tursd555-dot/WorkTimeTracker
2. Вы увидите уведомление о новой ветке
3. Нажмите "Compare & pull request"
4. Заполните описание изменений
5. Нажмите "Create pull request"

## Слияние в main

### Через GitHub (рекомендуется)
1. Создайте Pull Request
2. Проверьте изменения
3. Нажмите "Merge pull request"

### Через командную строку
```bash
# Переключиться на main
git checkout main

# Получить последние изменения
git pull origin main

# Слить ветку
git merge cursor/database-storage-optimization-archive-e516

# Отправить в main
git push origin main
```

## Полезные команды

```bash
# Просмотр удаленных репозиториев
git remote -v

# Просмотр всех веток
git branch -a

# Просмотр различий между ветками
git diff main..cursor/database-storage-optimization-archive-e516

# Отмена локальных изменений (ОСТОРОЖНО!)
git checkout -- файл.py

# Отмена последнего коммита (но сохранить изменения)
git reset --soft HEAD~1
```
