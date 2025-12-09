@echo off
REM Запуск пользовательского приложения WorkTimeTracker
cd /d "%~dp0"

echo ================================================
echo   WorkTimeTracker - User Application
echo ================================================
echo.

REM Активация виртуального окружения
if exist ".venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
    echo.
) else (
    echo WARNING: Virtual environment not found!
    echo Using system Python...
    echo.
)

REM Проверка Python
python --version 2>nul
if errorlevel 1 (
    echo ERROR: Python not found!
    echo Please install Python or fix virtual environment.
    pause
    exit /b 1
)

REM Запуск пользовательского приложения
echo Starting User Application...
echo.
python user_app/main.py

REM Если произошла ошибка
if errorlevel 1 (
    echo.
    echo ERROR: Failed to start User Application!
    echo Check the error message above.
    pause
)
