#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Единый скрипт сборки всех приложений WorkTimeTracker для Windows

Собирает:
- WorkTimeTracker_Admin.exe (админка)
- WorkTimeTracker_User.exe (пользовательское приложение)
- WorkTimeTracker_Bot.exe (Telegram бот)

Использование:
    python build_all_windows.py [--admin] [--user] [--bot] [--all]
    
    По умолчанию собирает все приложения.
"""

import os
import sys
import logging
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Optional

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('build_all.log', mode='w', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Константы
PROJECT_ROOT = Path(__file__).parent.resolve()
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
RELEASE_DIR = PROJECT_ROOT / "release"

# Пути к скриптам сборки
BUILD_ADMIN = PROJECT_ROOT / "dev-tools" / "build" / "build_admin.py"
BUILD_USER = PROJECT_ROOT / "dev-tools" / "build" / "build_user.py"
BUILD_BOT = PROJECT_ROOT / "dev-tools" / "build" / "build_bot.py"

# Имена приложений
APP_ADMIN = "WorkTimeTracker_Admin"
APP_USER = "WorkTimeTracker_User"
APP_BOT = "WorkTimeTracker_Bot"


def _add_python_runtime_binaries(options: List[str], logger_obj: logging.Logger) -> None:
    """
    Добавляет критичные runtime DLL в сборку Windows.
    Это снижает риск ошибок вида:
    "Failed to load Python DLL ... LoadLibrary: The specified module could not be found".
    """
    if os.name != "nt":
        return

    py_ver = f"python{sys.version_info.major}{sys.version_info.minor}.dll"
    wanted_names = {
        py_ver,
        "python3.dll",
        "vcruntime140.dll",
        "vcruntime140_1.dll",
        "msvcp140.dll",
    }

    search_dirs = [
        Path(sys.executable).resolve().parent,   # venv\Scripts
        Path(sys.base_prefix),                   # base python dir
        Path(sys.base_prefix) / "DLLs",          # base python DLLs
    ]

    added: set[str] = set()
    for d in search_dirs:
        if not d.exists():
            continue
        for name in wanted_names:
            p = (d / name).resolve()
            if p.exists() and str(p) not in added:
                options.extend(["--add-binary", f"{p};."])
                added.add(str(p))

    if added:
        logger_obj.info("✓ Added Windows runtime binaries: %s", ", ".join(sorted(Path(x).name for x in added)))
    else:
        logger_obj.warning("⚠ Windows runtime DLLs were not found explicitly; target PC may require VC++ runtime")


def check_requirements() -> bool:
    """Проверка наличия необходимых файлов и зависимостей"""
    logger.info("🔍 Проверка требований...")
    
    # Проверка PyInstaller
    try:
        import PyInstaller
        logger.info(f"✓ PyInstaller {PyInstaller.__version__}")
        if sys.version_info >= (3, 14):
            logger.warning(
                "⚠ Сборка выполняется на Python %d.%d. "
                "Для максимальной совместимости рекомендуем Python 3.12.",
                sys.version_info.major,
                sys.version_info.minor,
            )
    except ImportError:
        logger.error("❌ PyInstaller не установлен! Установите: pip install pyinstaller")
        return False
    
    # Проверка необходимых файлов
    required_files = [
        "config.py",
    ]
    
    # Опциональные файлы (предупреждение, но не ошибка)
    optional_files = [
        "secret_creds.zip",
    ]
    
    missing_files = []
    for file_path in required_files:
        if not (PROJECT_ROOT / file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        logger.error(f"❌ Отсутствуют необходимые файлы: {', '.join(missing_files)}")
        return False
    
    # Проверка опциональных файлов (только предупреждение)
    for file_path in optional_files:
        if not (PROJECT_ROOT / file_path).exists():
            logger.warning(f"⚠ Опциональный файл не найден: {file_path} (будет пропущен при сборке)")
    
    # Проверка директорий
    required_dirs = [
        "admin_app",
        "user_app",
        "telegram_bot",
        "sync",
        "shared",
    ]
    
    missing_dirs = []
    for dir_path in required_dirs:
        if not (PROJECT_ROOT / dir_path).is_dir():
            missing_dirs.append(dir_path)
    
    if missing_dirs:
        logger.error(f"❌ Отсутствуют необходимые директории: {', '.join(missing_dirs)}")
        return False
    
    logger.info("✅ Все требования выполнены")
    return True


def clean_build_dirs():
    """Очистка директорий сборки"""
    logger.info("🧹 Очистка директорий сборки...")
    
    for dir_path in [DIST_DIR, BUILD_DIR]:
        if dir_path.exists():
            try:
                shutil.rmtree(dir_path)
                logger.info(f"  ✓ Удалена: {dir_path}")
            except Exception as e:
                logger.warning(f"  ⚠ Не удалось удалить {dir_path}: {e}")


def build_admin() -> bool:
    """Сборка админского приложения"""
    logger.info("=" * 80)
    logger.info("🚀 СБОРКА АДМИНСКОГО ПРИЛОЖЕНИЯ")
    logger.info("=" * 80)
    
    try:
        # Импортируем и запускаем скрипт сборки
        sys.path.insert(0, str(BUILD_ADMIN.parent))
        from build_admin import main as build_admin_main
        
        build_admin_main()
        
        exe_path = DIST_DIR / APP_ADMIN / f"{APP_ADMIN}.exe"
        if exe_path.exists():
            logger.info(f"✅ Админка собрана: {exe_path}")
            return True
        else:
            logger.error(f"❌ EXE файл не найден: {exe_path}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Ошибка сборки админки: {e}", exc_info=True)
        return False


def build_user() -> bool:
    """Сборка пользовательского приложения"""
    logger.info("=" * 80)
    logger.info("🚀 СБОРКА ПОЛЬЗОВАТЕЛЬСКОГО ПРИЛОЖЕНИЯ")
    logger.info("=" * 80)
    
    try:
        # Импортируем и запускаем скрипт сборки
        sys.path.insert(0, str(BUILD_USER.parent))
        from build_user import main as build_user_main
        
        build_user_main()
        
        exe_path = DIST_DIR / APP_USER / f"{APP_USER}.exe"
        if exe_path.exists():
            logger.info(f"✅ Пользовательское приложение собрано: {exe_path}")
            return True
        else:
            logger.error(f"❌ EXE файл не найден: {exe_path}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Ошибка сборки пользовательского приложения: {e}", exc_info=True)
        return False


def build_bot() -> bool:
    """Сборка Telegram бота"""
    logger.info("=" * 80)
    logger.info("🚀 СБОРКА TELEGRAM БОТА")
    logger.info("=" * 80)
    
    try:
        # Улучшенная сборка бота
        from PyInstaller.__main__ import run
        
        main_script = PROJECT_ROOT / "bot_launcher.py"
        icon_file = PROJECT_ROOT / "user_app" / "sberhealf.ico"
        
        options = [
            str(main_script),
            f'--name={APP_BOT}',
            '--onedir',  # Используем onedir для совместимости
            '--windowed',
            '--clean',
            '--noconfirm',
            '--log-level=WARN',
            '--paths=.',
        ]
        
        # Добавляем иконку, если существует
        if icon_file.exists():
            options.append(f'--icon={icon_file}')
        else:
            logger.warning(f"⚠ Иконка не найдена: {icon_file}")

        # Добавляем runtime DLL для переносимости на "чистые" Windows-машины
        _add_python_runtime_binaries(options, logger)
        
        # Добавляем данные
        data_files = [
            ('secret_creds.zip', '.'),
            ('config.py', '.'),
            ('.env', '.') if (PROJECT_ROOT / '.env').exists() else None,
        ]
        
        for src, dst in data_files:
            if src:
                src_path = PROJECT_ROOT / src
                if src_path.exists():
                    options.extend(['--add-data', f'{src_path};{dst}'])
        
        # Скрытые импорты
        hidden_imports = [
            'PyQt5',
            'PyQt5.QtCore',
            'PyQt5.QtWidgets',
            'PyQt5.QtGui',
            'telegram_bot',
            'telegram_bot.main',
        ]
        
        for imp in hidden_imports:
            options.extend(['--hidden-import', imp])
        
        logger.info(f"⚙️ Запуск PyInstaller с опциями: {' '.join(options)}")
        run(options)
        
        exe_path = DIST_DIR / APP_BOT / f"{APP_BOT}.exe"
        if exe_path.exists():
            logger.info(f"✅ Бот собран: {exe_path}")
            return True
        else:
            logger.error(f"❌ EXE файл не найден: {exe_path}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Ошибка сборки бота: {e}", exc_info=True)
        return False


def create_release_package() -> Optional[Path]:
    """Создание пакета для распространения"""
    logger.info("=" * 80)
    logger.info("📦 СОЗДАНИЕ ПАКЕТА ДЛЯ РАСПРОСТРАНЕНИЯ")
    logger.info("=" * 80)
    
    try:
        # Создаем директорию release
        RELEASE_DIR.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        release_name = f"WorkTimeTracker_Release_{timestamp}"
        release_path = RELEASE_DIR / release_name
        
        if release_path.exists():
            shutil.rmtree(release_path)
        release_path.mkdir(parents=True)
        
        # Копируем собранные приложения
        apps_to_copy = [
            (APP_ADMIN, "Админка"),
            (APP_USER, "Пользовательское приложение"),
            (APP_BOT, "Telegram бот"),
        ]
        
        copied_apps = []
        for app_name, description in apps_to_copy:
            app_dir = DIST_DIR / app_name
            if app_dir.exists():
                dest_dir = release_path / app_name
                shutil.copytree(app_dir, dest_dir)
                copied_apps.append((app_name, description))
                logger.info(f"  ✓ Скопировано: {app_name} ({description})")
            else:
                logger.warning(f"  ⚠ Приложение не найдено: {app_name}")
        
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

1. Распакуйте папку `WorkTimeTracker_Admin` в удобное место (например, `C:\\Program Files\\WorkTimeTracker\\Admin`)
2. Запустите `WorkTimeTracker_Admin.exe`
3. При первом запуске убедитесь, что файл `secret_creds.zip` находится в той же папке

### Для пользователя:

1. Распакуйте папку `WorkTimeTracker_User` в удобное место (например, `C:\\Program Files\\WorkTimeTracker\\User`)
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

## Примечания

- Все приложения работают независимо друг от друга
- Файл `secret_creds.zip` содержит зашифрованные учетные данные для доступа к Google Sheets/Supabase
- Не удаляйте файлы из папок приложений - они необходимы для работы
"""
        
        readme_path = release_path / "README.txt"
        readme_path.write_text(readme_content, encoding='utf-8')
        logger.info(f"  ✓ Создан README.txt")
        
        # Создаем архив (опционально)
        try:
            import zipfile
            zip_path = RELEASE_DIR / f"{release_name}.zip"
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(release_path):
                    for file in files:
                        file_path = Path(root) / file
                        arcname = file_path.relative_to(release_path.parent)
                        zipf.write(file_path, arcname)
            logger.info(f"  ✓ Создан архив: {zip_path}")
        except Exception as e:
            logger.warning(f"  ⚠ Не удалось создать архив: {e}")
        
        logger.info(f"✅ Пакет создан: {release_path}")
        return release_path
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания пакета: {e}", exc_info=True)
        return None


