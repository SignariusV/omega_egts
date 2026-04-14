"""Тесты для Config — вложенная конфигурация с JSON и CLI override."""

import json
import tempfile

import pytest

from core.config import (
    CmwConfig,
    Config,
    LogConfig,
    TimeoutsConfig,
)

# --- Дефолты ---


class TestConfigDefaults:
    """Config использует правильные значения по умолчанию."""

    def test_top_level_defaults(self) -> None:
        """Поля верхнего уровня имеют верные дефолты."""
        cfg = Config()
        assert cfg.gost_version == "2015"
        assert cfg.tcp_host == "0.0.0.0"
        assert cfg.tcp_port == 8090
        assert cfg.credentials_path == "config/credentials.json"

    def test_cmw_defaults(self) -> None:
        """CMW-конфиг имеет верные дефолты."""
        cfg = Config()
        assert cfg.cmw500.ip == "192.168.2.2"  # Дефолтный IP CMW-500
        assert cfg.cmw500.timeout == 5.0
        assert cfg.cmw500.retries == 3
        assert cfg.cmw500.sms_send_timeout == 10.0
        assert cfg.cmw500.status_poll_interval == 2.0

    def test_timeouts_defaults(self) -> None:
        """Таймауты протокола имеют верные дефолты."""
        cfg = Config()
        assert cfg.timeouts.tl_response_to == 5.0
        assert cfg.timeouts.tl_resend_attempts == 3
        assert cfg.timeouts.tl_reconnect_to == 30.0
        assert cfg.timeouts.egts_sl_not_auth_to == 6.0

    def test_logging_defaults(self) -> None:
        """Настройки логирования имеют верные дефолты."""
        cfg = Config()
        assert cfg.logging.level == "INFO"
        assert cfg.logging.dir == "logs"
        assert cfg.logging.rotation == "daily"
        assert cfg.logging.max_size_mb == 100
        assert cfg.logging.retention_days == 30


# --- Загрузка из JSON ---


