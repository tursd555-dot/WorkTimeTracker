#!/usr/bin/env python3
"""
Patch script to update config imports in WorkTimeTracker

Обновляет импорты из старого config.py на новый config_secure.py
во всех файлах проекта.

Использование:
    python patch_config_imports.py

Автор: WorkTimeTracker Team
"""

import os
import re
from pathlib import Path


def patch_file(file_path: Path) -> bool:
    """
    Обновить импорты в файле.
    
    Args:
        file_path: Путь к файлу
        
    Returns:
        True если файл был изменён
    """
    try:
        # Прочитать файл
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Паттерны для замены
        patterns = [
            # from config import ...
            (
                r'from config import ([^\n]+)',
                'from config_secure import get_config\nconfig = get_config()'
            ),
            # import config
            (
                r'import config(?:\s|$)',
                'from config_secure import get_config\nconfig = get_config()'
            ),
        ]
        
        # Применить замены
        for pattern, replacement in patterns:
            if re.search(pattern, content):
                # Заменить импорт
                content = re.sub(pattern, replacement, content, count=1)
                
                # Заменить использование переменных
                # config.VARIABLE → config.get_variable()
                replacements = {
                    'SPREADSHEET_ID': 'config.get_spreadsheet_id()',
                    'WORKSHEET_NAME': 'config.get_worksheet_name()',
                    'TELEGRAM_BOT_TOKEN': 'config.get_telegram_token()',
                    'TELEGRAM_CHAT_ID': 'config.get_telegram_chat_id()',
                    'DB_MAIN_PATH': '"local_backup.db"',
                    'DB_FALLBACK_PATH': '"local_backup_fallback.db"',
                    'LOG_DIR': '"logs"',
                    'get_credentials_file()': 'config.get_google_credentials_path()',
                }
                
                for old, new in replacements.items():
                    # Заменить прямое использование
                    content = content.replace(old, new)
                
                break
        
        # Если изменения были
        if content != original_content:
            # Создать backup
            backup_path = file_path.with_suffix(file_path.suffix + '.bak')
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(original_content)
            
            # Записать изменённый файл
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return True
        
        return False
        
    except Exception as e:
        print(f"❌ Error patching {file_path}: {e}")
        return False


def main():
    """Основная функция"""
    print("=" * 80)
    print("WorkTimeTracker - Config Import Patcher")
    print("=" * 80)
    print()
    
    # Найти все Python файлы
    project_root = Path('.')
    python_files = list(project_root.rglob('*.py'))
    
    # Исключить некоторые файлы
    exclude = ['config.py', 'config_secure.py', 'patch_config_imports.py']
    python_files = [f for f in python_files if f.name not in exclude]
    
    print(f"Found {len(python_files)} Python files")
    print()
    
    # Патчить файлы
    patched = 0
    errors = 0
    
    for file_path in python_files:
        try:
            # Прочитать файл
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Проверить, нужен ли патч
            if 'from config import' in content or 'import config' in content:
                if patch_file(file_path):
                    print(f"✅ Patched: {file_path}")
                    patched += 1
                else:
                    print(f"⚠️  Skipped: {file_path}")
        
        except Exception as e:
            print(f"❌ Error: {file_path}: {e}")
            errors += 1
    
    print()
    print("=" * 80)
    print(f"Files patched: {patched}")
    print(f"Errors: {errors}")
    print()
    
    if patched > 0:
        print("✅ Patching completed!")
        print()
        print("Backup files created with .bak extension")
        print("If something goes wrong, restore from .bak files")
    else:
        print("No files needed patching")
    
    print("=" * 80)


if __name__ == "__main__":
    main()