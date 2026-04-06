"""Config — вложенная конфигурация с загрузкой из JSON и CLI override."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CmwConfig:
    """Настройки CMW-500."""

    ip: str | None = None
    timeout: float = 5.0
    retries: int = 3
    sms_send_timeout: float = 10.0
    status_poll_interval: float = 2.0


@dataclass(frozen=True)
class TimeoutsConfig:
    """Таймауты протокола EGTS."""

    tl_response_to: float = 5.0
    tl_resend_attempts: int = 3
    tl_reconnect_to: float = 30.0
    egts_sl_not_auth_to: float = 6.0


@dataclass(frozen=True)
class LogConfig:
    """Настройки логирования."""

    level: str = "INFO"
    dir: str = "logs"
    rotation: str = "daily"
    max_size_mb: int = 100
    retention_days: int = 30


def _validate_cmw(cmw: CmwConfig) -> None:
    """Валидация настроек CMW-500."""
    if cmw.retries < 0:
        raise ValueError(f"cmw500.retries не может быть отрицательным, получено {cmw.retries}")
    if cmw.timeout <= 0:
        raise ValueError(f"cmw500.timeout должен быть > 0, получено {cmw.timeout}")
    if cmw.sms_send_timeout <= 0:
        raise ValueError(f"cmw500.sms_send_timeout должен быть > 0, получено {cmw.sms_send_timeout}")
    if cmw.status_poll_interval <= 0:
        raise ValueError(f"cmw500.status_poll_interval должен быть > 0, получено {cmw.status_poll_interval}")


def _validate_timeouts(timeouts: TimeoutsConfig) -> None:
    """Валидация таймаутов протокола."""
    if timeouts.tl_response_to <= 0:
        raise ValueError(f"timeouts.tl_response_to должен быть > 0, получено {timeouts.tl_response_to}")
    if timeouts.tl_reconnect_to <= 0:
        raise ValueError(f"timeouts.tl_reconnect_to должен быть > 0, получено {timeouts.tl_reconnect_to}")
    if timeouts.egts_sl_not_auth_to <= 0:
        raise ValueError(f"timeouts.egts_sl_not_auth_to должен быть > 0, получено {timeouts.egts_sl_not_auth_to}")
    if timeouts.tl_resend_attempts < 1:
        raise ValueError(f"timeouts.tl_resend_attempts должен быть >= 1, получено {timeouts.tl_resend_attempts}")


_VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR"})


def _validate_log(log: LogConfig) -> None:
    """Валидация настроек логирования."""
    if log.level not in _VALID_LOG_LEVELS:
        raise ValueError(
            f"logging.level должен быть одним из {_VALID_LOG_LEVELS}, получено {log.level!r}"
        )
    if log.max_size_mb <= 0:
        raise ValueError(f"logging.max_size_mb должен быть > 0, получено {log.max_size_mb}")
    if log.retention_days < 0:
        raise ValueError(f"logging.retention_days не может быть отрицательным, получено {log.retention_days}")


@dataclass(frozen=True)
class Config:
    """Корневая конфигурация системы.

    Структура вложенная (nested dataclass'ы) — 1:1 с settings.json.
    """

    gost_version: str = "2015"
    tcp_host: str = "0.0.0.0"
    tcp_port: int = 8090
    cmw500: CmwConfig = field(default_factory=CmwConfig)
    timeouts: TimeoutsConfig = field(default_factory=TimeoutsConfig)
    logging: LogConfig = field(default_factory=LogConfig)
    credentials_path: str = "config/credentials.json"

    def __post_init__(self) -> None:
        """Валидация после создания."""
        if not (1 <= self.tcp_port <= 65535):
            raise ValueError(f"tcp_port должен быть в диапазоне 1–65535, получено {self.tcp_port}")
        _validate_cmw(self.cmw500)
        _validate_timeouts(self.timeouts)
        _validate_log(self.logging)

    @classmethod
    def from_file(cls, path: str) -> Config:
        """Загрузить конфигурацию из JSON-файла.

        Структура JSON соответствует полям Config (включая вложенные секции).
        Неизвестные ключи игнорируются.

        Args:
            path: Путь к JSON-файлу.

        Returns:
            Экземпляр Config.

        Raises:
            FileNotFoundError: Если файл не найден.
        """
        file = Path(path)
        if not file.exists():
            raise FileNotFoundError(f"Файл конфигурации не найден: {path}")

        raw = json.loads(file.read_text(encoding="utf-8"))
        return cls._from_dict(raw)

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> Config:
        """Создать Config из dict, включая вложенные секции."""
        cmw_data = data.get("cmw500", {})
        timeouts_data = data.get("timeouts", {})
        logging_data = data.get("logging", {})

        return cls(
            gost_version=data.get("gost_version", cls.gost_version),
            tcp_host=data.get("tcp_host", cls.tcp_host),
            tcp_port=data.get("tcp_port", cls.tcp_port),
            cmw500=CmwConfig(
                ip=cmw_data.get("ip", CmwConfig.ip),
                timeout=float(cmw_data.get("timeout", CmwConfig.timeout)),
                retries=cmw_data.get("retries", CmwConfig.retries),
                sms_send_timeout=float(cmw_data.get("sms_send_timeout", CmwConfig.sms_send_timeout)),
                status_poll_interval=float(cmw_data.get("status_poll_interval", CmwConfig.status_poll_interval)),
            ),
            timeouts=TimeoutsConfig(
                tl_response_to=float(timeouts_data.get("tl_response_to", TimeoutsConfig.tl_response_to)),
                tl_resend_attempts=timeouts_data.get("tl_resend_attempts", TimeoutsConfig.tl_resend_attempts),
                tl_reconnect_to=float(timeouts_data.get("tl_reconnect_to", TimeoutsConfig.tl_reconnect_to)),
                egts_sl_not_auth_to=float(timeouts_data.get("egts_sl_not_auth_to", TimeoutsConfig.egts_sl_not_auth_to)),
            ),
            logging=LogConfig(
                level=logging_data.get("level", LogConfig.level),
                dir=logging_data.get("dir", LogConfig.dir),
                rotation=logging_data.get("rotation", LogConfig.rotation),
                max_size_mb=logging_data.get("max_size_mb", LogConfig.max_size_mb),
                retention_days=logging_data.get("retention_days", LogConfig.retention_days),
            ),
            credentials_path=data.get("credentials_path", cls.credentials_path),
        )

    def merge_with_cli(self, cli_args: dict[str, Any]) -> Config:
        """Создать новый Config с переопределениями из CLI.

        Поддерживает dot-notation для вложенных полей:
        ``"cmw500.timeout": 10`` → ``config.cmw500.timeout = 10``.

        Args:
            cli_args: Dict с переопределениями (например, из argparse).

        Returns:
            Новый экземпляр Config с применёнными изменениями.
        """
        if not cli_args:
            return replace(self)

        # Разбираем dot-notation: группируем по секциям
        top_level: dict[str, Any] = {}
        nested: dict[str, dict[str, Any]] = {"cmw500": {}, "timeouts": {}, "logging": {}}

        for key, value in cli_args.items():
            if "." in key:
                section, field = key.split(".", 1)
                if section in nested:
                    nested[section][field] = value
                else:
                    # Неизвестная секция — игнорируем
                    pass
            else:
                top_level[key] = value

        # Применяем изменения к вложенным секциям
        kwargs: dict[str, Any] = {}
        if top_level:
            kwargs.update(top_level)

        if nested["cmw500"]:
            kwargs["cmw500"] = replace(self.cmw500, **nested["cmw500"])
        if nested["timeouts"]:
            kwargs["timeouts"] = replace(self.timeouts, **nested["timeouts"])
        if nested["logging"]:
            kwargs["logging"] = replace(self.logging, **nested["logging"])

        return replace(self, **kwargs) if kwargs else replace(self)

    def __str__(self) -> str:
        """Компактное строковое представление для логов."""
        cmw_ip = self.cmw500.ip or "не настроен"
        return (
            f"Config(gost={self.gost_version}, "
            f"tcp={self.tcp_host}:{self.tcp_port}, "
            f"cmw={cmw_ip})"
        )
