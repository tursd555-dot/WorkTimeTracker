
# build_bot.py
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
        logging.FileHandler('build_bot.log', mode='w', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    try:
        logger.info("🚀 Сборка Telegram бота...")
        app_name = "WorkTimeTracker_Bot"
        
        # Определяем корень проекта (на 2 уровня выше от dev-tools/build)
        project_root = Path(__file__).parent.parent.parent.resolve()
        main_script = project_root / "bot_launcher.py"
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
        
        # Добавляем данные
        data_files = [
            ('config.py', '.'),
        ]
        
        # Опциональные файлы
        optional_data_files = [
            ('secret_creds.zip', '.'),
        ]
        
        # Обязательные директории
        data_dirs = [
            ('telegram_bot', 'telegram_bot'),
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
        
        # Добавляем .env, если существует
        env_file = project_root / '.env'
        if env_file.exists():
            options.extend(['--add-data', f'{env_file};.'])
        
        # Скрытые импорты
        hidden_imports = [
            'PyQt5',
            'PyQt5.QtCore',
            'PyQt5.QtWidgets',
            'PyQt5.QtGui',
            'telegram_bot',
            'telegram_bot.main',
            'telegram_bot.monitor_bot',
            'telegram_bot.notifier',
            'subprocess',
            'threading',
            'supabase_api',
            'shared.time_utils',
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