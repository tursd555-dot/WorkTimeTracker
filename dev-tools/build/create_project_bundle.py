#!/usr/bin/env python3
# coding: utf-8
"""
Создание полного бандла проекта WorkTimeTracker

Включает:
- Структуру проекта
- Все исходные файлы
- Конфигурацию
- Структуру Google Sheets
- Зависимости
"""
import sys
from pathlib import Path
from datetime import datetime
import json

# Файлы и директории для включения
INCLUDE_PATTERNS = [
    "*.py",
    "*.txt",
    "*.md",
    "*.json",
    "*.toml",
    "*.ini",
    "*.cfg",
    "*.yaml",
    "*.yml",
    ".env.example",
]

INCLUDE_DIRS = [
    "admin_app",
    "user_app", 
    "shared",
    "notifications",
    "telegram_bot",
    "sync",
    "tools",
]

EXCLUDE_PATTERNS = [
    "__pycache__",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    ".git",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "dist",
    "build",
    "*.egg-info",
    ".pytest_cache",
    ".mypy_cache",
    "logs",
    "*.log",
    "*.db",
    "*.zip",
    ".env",  # Не включаем секреты
    "temp_credentials.json",
    "service_account.json",
    "credentials",
    "secret_creds",
]

# Файлы в корне
ROOT_FILES = [
    "config.py",
    "sheets_api.py",
    "logging_setup.py",
    "requirements.txt",
    "pyproject.toml",
    "README.md",
]

def should_exclude(path: Path) -> bool:
    """Проверяет нужно ли исключить файл/директорию"""
    path_str = str(path)
    for pattern in EXCLUDE_PATTERNS:
        if pattern in path_str:
            return True
    return False

def get_google_sheets_structure():
    """Получает структуру Google Sheets"""
    try:
        from api_adapter import get_sheets_api
        from config import GOOGLE_SHEET_NAME
        
        sheets = get_sheets_api()
        ss = sheets.client.open(GOOGLE_SHEET_NAME)
        
        structure = {
            "spreadsheet_name": GOOGLE_SHEET_NAME,
            "worksheets": []
        }
        
        for ws in ss.worksheets():
            try:
                # Получаем заголовки
                header = sheets._request_with_retry(ws.row_values, 1) or []
                row_count = ws.row_count
                col_count = ws.col_count
                
                ws_info = {
                    "title": ws.title,
                    "rows": row_count,
                    "cols": col_count,
                    "headers": header
                }
                
                # Для небольших листов получаем примеры данных
                if row_count <= 100:
                    values = sheets._request_with_retry(ws.get_all_values) or []
                    ws_info["sample_data"] = values[:5] if len(values) > 1 else []
                
                structure["worksheets"].append(ws_info)
                
            except Exception as e:
                print(f"  Warning: Could not read worksheet {ws.title}: {e}")
        
        return structure
        
    except Exception as e:
        print(f"Warning: Could not access Google Sheets: {e}")
        return None

