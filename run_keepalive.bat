@echo off
REM ================================================================================
REM Supabase Keep-Alive - Windows запуск
REM ================================================================================
REM
REM Этот скрипт выполняет "ping" Supabase проекта для предотвращения приостановки
REM
REM Использование:
REM   1. Запуск вручную: дважды кликните на этот файл
REM   2. Планировщик задач: добавьте задачу на запуск каждые 3 дня
REM
REM ================================================================================

echo ================================================================================
echo Supabase Keep-Alive Script
echo ================================================================================
echo.

REM Проверка наличия Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python не найден!
    echo Установите Python: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Проверка наличия библиотеки supabase
python -c "import supabase" >nul 2>&1
if errorlevel 1 (
    echo WARNING: Библиотека 'supabase' не установлена!
    echo Устанавливаю...
    pip install supabase
    if errorlevel 1 (
        echo ERROR: Не удалось установить библиотеку!
        pause
        exit /b 1
    )
)

REM Запуск скрипта keep-alive
echo Запускаю keep-alive скрипт...
echo.
python "%~dp0supabase_keepalive.py"

if errorlevel 1 (
    echo.
    echo ERROR: Скрипт завершился с ошибкой!
    echo Проверьте что SUPABASE_URL и SUPABASE_KEY установлены в .env
    pause
    exit /b 1
)

echo.
echo ================================================================================
echo ГОТОВО! Supabase проект активен.
echo Следующий запуск: через 3 дня
echo ================================================================================
echo.

REM Закрыть автоматически через 5 секунд (для планировщика задач)
timeout /t 5 /nobreak >nul
exit /b 0
