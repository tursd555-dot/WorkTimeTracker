#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для создания готового пакета приложений для распространения

Создает структурированный архив с приложениями и инструкциями.
"""

import os
import sys
import shutil
import zipfile
from pathlib import Path
from datetime import datetime
from typing import Optional

def create_release_package(dist_dir: Optional[Path] = None, output_dir: Optional[Path] = None) -> Optional[Path]:
    """
    Создает пакет для распространения из собранных приложений
    
    Args:
        dist_dir: Путь к папке dist (по умолчанию ./dist)
        output_dir: Путь для сохранения пакета (по умолчанию ./release)
    
    Returns:
        Путь к созданному пакету или None в случае ошибки
    """
    project_root = Path(__file__).parent.resolve()
    
    if dist_dir is None:
        dist_dir = project_root / "dist"
    
    if output_dir is None:
        output_dir = project_root / "release"
    
    if not dist_dir.exists():
        print(f"❌ Папка dist не найдена: {dist_dir}")
        print("   Сначала выполните сборку приложений: python build_all_windows.py")
        return None
    
    # Создаем директорию release
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    release_name = f"WorkTimeTracker_Release_{timestamp}"
    release_path = output_dir / release_name
    
    if release_path.exists():
        shutil.rmtree(release_path)
    release_path.mkdir(parents=True)
    
    print("=" * 80)
    print("📦 СОЗДАНИЕ ПАКЕТА ДЛЯ РАСПРОСТРАНЕНИЯ")
    print("=" * 80)
    print(f"Источник: {dist_dir}")
    print(f"Назначение: {release_path}")
    print()
    
    # Копируем собранные приложения
    apps_to_copy = [
        ("WorkTimeTracker_Admin", "Админка"),
        ("WorkTimeTracker_User", "Пользовательское приложение"),
        ("WorkTimeTracker_Bot", "Telegram бот"),
    ]
    
    copied_apps = []
    for app_name, description in apps_to_copy:
        app_dir = dist_dir / app_name
        if app_dir.exists():
            dest_dir = release_path / app_name
            print(f"📋 Копирование {app_name}...")
            shutil.copytree(app_dir, dest_dir)
            copied_apps.append((app_name, description))
            print(f"   ✓ Скопировано: {app_name}")
        else:
            print(f"   ⚠ Приложение не найдено: {app_name}")
    
    if not copied_apps:
        print("❌ Не найдено ни одного собранного приложения!")
        shutil.rmtree(release_path)
        return None
    
    # Создаем README для пользователей
    readme_content = f"""# WorkTimeTracker - Готовые приложения

Дата сборки: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Содержимое пакета

"""
    for app_name, description in copied_apps:
        readme_content += f"- **{app_name}** - {description}\n"
    
    readme_content += """
## Инструкция по установке

### Для администратора:

1. Распакуйте папку `WorkTimeTracker_Admin` в удобное место
   (например, `C:\\Program Files\\WorkTimeTracker\\Admin`)
2. Запустите `WorkTimeTracker_Admin.exe`
3. При первом запуске убедитесь, что файл `secret_creds.zip` находится в той же папке

### Для пользователя:

1. Распакуйте папку `WorkTimeTracker_User` в удобное место
   (например, `C:\\Program Files\\WorkTimeTracker\\User`)
2. Запустите `WorkTimeTracker_User.exe`
3. При первом запуске убедитесь, что файл `secret_creds.zip` находится в той же папке
4. Войдите в систему используя свой email

### Для Telegram бота:

1. Распакуйте папку `WorkTimeTracker_Bot` в удобное место
2. Убедитесь, что файл `.env` настроен с правильными токенами Telegram
3. Запустите `WorkTimeTracker_Bot.exe`
4. Бот будет работать в фоновом режиме

## Требования

- Windows 7 или выше
- Не требуется установка Python или дополнительных библиотек

## Поддержка

При возникновении проблем проверьте логи в папке `logs` (создается автоматически).

## Важно!

- Все приложения работают независимо друг от друга
- Файл `secret_creds.zip` содержит зашифрованные учетные данные для доступа к базе данных
- Не удаляйте файлы из папок приложений - они необходимы для работы
- При первом запуске антивирус может заблокировать приложение - это ложное срабатывание
"""
    
    readme_path = release_path / "README.txt"
    readme_path.write_text(readme_content, encoding='utf-8')
    print(f"   ✓ Создан README.txt")
    
    # Создаем архив
    try:
        zip_path = output_dir / f"{release_name}.zip"
        print(f"📦 Создание архива {zip_path.name}...")
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(release_path):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(release_path.parent)
                    zipf.write(file_path, arcname)
        
        zip_size_mb = zip_path.stat().st_size / (1024 * 1024)
        print(f"   ✓ Архив создан: {zip_path.name} ({zip_size_mb:.1f} МБ)")
        
    except Exception as e:
        print(f"   ⚠ Не удалось создать архив: {e}")
        zip_path = None
    
    print()
    print("=" * 80)
    print("✅ ПАКЕТ СОЗДАН УСПЕШНО!")
    print("=" * 80)
    print(f"Расположение: {release_path}")
    if zip_path:
        print(f"Архив: {zip_path}")
    print()
    print("Теперь вы можете:")
    print("  1. Передать папку или архив администратору и пользователям")
    print("  2. Распространить через файлообменник или внутреннюю сеть")
    print()
    
    return release_path


def main():
    """Главная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Создание пакета для распространения')
    parser.add_argument('--dist', type=str, help='Путь к папке dist (по умолчанию ./dist)')
    parser.add_argument('--output', type=str, help='Путь для сохранения пакета (по умолчанию ./release)')
    
    args = parser.parse_args()
    
    dist_dir = Path(args.dist) if args.dist else None
    output_dir = Path(args.output) if args.output else None
    
    result = create_release_package(dist_dir, output_dir)
    
    if result:
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