def create_bundle():
    """Создаёт бандл проекта"""
    
    root = Path.cwd()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = root / f"project_bundle_{timestamp}.txt"
    
    print("=" * 80)
    print("СОЗДАНИЕ БАНДЛА ПРОЕКТА")
    print("=" * 80)
    print()
    print(f"Корень проекта: {root}")
    print(f"Выходной файл: {output_file}")
    print()
    
    with open(output_file, 'w', encoding='utf-8') as f:
        # Заголовок
        f.write("=" * 80 + "\n")
        f.write("WORKTIMETRACKER PROJECT BUNDLE\n")
        f.write("=" * 80 + "\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n")
        f.write(f"Root: {root}\n")
        f.write("=" * 80 + "\n\n")
        
        # 1. Структура проекта
        print("1. Создание дерева проекта...")
        f.write("=" * 80 + "\n")
        f.write("PROJECT STRUCTURE\n")
        f.write("=" * 80 + "\n\n")
        
        def write_tree(path: Path, prefix: str = "", is_last: bool = True):
            if should_exclude(path):
                return
            
            connector = "└── " if is_last else "├── "
            f.write(f"{prefix}{connector}{path.name}\n")
            
            if path.is_dir():
                children = sorted([p for p in path.iterdir() if not should_exclude(p)])
                for i, child in enumerate(children):
                    is_last_child = (i == len(children) - 1)
                    extension = "    " if is_last else "│   "
                    write_tree(child, prefix + extension, is_last_child)
        
        write_tree(root)
        f.write("\n")
        
        # 2. Google Sheets структура
        print("2. Получение структуры Google Sheets...")
        f.write("=" * 80 + "\n")
        f.write("GOOGLE SHEETS STRUCTURE\n")
        f.write("=" * 80 + "\n\n")
        
        sheets_structure = get_google_sheets_structure()
        if sheets_structure:
            f.write(f"Spreadsheet: {sheets_structure['spreadsheet_name']}\n\n")
            
            for ws in sheets_structure['worksheets']:
                f.write(f"Sheet: {ws['title']}\n")
                f.write(f"  Size: {ws['rows']} rows × {ws['cols']} cols\n")
                f.write(f"  Headers: {', '.join(ws['headers'])}\n")
                
                if ws.get('sample_data'):
                    f.write(f"  Sample data (first 5 rows):\n")
                    for i, row in enumerate(ws['sample_data'], 1):
                        f.write(f"    {i}. {row}\n")
                
                f.write("\n")
        else:
            f.write("Could not access Google Sheets structure\n\n")
        
        # 3. Зависимости
        print("3. Сбор зависимостей...")
        f.write("=" * 80 + "\n")
        f.write("DEPENDENCIES\n")
        f.write("=" * 80 + "\n\n")
        
        req_file = root / "requirements.txt"
        if req_file.exists():
            f.write("requirements.txt:\n")
            f.write(req_file.read_text(encoding='utf-8'))
            f.write("\n")
        
        pyproject_file = root / "pyproject.toml"
        if pyproject_file.exists():
            f.write("\npyproject.toml:\n")
            f.write(pyproject_file.read_text(encoding='utf-8'))
            f.write("\n")
        
        # 4. Исходные файлы
        print("4. Копирование исходных файлов...")
        f.write("=" * 80 + "\n")
        f.write("SOURCE FILES\n")
        f.write("=" * 80 + "\n\n")
        
        file_count = 0
        
        # Корневые файлы
        for filename in ROOT_FILES:
            filepath = root / filename
            if filepath.exists() and not should_exclude(filepath):
                print(f"   + {filepath.relative_to(root)}")
                f.write("-" * 80 + "\n")
                f.write(f"File: {filepath.relative_to(root)}\n")
                f.write("-" * 80 + "\n")
                
                try:
                    content = filepath.read_text(encoding='utf-8')
                    f.write(content)
                    f.write("\n\n")
                    file_count += 1
                except Exception as e:
                    f.write(f"Error reading file: {e}\n\n")
        
        # Директории
        for dir_name in INCLUDE_DIRS:
            dir_path = root / dir_name
            if not dir_path.exists():
                continue
            
            print(f"   Processing {dir_name}/...")
            
            for pattern in INCLUDE_PATTERNS:
                for filepath in dir_path.rglob(pattern):
                    if should_exclude(filepath):
                        continue
                    
                    print(f"   + {filepath.relative_to(root)}")
                    f.write("-" * 80 + "\n")
                    f.write(f"File: {filepath.relative_to(root)}\n")
                    f.write("-" * 80 + "\n")
                    
                    try:
                        content = filepath.read_text(encoding='utf-8')
                        f.write(content)
                        f.write("\n\n")
                        file_count += 1
                    except Exception as e:
                        f.write(f"Error reading file: {e}\n\n")
        
        # 5. Конфигурация (пример)
        print("5. Создание примера конфигурации...")
        f.write("=" * 80 + "\n")
        f.write("CONFIGURATION EXAMPLE\n")
        f.write("=" * 80 + "\n\n")
        
        f.write("""# .env.example
# Copy this file to .env and fill in your values

# Google Sheets
GOOGLE_SHEET_NAME=WorkTime
GOOGLE_CREDENTIALS_FILE=temp_credentials.json

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_ADMIN_CHAT_ID=your_admin_chat_id
TELEGRAM_MONITORING_CHAT_ID=-1002917784307

# Paths
DB_MAIN_PATH=local_backup.db
LOG_DIR=logs

# Limits
BREAK_LIMIT_MINUTES=15
LUNCH_LIMIT_MINUTES=60

# Notifications
BREAK_NOTIFY_USER_ON_VIOLATION=True
BREAK_NOTIFY_ADMIN_ON_VIOLATION=True
""")
        
        # Итоги
        f.write("\n")
        f.write("=" * 80 + "\n")
        f.write("BUNDLE SUMMARY\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Total files included: {file_count}\n")
        f.write(f"Google Sheets: {'✓ Included' if sheets_structure else '✗ Not available'}\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n")
    
    print()
    print("=" * 80)
    print("✓ БАНДЛ СОЗДАН!")
    print("=" * 80)
    print()
    print(f"Файл: {output_file}")
    print(f"Размер: {output_file.stat().st_size / 1024:.2f} KB")
    print(f"Файлов: {file_count}")
    print()
    print("Вы можете:")
    print("  1. Отправить этот файл Claude для анализа")
    print("  2. Использовать как backup")
    print("  3. Использовать для документации")
    print()
    
    return output_file

if __name__ == "__main__":
    try:
        bundle_file = create_bundle()
        print(f"Success! Bundle saved to: {bundle_file}")
    except KeyboardInterrupt:
        print("\n\nОтменено пользователем")
    except Exception as e:
        print(f"\n\n✗ Ошибка: {e}")
        import traceback
        traceback.print_exc()
