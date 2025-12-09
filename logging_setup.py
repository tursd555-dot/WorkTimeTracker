
# logging_setup.py
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
import re
from typing import Optional, Union

_LOGGING_INITIALIZED = False
_ROOT_LOGGER_CONFIGURED = False

def _mask_pii(msg: str) -> str:
    # простое маскирование email и телефонов
    msg = re.sub(r'([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})', r'***@\2', msg)
    msg = re.sub(r'\+?\d[\d\s\-()]{6,}\d', '***PHONE***', msg)
    return msg

class PIIFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _mask_pii(record.msg)
        return True

def _configure_root_logger(level: int, handler: logging.Handler) -> None:
    global _ROOT_LOGGER_CONFIGURED
    root = logging.getLogger()
    if _ROOT_LOGGER_CONFIGURED:
        # избегаем дублирования хендлеров при повторных запусках из CLI
        for h in list(root.handlers):
            root.removeHandler(h)
    root.setLevel(level)
    root.addHandler(handler)
    _ROOT_LOGGER_CONFIGURED = True

def _setup_logging_impl(app_name: str,
                       log_dir: Union[str, Path],
                       level: int = logging.INFO,
                       rotate_mb: int = 5,
                       backup_count: int = 5) -> logging.Logger:
    """
    Реальная реализация настройки логирования.
    """
    global _LOGGING_INITIALIZED
    
    dir_path = Path(log_dir)
    dir_path.mkdir(parents=True, exist_ok=True)
    log_path = dir_path / f"{app_name}.log"
    
    # Настройка корневого логгера
    if not _LOGGING_INITIALIZED:
        root = logging.getLogger()
        root.setLevel(logging.DEBUG)
        # Удаляем все старые хендлеры один раз
        for h in list(root.handlers):
            root.removeHandler(h)
        
        # Глушим болтливые сторонние либы
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("google").setLevel(logging.WARNING)
        logging.getLogger("gspread").setLevel(logging.INFO)
        logging.captureWarnings(True)
        
        _LOGGING_INITIALIZED = True

    # Создаем хендлер для файла
    fmt = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    fh = RotatingFileHandler(
        log_path, 
        maxBytes=rotate_mb * 1024 * 1024, 
        backupCount=backup_count, 
        encoding="utf-8"
    )
    fh.setLevel(level)
    fh.setFormatter(fmt)
    fh.addFilter(PIIFilter())
    
    # Добавляем хендлер к корневому логгеру
    _configure_root_logger(level, fh)

    # Консоль — только если переменная окружения DEBUG_CONSOLE=1
    if os.getenv("DEBUG_CONSOLE") == "1":
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(level)
        ch.setFormatter(fmt)
        ch.addFilter(PIIFilter())
        logging.getLogger().addHandler(ch)
    
    # Получаем и возвращаем логгер для приложения
    logger = logging.getLogger(app_name)
    logger.info("Logging initialized (path=%s)", log_path)
    return logger

def setup_logging(*, 
                 app_name: str = "wtt-app",
                 log_dir: Optional[Union[str, Path]] = None,
                 level: int = logging.INFO,
                 rotate_mb: int = 5,
                 backup_count: int = 5) -> logging.Logger:
    """
    НОВАЯ ВЕРСИЯ: имя приложения + папка логов. Возвращает логгер.
    Совместима с вызовами вида:
        setup_logging(app_name="wtt-admin", log_dir=LOG_DIR)
    """
    # Импортируем LOG_DIR из config если log_dir не указан
    if log_dir is None:
        from config import LOG_DIR
        log_dir = LOG_DIR
    
    return _setup_logging_impl(
        app_name=app_name,
        log_dir=log_dir,
        level=level,
        rotate_mb=rotate_mb,
        backup_count=backup_count
    )

def setup_logging_compat(*args, **kwargs) -> logging.Logger:
    """
    Совместимый враппер для старых вызовов.
    Поддерживает:
      - setup_logging_compat("wtt-admin", LOG_DIR)
      - setup_logging_compat(app_name="wtt-admin", log_dir=LOG_DIR)
    """
    if kwargs:
        # Если переданы именованные аргументы - используем новую сигнатуру
        return setup_logging(**kwargs)
    
    # Обработка позиционных аргументов для обратной совместимости
    name = args[0] if len(args) > 0 else "wtt-app"
    logfile = args[1] if len(args) > 1 else None
    level = args[2] if len(args) > 2 else logging.INFO
    
    log_dir = Path(logfile).parent if logfile else None
    return setup_logging(app_name=str(name), log_dir=log_dir, level=level)

def get_logger(app_name: str = "wtt-app") -> logging.Logger:
    """
    Возвращает логгер с указанным именем приложения.
    Упрощенный интерфейс для получения логгера.
    """
    return logging.getLogger(app_name)

__all__ = ["setup_logging", "setup_logging_compat", "get_logger"]