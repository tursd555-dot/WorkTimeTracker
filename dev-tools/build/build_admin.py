
# build_admin.py
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
        logging.FileHandler('build_admin.log', mode='w', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    try:
        logger.info("🚀 Сборка админки...")
        app_name = "WorkTimeTracker_Admin"
        
        # Определяем корень проекта (на 2 уровня выше от dev-tools/build)
        project_root = Path(__file__).parent.parent.parent.resolve()
        main_script = project_root / "admin_app" / "main_admin.py"
        icon_file = project_root / "user_app" / "sberhealf.ico"
        
        # Переходим в корень проекта
        os.chdir(str(project_root))
        
        # Очистка
        for dir_name in ['dist', 'build']:
            if Path(dir_name).exists():
                shutil.rmtree(dir_name)
                logger.info(f"🧹 Очищена директория: {dir_name}")

        # Проверка существования файлов
        if not main_script.exists():
            logger.critical(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {main_script} не найден!")
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
            ('secret_creds.zip', '.'),
            ('config.py', '.'),
        ]
        
        for src, dst in data_files:
            src_path = project_root / src
            if src_path.exists():
                options.extend(['--add-data', f'{src_path};{dst}'])
            else:
                logger.warning(f"⚠ Файл не найден: {src_path}")
        
        # Добавляем PNG иконку, если существует
        png_icon = project_root / "user_app" / "sberhealf.png"
        if png_icon.exists():
            options.extend(['--add-data', f'{png_icon};user_app'])
        
        # Скрытые импорты
        hidden_imports = [
            'auto_sync',
            'sheets_api',
            'supabase_api',
            'user_app.db_local',
            'admin_app',
            'admin_app.repo',
            'admin_app.break_manager',
            'admin_app.reports_tab',
            'shared',
            'sync',
            'PyQt5',
            'PyQt5.QtCore',
            'PyQt5.QtWidgets',
            'PyQt5.QtGui',
            # Для экспорта в Excel
            'openpyxl',
            'openpyxl.styles',
            'openpyxl.utils',
            'openpyxl.workbook',
            'openpyxl.worksheet',
            # Для работы с Supabase
            'supabase',
            'supabase.client',
            'postgrest',
            'realtime',
            'storage',
            'gotrue',
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