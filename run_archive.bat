@echo off
REM Скрипт для запуска архивации данных на Windows
REM Автоматически активирует виртуальное окружение если оно есть

setlocal

REM Получаем директорию где находится скрипт
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

REM Проверяем наличие виртуального окружения
if exist ".venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
) else if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
)

REM Запускаем скрипт архивации
echo Starting archive process...
python run_archive.py

REM Сохраняем код выхода
set EXIT_CODE=%ERRORLEVEL%

REM Если была активирована виртуальная среда, деактивируем
if defined VIRTUAL_ENV (
    deactivate
)

exit /b %EXIT_CODE%
