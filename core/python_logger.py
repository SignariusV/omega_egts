"""Настройка Python-логирования для всего приложения."""

import logging
import logging.handlers
import sys
from datetime import datetime
from pathlib import Path

_LOGGING_INITIALIZED = False
_current_session_id: str | None = None


def setup_python_logging(
    log_dir: str | Path = "logs",
    console_level: str = "ERROR",
    file_level: str = "DEBUG",
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    force_new: bool = False,
) -> str:
    """Настроить Python-логирование для новой сессии.

    Args:
        log_dir: Директория для логов
        console_level: Уровень логирования в консоль (ERROR, WARNING, INFO, DEBUG)
        file_level: Уровень логирования в файл
        max_bytes: Максимальный размер файла до ротации (по умолч. 10 MB)
        backup_count: Количествоbackup-файлов при ротации
        force_new: Принудительно создать новую сессию

    Returns:
        session_id: Идентификатор сессии
    """
    global _LOGGING_INITIALIZED, _current_session_id

    if _LOGGING_INITIALIZED and not force_new:
        return _current_session_id or ""

    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    _LOGGING_INITIALIZED = True

    session_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_file = log_dir / f"python-{session_id}.log"

    formatter = logging.Formatter(
        fmt="%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logging.root.handlers.clear()

    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(_str_to_level(file_level))
    file_handler.setFormatter(formatter)
    logging.root.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(_str_to_level(console_level))
    console_handler.setFormatter(formatter)
    logging.root.addHandler(console_handler)

    logging.root.setLevel(logging.DEBUG)

    # Убираем verbose логи от pyvisa
    logging.getLogger("pyvisa").setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("Python logging initialized")
    logger.info(f"Session ID: {session_id}")
    logger.info(f"Log file: {log_file}")
    logger.info(f"Console level: {console_level}, File level: {file_level}")
    logger.info(f"Rotation: {max_bytes} bytes, {backup_count} backups")
    logger.info("=" * 60)

    _cleanup_old_logs(log_dir, keep_count=10)

    return session_id


def get_session_id() -> str:
    """Вернуть ID текущей сессии."""
    return _current_session_id or ""


def get_log_dir() -> Path:
    """Вернуть директорию логов."""
    return _log_dir


def _cleanup_old_logs(log_dir: Path, keep_count: int = 10) -> None:
    """Удалить старые лог-файлы.

    Args:
        log_dir: Директория с логами
        keep_count: Сколько файлов оставить
    """
    log_files = sorted(log_dir.glob("python-*.log"), key=lambda p: p.stat().st_mtime, reverse=True)

    for old_file in log_files[keep_count:]:
        try:
            old_file.unlink()
        except OSError:
            pass


def _str_to_level(level: str) -> int:
    """Преобразовать строку в уровень логирования."""
    levels: dict[str, int] = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    return levels.get(level.upper(), logging.INFO)
