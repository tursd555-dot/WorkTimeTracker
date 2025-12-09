# HOTFIX: Исправление ошибки AttributeError '_cleanup'

## Проблема

При запуске приложения возникает ошибка:
```
AttributeError: 'ApplicationManager' object has no attribute '_cleanup'
```

## Причина

`atexit.register(self._cleanup)` вызывался в `__init__` до того, как метод `_cleanup` был определен в классе.

## Решение

Переместить `atexit.register(self._cleanup)` в конец блока инициализации, после того как все методы класса определены и инициализация прошла успешно.

## Изменения в user_app/main.py

### БЫЛО (строки 74-77):
```python
sys.excepthook = self.handle_uncaught_exception

# Регистрация cleanup
atexit.register(self._cleanup)

try:
    self._initialize_resources()
    self._start_sync_service()
    self.signals.app_started.emit()
```

### СТАЛО (строки 74-82):
```python
sys.excepthook = self.handle_uncaught_exception

try:
    self._initialize_resources()
    self._start_sync_service()
    self.signals.app_started.emit()
    
    # Регистрация cleanup после успешной инициализации
    atexit.register(self._cleanup)
```

## Как применить

### Вариант 1: Вручную
1. Открыть `user_app/main.py`
2. Найти строки 74-77
3. Убрать `atexit.register(self._cleanup)` из этого места
4. Добавить `atexit.register(self._cleanup)` после `self.signals.app_started.emit()`

### Вариант 2: Автоматически
```bash
cd /home/claude/WorkTimeTracker

# Удалить старую регистрацию
sed -i '76,77d' user_app/main.py

# Добавить новую регистрацию после app_started.emit()
# (это уже сделано в исправленной версии)
```

## Проверка

После применения патча приложение должно запускаться без ошибок:

```bash
python user_app/main.py
```

Ожидаемый вывод в логах:
```
[INFO] === ИНИЦИАЛИЗАЦИЯ СИСТЕМ ОТКАЗОУСТОЙЧИВОСТИ ===
[INFO] Circuit Breaker initialized for Sheets API
[INFO] ✓ Health Checker запущен (interval=60s)
[INFO] ✓ Degradation Manager запущен (interval=30s)
[INFO] === СИСТЕМЫ ОТКАЗОУСТОЙЧИВОСТИ ГОТОВЫ ===
```

## Статус

✅ Исправление применено в коде
✅ Тестирование требуется
