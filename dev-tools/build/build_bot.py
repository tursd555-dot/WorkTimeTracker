
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

def _add_python_runtime_binaries(options):
    """Добавляет runtime DLL для надежного запуска на другом ПК (Windows)."""
    if os.name != "nt":
        return

    py_ver = f"python{sys.version_info.major}{sys.version_info.minor}.dll"
    wanted = {
        py_ver,
        "python3.dll",
        "vcruntime140.dll",
        "vcruntime140_1.dll",
        "msvcp140.dll",
    }

    search_dirs = [
        Path(sys.executable).resolve().parent,
        Path(sys.base_prefix),
        Path(sys.base_prefix) / "DLLs",
    ]

    added = set()
    for d in search_dirs:
        if not d.exists():
            continue
        for name in wanted:
            p = (d / name).resolve()
            if p.exists() and str(p) not in added:
                options.extend(["--add-binary", f"{p};."])
                added.add(str(p))

    if added:
        logger.info("✓ Добавлены runtime DLL: %s", ", ".join(sorted(Path(x).name for x in added)))
    else:
        logger.warning("⚠ Runtime DLL не найдены явно (на целевой машине может потребоваться VC++ runtime)")

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
        
        # Очистка только build директории (dist очищается в build_all_windows.py)
        build_dir = Path('build')
        if build_dir.exists():
            shutil.rmtree(build_dir)
            logger.info(f"🧹 Очищена директория: {build_dir}")
        
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

        # Критично для переносимости: добавляем python/vcruntime DLL
        _add_python_runtime_binaries(options)
        
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