class TestConfigFromFile:
    """Загрузка конфигурации из JSON-файла."""

    def test_from_file_loads_values(self) -> None:
        """from_file() загружает JSON и создаёт Config."""
        data = {
            "tcp_port": 9090,
            "gost_version": "2023",
            "cmw500": {
                "ip": "10.0.0.1",
                "timeout": 15,
            },
            "timeouts": {
                "tl_response_to": 10,
            },
            "logging": {
                "level": "DEBUG",
                "dir": "/tmp/logs",
            },
            "credentials_path": "/etc/egts/creds.json",
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name

        cfg = Config.from_file(path)

        assert cfg.tcp_port == 9090
        assert cfg.gost_version == "2023"
        assert cfg.cmw500.ip == "10.0.0.1"
        assert cfg.cmw500.timeout == 15.0
        assert cfg.timeouts.tl_response_to == 10.0
        assert cfg.logging.level == "DEBUG"
        assert cfg.logging.dir == "/tmp/logs"
        assert cfg.credentials_path == "/etc/egts/creds.json"
        # Поля, которых не было в JSON — из дефолтов
        assert cfg.cmw500.retries == 3
        assert cfg.timeouts.tl_reconnect_to == 30.0

    def test_from_file_not_found(self) -> None:
        """from_file() выбрасывает FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            Config.from_file("несуществующий_файл.json")

    def test_from_file_partial_json(self) -> None:
        """Пустой JSON даёт Config со значениями по умолчанию."""
        data: dict[str, object] = {}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name

        cfg = Config.from_file(path)

        # Все дефолты
        assert cfg.tcp_port == 8090
        assert cfg.cmw500.timeout == 5.0
        assert cfg.timeouts.tl_response_to == 5.0
        assert cfg.logging.level == "INFO"

    def test_from_file_ignores_extra_keys(self) -> None:
        """Неизвестные ключи JSON игнорируются."""
        data = {
            "tcp_port": 9090,
            "unknown_key": "ignore_me",
            "cmw500": {"phantom_field": 42},
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name

        cfg = Config.from_file(path)
        assert cfg.tcp_port == 9090


# --- Frozen (неизменяемость) ---


class TestConfigFrozen:
    """Config — замороженный dataclass, поля нельзя менять."""

    def test_config_is_frozen(self) -> None:
        """Попытка изменить поле вызывает FrozenInstanceError."""
        cfg = Config()
        with pytest.raises(AttributeError):  # frozen dataclass даёт AttributeError
            cfg.tcp_port = 9999  # type: ignore[misc]

    def test_nested_config_is_frozen(self) -> None:
        """Вложенные конфиги тоже заморожены."""
        cfg = Config()
        with pytest.raises(AttributeError):
            cfg.cmw500.timeout = 99.0  # type: ignore[misc]


# --- CLI override ---


class TestMergeWithCli:
    """merge_with_cli() переопределяет поля из dict."""

    def test_override_top_level(self) -> None:
        """CLI переопределяет поля верхнего уровня."""
        cfg = Config(tcp_port=3001)
        merged = cfg.merge_with_cli({"tcp_port": 9090})
        assert merged.tcp_port == 9090
        # Оригинал не изменился
        assert cfg.tcp_port == 3001

    def test_override_nested_dot_notation(self) -> None:
        """CLI переопределяет вложенные поля через dot-notation."""
        cfg = Config()
        merged = cfg.merge_with_cli({"cmw500.timeout": 15.0})
        assert merged.cmw500.timeout == 15.0
        # Остальные поля cmw500 — из оригинала
        assert merged.cmw500.retries == 3
        assert merged.cmw500.ip == "192.168.2.2"

    def test_override_multiple_nested(self) -> None:
        """CLI может переопределить несколько вложенных полей."""
        cfg = Config()
        merged = cfg.merge_with_cli({
            "cmw500.ip": "10.0.0.1",
            "timeouts.tl_response_to": 20.0,
            "logging.level": "DEBUG",
        })
        assert merged.cmw500.ip == "10.0.0.1"
        assert merged.timeouts.tl_response_to == 20.0
        assert merged.logging.level == "DEBUG"

    def test_empty_cli_returns_copy(self) -> None:
        """Пустой CLI-merge возвращает идентичный Config."""
        cfg = Config(tcp_port=3001)
        merged = cfg.merge_with_cli({})
        assert merged.tcp_port == 3001
        assert merged is not cfg  # новый экземпляр


# --- Валидация ---


class TestConfigValidation:
    """Валидация параметров в __post_init__."""

    def test_port_too_low(self) -> None:
        """tcp_port < 1 выбрасывает ValueError."""
        with pytest.raises(ValueError, match="tcp_port"):
            Config(tcp_port=0)

    def test_port_too_high(self) -> None:
        """tcp_port > 65535 выбрасывает ValueError."""
        with pytest.raises(ValueError, match="tcp_port"):
            Config(tcp_port=65536)

    def test_valid_port_min(self) -> None:
        """tcp_port=1 допустим."""
        cfg = Config(tcp_port=1)
        assert cfg.tcp_port == 1

    def test_valid_port_max(self) -> None:
        """tcp_port=65535 допустим."""
        cfg = Config(tcp_port=65535)
        assert cfg.tcp_port == 65535

    def test_negative_timeout(self) -> None:
        """Отрицательный таймаут выбрасывает ValueError."""
        with pytest.raises(ValueError, match="tl_response_to"):
            Config(timeouts=TimeoutsConfig(tl_response_to=-1.0))

    def test_zero_retries_allowed(self) -> None:
        """retries=0 допустим."""
        cfg = Config(cmw500=CmwConfig(retries=0))
        assert cfg.cmw500.retries == 0

    def test_negative_retries(self) -> None:
        """retries < 0 выбрасывает ValueError."""
        with pytest.raises(ValueError, match="retries"):
            Config(cmw500=CmwConfig(retries=-1))

    def test_invalid_log_level(self) -> None:
        """Недопустимый уровень логов выбрасывает ValueError."""
        with pytest.raises(ValueError, match="logging.level"):
            Config(logging=LogConfig(level="DEBGU"))

    def test_valid_log_levels(self) -> None:
        """Допустимые уровни логов принимаются."""
        for level in ("DEBUG", "INFO", "WARNING", "ERROR"):
            cfg = Config(logging=LogConfig(level=level))
            assert cfg.logging.level == level


# --- __str__ ---


class TestConfigStr:
    """__str__ даёт компактное представление."""

    def test_str_with_cmw_ip(self) -> None:
        """Строка содержит IP CMW, если настроен."""
        cfg = Config(tcp_port=9090, gost_version="2023", cmw500=CmwConfig(ip="10.0.0.1"))
        s = str(cfg)
        assert "gost=2023" in s
        assert "tcp=0.0.0.0:9090" in s
        assert "cmw=10.0.0.1" in s

    def test_str_without_cmw_ip(self) -> None:
        """Строка показывает IP CMW когда он настроен."""
        cfg = Config()
        s = str(cfg)
        assert "cmw=192.168.2.2" in s


# --- Sub-dataclasses standalone ---


class TestSubDataclasses:
    """Вложенные dataclass'ы можно создавать отдельно."""

    def test_cmw_config_standalone(self) -> None:
        """CmwConfig создаётся без Config."""
        cmw = CmwConfig(ip="10.0.0.1", timeout=10.0)
        assert cmw.ip == "10.0.0.1"
        assert cmw.timeout == 10.0

    def test_timeouts_config_standalone(self) -> None:
        """TimeoutsConfig создаётся без Config."""
        to = TimeoutsConfig(tl_response_to=10.0)
        assert to.tl_response_to == 10.0

    def test_log_config_standalone(self) -> None:
        """LogConfig создаётся без Config."""
        log = LogConfig(level="DEBUG")
        assert log.level == "DEBUG"
