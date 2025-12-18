@echo off
REM Батник для сборки всех приложений WorkTimeTracker для Windows
REM Использование: build_windows.bat [admin|user|bot|all]

setlocal enabledelayedexpansion

echo ================================================================================
echo СБОРКА ПРИЛОЖЕНИЙ WORKTIMETRACKER ДЛЯ WINDOWS
echo ================================================================================
echo.

REM Проверка наличия Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не найден! Установите Python 3.10 или выше.
    pause
    exit /b 1
)

REM Проверка наличия PyInstaller
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo [ПРЕДУПРЕЖДЕНИЕ] PyInstaller не установлен. Устанавливаю...
    pip install pyinstaller
    if errorlevel 1 (
        echo [ОШИБКА] Не удалось установить PyInstaller!
        pause
        exit /b 1
    )
)

REM Определение режима сборки
set BUILD_MODE=all
if not "%1"=="" set BUILD_MODE=%1

echo Режим сборки: %BUILD_MODE%
echo.

REM Запуск сборки
if "%BUILD_MODE%"=="admin" (
    python build_all_windows.py --admin
) else if "%BUILD_MODE%"=="user" (
    python build_all_windows.py --user
) else if "%BUILD_MODE%"=="bot" (
    python build_all_windows.py --bot
) else (
    python build_all_windows.py --all
)

if errorlevel 1 (
    echo.
    echo [ОШИБКА] Сборка завершилась с ошибками!
    pause
    exit /b 1
)

echo.
echo ================================================================================
echo СБОРКА ЗАВЕРШЕНА УСПЕШНО!
echo ================================================================================
echo.
echo Собранные приложения находятся в папке: dist\
echo Готовый пакет для распространения: release\
echo.
pause
