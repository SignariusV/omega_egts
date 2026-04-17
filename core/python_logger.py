"""Настройка Python-логирования для всего приложения."""

import logging
import sys
from pathlib import Path
from datetime import datetime


def setup_python_logging(
    log_dir: str | Path = "logs",
    console_level: str = "ERROR",
    file_level: str = "DEBUG",
) -> None:
    """Настроить Python-логирование.
    
    Args:
        log_dir: Директория для логов
        console_level: Уровень логирования в консоль (ERROR, WARNING, INFO, DEBUG)
        file_level: Уровень логирования в файл
    """
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Имя файла с датой: python-2026-04-17.log
    date_str = datetime.now().strftime("%Y-%m-%d")
    log_file = log_dir / f"python-{date_str}.log"
    
    # Форматтер для логов
    formatter = logging.Formatter(
        fmt='%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Очищаем существующие обработчики у корневого логгера
    logging.root.handlers.clear()
    
    # Файловый обработчик (все уровни)
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(_str_to_level(file_level))
    file_handler.setFormatter(formatter)
    logging.root.addHandler(file_handler)
    
    # Консольный обработчик (только ошибки)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(_str_to_level(console_level))
    console_handler.setFormatter(formatter)
    logging.root.addHandler(console_handler)
    
    # Устанавливаем общий уровень (самый детальный)
    logging.root.setLevel(logging.DEBUG)
    
    # Логируем старт
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("Python logging initialized")
    logger.info(f"Log file: {log_file}")
    logger.info(f"Console level: {console_level}, File level: {file_level}")
    logger.info("=" * 60)


def _str_to_level(level: str) -> int:
    """Преобразовать строку в уровень логирования."""
    levels = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    return levels.get(level.upper(), logging.INFO)