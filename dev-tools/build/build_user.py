
# build_user.py
import os
import sys
import logging
import shutil
from pathlib import Path
from PyInstaller.__main__ import run

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('build_user.log', mode='w', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    try:
        logger.info("🚀 Сборка пользовательской части...")
        app_name = "WorkTimeTracker_User"
        
        # Определяем корень проекта (на 2 уровня выше от dev-tools/build)
        project_root = Path(__file__).parent.parent.parent.resolve()
        main_script = project_root / "user_app" / "main.py"
        icon_file = project_root / "user_app" / "sberhealf.ico"
        
        # Переходим в корень проекта
        os.chdir(str(project_root))
        
        # Очистка только build директории (dist очищается в build_all_windows.py)
        build_dir = Path('build')
        if build_dir.exists():
            shutil.rmtree(build_dir)
            logger.info(f"🧹 Очищена директория: {build_dir}")

        # Проверка существования файлов
        required_files = [
            'config.py',
        ]
        
        # Опциональные файлы (предупреждение, но не ошибка)
        optional_files = [
            'secret_creds.zip',
        ]
        
        missing_files = []
        for file in required_files:
            file_path = project_root / file
            if not file_path.exists():
                missing_files.append(file)
        
        if missing_files:
            logger.critical(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Отсутствуют необходимые файлы: {', '.join(missing_files)}")
            sys.exit(1)
        
        # Проверка опциональных файлов (только предупреждение)
        for file in optional_files:
            file_path = project_root / file
            if not file_path.exists():
                logger.warning(f"⚠ Опциональный файл не найден: {file} (будет пропущен при сборке)")
        
        # Проверка директорий
        required_dirs = ['user_app', 'sync']
        missing_dirs = []
        for dir_name in required_dirs:
            dir_path = project_root / dir_name
            if not dir_path.is_dir():
                missing_dirs.append(dir_name)
        
        if missing_dirs:
            logger.critical(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Отсутствуют необходимые директории: {', '.join(missing_dirs)}")
            sys.exit(1)

        options = [
            str(main_script),
            f'--name={app_name}',
            '--onedir',
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
        
        # Добавляем данные
        data_files = [
            ('config.py', '.'),
        ]
        
        # Опциональные файлы
        optional_data_files = [
            ('secret_creds.zip', '.'),
            ('auto_sync.py', '.'),
            ('sheets_api.py', '.'),
        ]
        
        # Обязательные директории
        data_dirs = [
            ('user_app', 'user_app'),
            ('sync', 'sync'),
        ]
        
        for src, dst in data_files:
            src_path = project_root / src
            if src_path.exists():
                options.extend(['--add-data', f'{src_path};{dst}'])
            else:
                logger.warning(f"⚠ Файл не найден: {src_path}")
        
        for src, dst in optional_data_files:
            src_path = project_root / src
            if src_path.exists():
                options.extend(['--add-data', f'{src_path};{dst}'])
        
        for src, dst in data_dirs:
            src_path = project_root / src
            if src_path.exists():
                options.extend(['--add-data', f'{src_path};{dst}'])
            else:
                logger.warning(f"⚠ Директория не найдена: {src_path}")
        
        # Скрытые импорты
        hidden_imports = [
            'PyQt5',
            'PyQt5.QtCore',
            'PyQt5.QtWidgets',
            'PyQt5.QtGui',
            'user_app',
            'user_app.db_local',
            'user_app.gui',
            'user_app.login_window',
            'auto_sync',
            'api_adapter',
            'supabase_api',
            'sync',
            'sync.notifications',
            'shared',
            'shared.time_utils',
            'notifications',
            'notifications.engine',
            # Google Sheets импорты (опционально, если не используется Supabase)
            # 'gspread',
            # 'oauth2client',
            # 'google.auth',
            # 'googleapiclient',
            # 'google.oauth2',
            # 'googleapiclient.discovery',
            # 'httplib2',
            # 'OpenSSL',
            'requests',
        ]
        
        for imp in hidden_imports:
            options.extend(['--hidden-import', imp])

        logger.info(f"⚙️ Запуск PyInstaller...")
        logger.debug(f"Опции: {' '.join(options)}")
        run(options)

        exe_path = Path('dist') / app_name / f"{app_name}.exe"
        if exe_path.exists():
            logger.info(f"✅ Успех! {exe_path}")
        else:
            raise RuntimeError("Сборка прошла, но exe не найден.")

    except Exception as e:
        logger.critical(f"❌ Ошибка: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()