def main():
    """Главная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Сборка всех приложений WorkTimeTracker для Windows')
    parser.add_argument('--admin', action='store_true', help='Собрать только админку')
    parser.add_argument('--user', action='store_true', help='Собрать только пользовательское приложение')
    parser.add_argument('--bot', action='store_true', help='Собрать только бота')
    parser.add_argument('--all', action='store_true', help='Собрать все приложения (по умолчанию)')
    parser.add_argument('--no-clean', action='store_true', help='Не очищать директории сборки перед началом')
    parser.add_argument('--no-package', action='store_true', help='Не создавать пакет для распространения')
    
    args = parser.parse_args()
    
    # Определяем, что собирать
    build_admin_app = args.admin or (not args.user and not args.bot)
    build_user_app = args.user or (not args.admin and not args.bot)
    build_bot_app = args.bot or (not args.admin and not args.user)
    
    if args.all:
        build_admin_app = build_user_app = build_bot_app = True
    
    logger.info("=" * 80)
    logger.info("🔨 СБОРКА ПРИЛОЖЕНИЙ WORKTIMETRACKER ДЛЯ WINDOWS")
    logger.info("=" * 80)
    logger.info(f"Сборка: Admin={build_admin_app}, User={build_user_app}, Bot={build_bot_app}")
    logger.info("=" * 80)
    
    # Проверка требований
    if not check_requirements():
        logger.error("❌ Проверка требований не пройдена. Прерывание сборки.")
        return 1
    
    # Очистка
    if not args.no_clean:
        clean_build_dirs()
    
    # Сборка приложений
    results = {}
    
    if build_admin_app:
        results['admin'] = build_admin()
    
    if build_user_app:
        results['user'] = build_user()
    
    if build_bot_app:
        results['bot'] = build_bot()
    
    # Итоги
    logger.info("=" * 80)
    logger.info("📊 ИТОГИ СБОРКИ")
    logger.info("=" * 80)
    
    for app_name, success in results.items():
        status = "✅ Успешно" if success else "❌ Ошибка"
        logger.info(f"{app_name.upper()}: {status}")
    
    # Создание пакета
    if not args.no_package and any(results.values()):
        package_path = create_release_package()
        if package_path:
            logger.info(f"📦 Пакет готов к распространению: {package_path}")
    
    # Финальный статус
    all_success = all(results.values()) if results else False
    
    if all_success:
        logger.info("=" * 80)
        logger.info("✅ ВСЕ ПРИЛОЖЕНИЯ УСПЕШНО СОБРАНЫ!")
        logger.info("=" * 80)
        return 0
    else:
        logger.error("=" * 80)
        logger.error("❌ СБОРКА ЗАВЕРШИЛАСЬ С ОШИБКАМИ")
        logger.error("=" * 80)
        return 1


if __name__ == "__main__":
    sys.exit(main())
