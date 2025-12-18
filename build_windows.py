#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Главный скрипт сборки всех компонентов WorkTimeTracker для Windows

Собирает:
1. Пользовательская часть (WorkTimeTracker_User.exe)
2. Админка (WorkTimeTracker_Admin.exe)
3. Реал тайм монитор (WorkTimeTracker_Monitor.exe)
4. Телеграм бот (WorkTimeTracker_Bot.exe)

Все компоненты собираются как portable приложения (--onedir),
работают без прав администратора и готовы к отправке.
"""

import os
import sys
import logging
import shutil
import zipfile
import stat
import time
from pathlib import Path
from datetime import datetime
from PyInstaller.__main__ import run

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('build_all.log', mode='w', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Корневая директория проекта
ROOT_DIR = Path(__file__).parent.resolve()
os.chdir(ROOT_DIR)

# Общие зависимости для всех приложений
COMMON_HIDDEN_IMPORTS = [
    'PyQt5.sip',
    'gspread',
    'google.auth',
    'google.oauth2',
    'googleapiclient',
    'googleapiclient.discovery',
    'httplib2',
    'OpenSSL',
    'requests',
    'sqlite3',
    'cryptography',
    'pyzipper',
    'dotenv',
    'supabase',
    'supabase.client',
    'supabase._sync',
    'postgrest',
    'realtime',
    'storage',
    'gotrue',
    'functions',
    'api_adapter',
    'supabase_api',
    'sheets_api',
    'httpx',
    'httpx._client',
    'httpx._transports',
    'httpx._config',
    'certifi',
    'ssl',
]

# Общие данные для включения
COMMON_DATA_FILES = [
    ('config.py', '.'),
    ('api_adapter.py', '.'),
    ('sheets_api.py', '.'),
    ('supabase_api.py', '.'),
    ('auto_sync.py', '.'),
    ('logging_setup.py', '.'),
    ('shared', 'shared'),
    ('sync', 'sync'),
    ('notifications', 'notifications'),
]

def check_required_files():
    """Проверяет наличие необходимых файлов"""
    required = [
        'config.py',
        'user_app',
        'admin_app',
        'telegram_bot',
        'shared',
        'sync',
        'notifications',
    ]
    missing = []
    for item in required:
        if not Path(item).exists():
            missing.append(item)
    
    if missing:
        logger.error(f"❌ Отсутствуют необходимые файлы: {', '.join(missing)}")
        return False
    
    # Проверяем опциональные файлы
    optional = ['secret_creds.zip', '.env']
    for item in optional:
        if Path(item).exists():
            logger.info(f"✓ Найден: {item}")
        else:
            logger.warning(f"⚠ Не найден (опционально): {item}")
    
    return True

def get_base_options(main_script: str, app_name: str, windowed: bool = True):
    """Возвращает базовые опции PyInstaller для всех приложений"""
    options = [
        main_script,
        f'--name={app_name}',
        '--onedir',
        '--windowed' if windowed else '--console',
        '--clean',
        '--noconfirm',
        '--log-level=WARN',
        '--paths=.',
        '--collect-all', 'certifi',  # Собираем SSL сертификаты
        '--collect-submodules', 'httpx',  # Собираем все подмодули httpx
        '--collect-submodules', 'supabase',  # Собираем все подмодули supabase
    ]
    return options

def build_user_app():
    """Собирает пользовательскую часть"""
    logger.info("=" * 80)
    logger.info("🚀 Сборка пользовательской части...")
    logger.info("=" * 80)
    
    app_name = "WorkTimeTracker_User"
    main_script = "user_app/main.py"
    icon_file = "user_app/sberhealf.ico"
    
    options = get_base_options(main_script, app_name, windowed=True)
    
    # Иконка
    if Path(icon_file).exists():
        options.append(f'--icon={icon_file}')
    
    # Данные
    for src, dst in COMMON_DATA_FILES:
        if Path(src).exists():
            options.extend(['--add-data', f'{src};{dst}'])
    
    # Специфичные данные для пользовательской части
    user_data = [
        ('user_app', 'user_app'),
    ]
    for src, dst in user_data:
        if Path(src).exists():
            options.extend(['--add-data', f'{src};{dst}'])
    
    # Скрытые импорты
    user_imports = COMMON_HIDDEN_IMPORTS + [
        'user_app',
        'user_app.gui',
        'user_app.login_window',
        'user_app.db_local',
        'user_app.signals',
        'user_app.session',
        'user_app.personal_rules',
        'user_app.ui_helpers',
        'user_app.break_info_widget',
        'auto_sync',
        'sync',
        'sync.notifications',
        'sync.sync_queue_improved',
        'sync.conflict_resolver',
        'sync.network',
        'notifications',
        'notifications.engine',
        'notifications.rules_manager',
        'shared',
        'shared.health',
        'shared.resilience',
        'shared.time_utils',
        'shared.data_cache',
        'shared.db',
        'shared.db.connection_pool',
        'shared.db.encrypted_database',
    ]
    for imp in user_imports:
        options.extend(['--hidden-import', imp])
    
    # Опциональные файлы
    if Path('secret_creds.zip').exists():
        options.extend(['--add-data', 'secret_creds.zip;.'])
    if Path('.env').exists():
        options.extend(['--add-data', '.env;.'])
    
    try:
        run(options)
        exe_path = Path('dist') / app_name / f"{app_name}.exe"
        if exe_path.exists():
            logger.info(f"✅ Пользовательская часть собрана: {exe_path}")
            return True
        else:
            logger.error(f"❌ EXE не найден: {exe_path}")
            return False
    except Exception as e:
        logger.error(f"❌ Ошибка сборки пользовательской части: {e}", exc_info=True)
        return False

def build_admin_app():
    """Собирает админку"""
    logger.info("=" * 80)
    logger.info("🚀 Сборка админки...")
    logger.info("=" * 80)
    
    app_name = "WorkTimeTracker_Admin"
    main_script = "admin_app/main_admin.py"
    icon_file = "user_app/sberhealf.ico"
    
    options = get_base_options(main_script, app_name, windowed=True)
    
    # Иконка
    if Path(icon_file).exists():
        options.append(f'--icon={icon_file}')
    
    # Данные
    for src, dst in COMMON_DATA_FILES:
        if Path(src).exists():
            options.extend(['--add-data', f'{src};{dst}'])
    
    # Специфичные данные для админки
    admin_data = [
        ('admin_app', 'admin_app'),
    ]
    for src, dst in admin_data:
        if Path(src).exists():
            options.extend(['--add-data', f'{src};{dst}'])
    
    # Скрытые импорты
    admin_imports = COMMON_HIDDEN_IMPORTS + [
        'admin_app',
        'admin_app.repo',
        'admin_app.gui_admin',
        'admin_app.break_manager',
        'admin_app.break_analytics_tab',
        'admin_app.break_schedule_dialog',
        'admin_app.break_monitor_service',
        'admin_app.notifications_panel',
        'admin_app.reports_tab',
        'admin_app.audit_logger',
        'admin_app.schedule_parser',
        'shared',
        'shared.time_utils',
        'shared.data_cache',
    ]
    for imp in admin_imports:
        options.extend(['--hidden-import', imp])
    
    # Опциональные файлы
    if Path('secret_creds.zip').exists():
        options.extend(['--add-data', 'secret_creds.zip;.'])
    if Path('.env').exists():
        options.extend(['--add-data', '.env;.'])
    
    try:
        run(options)
        exe_path = Path('dist') / app_name / f"{app_name}.exe"
        if exe_path.exists():
            logger.info(f"✅ Админка собрана: {exe_path}")
            return True
        else:
            logger.error(f"❌ EXE не найден: {exe_path}")
            return False
    except Exception as e:
        logger.error(f"❌ Ошибка сборки админки: {e}", exc_info=True)
        return False

def build_monitor_app():
    """Собирает реал тайм монитор"""
    logger.info("=" * 80)
    logger.info("🚀 Сборка реал тайм монитора...")
    logger.info("=" * 80)
    
    app_name = "WorkTimeTracker_Monitor"
    main_script = "admin_app/realtime_monitor.py"
    icon_file = "user_app/sberhealf.ico"
    
    options = get_base_options(main_script, app_name, windowed=True)
    
    # Иконка
    if Path(icon_file).exists():
        options.append(f'--icon={icon_file}')
    
    # Данные
    for src, dst in COMMON_DATA_FILES:
        if Path(src).exists():
            options.extend(['--add-data', f'{src};{dst}'])
    
    # Специфичные данные для монитора
    monitor_data = [
        ('admin_app', 'admin_app'),
    ]
    for src, dst in monitor_data:
        if Path(src).exists():
            options.extend(['--add-data', f'{src};{dst}'])
    
    # Скрытые импорты
    monitor_imports = COMMON_HIDDEN_IMPORTS + [
        'admin_app',
        'admin_app.repo',
        'admin_app.break_manager',
        'shared',
        'shared.time_utils',
    ]
    for imp in monitor_imports:
        options.extend(['--hidden-import', imp])
    
    # Опциональные файлы
    if Path('secret_creds.zip').exists():
        options.extend(['--add-data', 'secret_creds.zip;.'])
    if Path('.env').exists():
        options.extend(['--add-data', '.env;.'])
    
    try:
        run(options)
        exe_path = Path('dist') / app_name / f"{app_name}.exe"
        if exe_path.exists():
            logger.info(f"✅ Реал тайм монитор собран: {exe_path}")
            return True
        else:
            logger.error(f"❌ EXE не найден: {exe_path}")
            return False
    except Exception as e:
        logger.error(f"❌ Ошибка сборки монитора: {e}", exc_info=True)
        return False

def build_bot_app():
    """Собирает телеграм бота"""
    logger.info("=" * 80)
    logger.info("🚀 Сборка телеграм бота...")
    logger.info("=" * 80)
    
    app_name = "WorkTimeTracker_Bot"
    main_script = "telegram_bot/main.py"
    icon_file = "user_app/sberhealf.ico"
    
    options = get_base_options(main_script, app_name, windowed=False)  # Бот должен показывать консоль
    
    # Иконка
    if Path(icon_file).exists():
        options.append(f'--icon={icon_file}')
    
    # Данные
    for src, dst in COMMON_DATA_FILES:
        if Path(src).exists():
            options.extend(['--add-data', f'{src};{dst}'])
    
    # Специфичные данные для бота
    bot_data = [
        ('telegram_bot', 'telegram_bot'),
    ]
    for src, dst in bot_data:
        if Path(src).exists():
            options.extend(['--add-data', f'{src};{dst}'])
    
    # Скрытые импорты
    bot_imports = COMMON_HIDDEN_IMPORTS + [
        'telegram_bot',
        'telegram_bot.notifier',
    ]
    for imp in bot_imports:
        options.extend(['--hidden-import', imp])
    
    # Опциональные файлы
    if Path('secret_creds.zip').exists():
        options.extend(['--add-data', 'secret_creds.zip;.'])
    if Path('.env').exists():
        options.extend(['--add-data', '.env;.'])
    
    try:
        run(options)
        exe_path = Path('dist') / app_name / f"{app_name}.exe"
        if exe_path.exists():
            logger.info(f"✅ Телеграм бот собран: {exe_path}")
            return True
        else:
            logger.error(f"❌ EXE не найден: {exe_path}")
            return False
    except Exception as e:
        logger.error(f"❌ Ошибка сборки бота: {e}", exc_info=True)
        return False

def create_archive():
    """Создает ZIP архив со всеми собранными приложениями"""
    logger.info("=" * 80)
    logger.info("📦 Создание архива...")
    logger.info("=" * 80)
    
    dist_dir = Path('dist')
    if not dist_dir.exists():
        logger.error("❌ Директория dist не найдена")
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"WorkTimeTracker_Windows_{timestamp}.zip"
    archive_path = Path(archive_name)
    
    apps = [
        'WorkTimeTracker_User',
        'WorkTimeTracker_Admin',
        'WorkTimeTracker_Monitor',
        'WorkTimeTracker_Bot',
    ]
    
    try:
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Добавляем каждое приложение
            for app in apps:
                app_dir = dist_dir / app
                if app_dir.exists():
                    logger.info(f"📦 Добавление {app}...")
                    for file_path in app_dir.rglob('*'):
                        if file_path.is_file():
                            arcname = file_path.relative_to(dist_dir)
                            zipf.write(file_path, arcname)
                            logger.debug(f"  Добавлен: {arcname}")
                else:
                    logger.warning(f"⚠ Приложение {app} не найдено в dist")
        
        size_mb = archive_path.stat().st_size / (1024 * 1024)
        logger.info(f"✅ Архив создан: {archive_path} ({size_mb:.2f} MB)")
        return archive_path
    except Exception as e:
        logger.error(f"❌ Ошибка создания архива: {e}", exc_info=True)
        return None

def main():
    """Главная функция"""
    logger.info("=" * 80)
    logger.info("🔨 СБОРКА WORKTIMETRACKER ДЛЯ WINDOWS")
    logger.info("=" * 80)
    
    # Проверка необходимых файлов
    if not check_required_files():
        logger.error("❌ Проверка файлов не пройдена. Прерывание сборки.")
        sys.exit(1)
    
    # Очистка старых сборок
    logger.info("🧹 Очистка старых сборок...")
    
    def handle_remove_readonly(func, path, exc):
        """Обработчик для удаления файлов с атрибутом readonly"""
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except Exception:
            # Если не удалось изменить права, просто пропускаем
            pass
    
    def safe_remove_tree(path: Path, max_retries: int = 3):
        """Безопасное удаление дерева с повторными попытками"""
        for attempt in range(max_retries):
            try:
                if path.exists():
                    shutil.rmtree(path, onerror=handle_remove_readonly)
                    return True
                return True
            except PermissionError as e:
                if attempt < max_retries - 1:
                    logger.debug(f"  Попытка {attempt + 1}/{max_retries} удаления {path}...")
                    time.sleep(1)  # Ждем секунду перед повторной попыткой
                else:
                    logger.warning(f"  ⚠ Не удалось удалить {path} после {max_retries} попыток: {e}")
                    logger.warning(f"  Возможно, файлы используются другим процессом или заблокированы антивирусом")
                    # Пытаемся переименовать папку вместо удаления
                    try:
                        old_name = path.name
                        new_name = f"{old_name}_old_{int(time.time())}"
                        path.rename(path.parent / new_name)
                        logger.info(f"  Переименована папка {old_name} → {new_name}")
                        return True
                    except Exception as e2:
                        logger.error(f"  ❌ Не удалось переименовать {path}: {e2}")
                        return False
            except Exception as e:
                logger.warning(f"  ⚠ Ошибка при удалении {path}: {e}")
                return False
        return False
    
    for dir_name in ['dist', 'build']:
        dir_path = Path(dir_name)
        if dir_path.exists():
            if safe_remove_tree(dir_path):
                logger.info(f"  ✓ Очищена директория: {dir_name}")
            else:
                logger.warning(f"  ⚠ Директория {dir_name} не удалена, но сборка продолжится")
                logger.warning(f"  Рекомендуется удалить папку {dir_name} вручную перед следующей сборкой")
    
    # Сборка всех компонентов
    results = {}
    results['user'] = build_user_app()
    results['admin'] = build_admin_app()
    results['monitor'] = build_monitor_app()
    results['bot'] = build_bot_app()
    
    # Итоги
    logger.info("=" * 80)
    logger.info("📊 ИТОГИ СБОРКИ")
    logger.info("=" * 80)
    
    success_count = sum(1 for v in results.values() if v)
    total_count = len(results)
    
    for name, success in results.items():
        status = "✅ Успешно" if success else "❌ Ошибка"
        logger.info(f"  {name:10} : {status}")
    
    logger.info(f"\nУспешно собрано: {success_count}/{total_count}")
    
    if success_count == total_count:
        # Создаем архив
        archive_path = create_archive()
        if archive_path:
            logger.info("=" * 80)
            logger.info("🎉 СБОРКА ЗАВЕРШЕНА УСПЕШНО!")
            logger.info("=" * 80)
            logger.info(f"📦 Архив: {archive_path.absolute()}")
            logger.info(f"📁 Директория dist: {Path('dist').absolute()}")
        else:
            logger.warning("⚠ Архив не создан, но сборки готовы в dist/")
    else:
        logger.error("=" * 80)
        logger.error("❌ СБОРКА ЗАВЕРШЕНА С ОШИБКАМИ")
        logger.error("=" * 80)
        sys.exit(1)

if __name__ == "__main__":
    main()
