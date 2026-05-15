"""Тесты для Config — вложенная конфигурация с JSON и CLI override."""

import json
import tempfile

import pytest

from core.config import (
    CmwConfig,
    Config,
    LogConfig,
    TimeoutsConfig,
    VehicleConfig,
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


# --- Новые поля CmwConfig (ТЗ п. 2.1.1, 2.1.2) ---


class TestNewCmwConfigFields:
    """Тесты новых полей CmwConfig."""

    def test_visa_resource_default(self) -> None:
        cmw = CmwConfig()
        assert cmw.visa_resource == "TCPIP::192.168.2.2::inst0::INSTR"

    def test_network_type_default(self) -> None:
        cmw = CmwConfig()
        assert cmw.network_type == "GSM/EDGE"

    def test_ps_domain_default(self) -> None:
        cmw = CmwConfig()
        assert cmw.ps_domain is True

    def test_gsm_auth_default(self) -> None:
        cmw = CmwConfig()
        assert cmw.gsm_auth is False

    def test_frequency_band_default(self) -> None:
        cmw = CmwConfig()
        assert cmw.frequency_band == "900"

    def test_voice_codec_default(self) -> None:
        cmw = CmwConfig()
        assert cmw.voice_codec == "FR"

    def test_arfcn_defaults(self) -> None:
        cmw = CmwConfig()
        assert cmw.arfcn_bch == 0
        assert cmw.arfcn_tch == 0

    def test_rf_level_range_defaults(self) -> None:
        cmw = CmwConfig()
        assert cmw.rf_level_min == -30.0
        assert cmw.rf_level_max == 30.0

    def test_pcl_value_default(self) -> None:
        cmw = CmwConfig()
        assert cmw.pcl_value == "MAX"

    def test_profile_imsi_default(self) -> None:
        cmw = CmwConfig()
        assert cmw.profile_imsi == ""

    def test_smsc_number_default(self) -> None:
        cmw = CmwConfig()
        assert cmw.smsc_number == ""

    def test_network_ip_defaults(self) -> None:
        cmw = CmwConfig()
        assert cmw.dau_ip == "192.168.2.1"
        assert cmw.dau_subnet_mask == "255.255.255.0"
        assert cmw.test_system_ip == "192.168.2.100"
        assert cmw.usv_dhcp_ip == "192.168.2.200"

    def test_mnc_default_is_77(self) -> None:
        """ТЗ: NID=25077, mnc=77."""
        cmw = CmwConfig()
        assert cmw.mnc == 77

    def test_mcc_default_is_250(self) -> None:
        """ТЗ: NID=25077, mcc=250."""
        cmw = CmwConfig()
        assert cmw.mcc == 250


# --- VehicleConfig ---


class TestVehicleConfig:
    """Тесты VehicleConfig (ТЗ п. 2.1.4)."""

    def test_defaults(self) -> None:
        v = VehicleConfig()
        assert v.vin == ""
        assert v.category == ""
        assert v.fuel_type == ""

    def test_custom_values(self) -> None:
        v = VehicleConfig(vin="WBA12345678901234", category="M1", fuel_type="бензин")
        assert v.vin == "WBA12345678901234"
        assert v.category == "M1"
        assert v.fuel_type == "бензин"

    def test_is_frozen(self) -> None:
        v = VehicleConfig()
        with pytest.raises(AttributeError):
            v.vin = "test"  # type: ignore[misc]


# --- Валидация MCC/MNC (ТЗ: не корректируемы) ---


class TestMccMncValidation:
    """MCC=250 и MNC=77 — не корректируемы (ТЗ п. 2.1.2 в)."""

    def test_mcc_not_250_raises(self) -> None:
        with pytest.raises(ValueError, match="mcc.*250"):
            Config(cmw500=CmwConfig(mcc=255))

    def test_mnc_not_77_raises(self) -> None:
        with pytest.raises(ValueError, match="mnc.*77"):
            Config(cmw500=CmwConfig(mnc=60))

    def test_valid_mcc_mnc(self) -> None:
        cfg = Config(cmw500=CmwConfig(mcc=250, mnc=77))
        assert cfg.cmw500.mcc == 250
        assert cfg.cmw500.mnc == 77


# --- Валидация frequency_band ---


class TestFrequencyBandValidation:
    """frequency_band ∈ {900, 1800}."""

    def test_invalid_band_raises(self) -> None:
        with pytest.raises(ValueError, match="frequency_band"):
            Config(cmw500=CmwConfig(frequency_band="2100"))

    def test_valid_900(self) -> None:
        cfg = Config(cmw500=CmwConfig(frequency_band="900"))
        assert cfg.cmw500.frequency_band == "900"

    def test_valid_1800(self) -> None:
        cfg = Config(cmw500=CmwConfig(frequency_band="1800"))
        assert cfg.cmw500.frequency_band == "1800"


# --- Валидация profile_imsi ---


class TestProfileImsiValidation:
    """profile_imsi должен начинаться с 25077."""

    def test_valid_prefix(self) -> None:
        cfg = Config(cmw500=CmwConfig(profile_imsi="250770000000001"))
        assert cfg.cmw500.profile_imsi == "250770000000001"

    def test_empty_allowed(self) -> None:
        cfg = Config(cmw500=CmwConfig(profile_imsi=""))
        assert cfg.cmw500.profile_imsi == ""

    def test_invalid_prefix_raises(self) -> None:
        with pytest.raises(ValueError, match="profile_imsi.*25077"):
            Config(cmw500=CmwConfig(profile_imsi="250011234567890"))


# --- Валидация IPv4-адресов ---


class TestIpv4Validation:
    """IPv4-адреса должны быть валидными."""

    def test_invalid_dau_ip(self) -> None:
        with pytest.raises(ValueError, match="dau_ip"):
            Config(cmw500=CmwConfig(dau_ip="999.999.999.999"))

    def test_invalid_subnet_mask(self) -> None:
        with pytest.raises(ValueError, match="dau_subnet_mask"):
            Config(cmw500=CmwConfig(dau_subnet_mask="not-an-ip"))

    def test_invalid_test_system_ip(self) -> None:
        with pytest.raises(ValueError, match="test_system_ip"):
            Config(cmw500=CmwConfig(test_system_ip="abc.def.ghi.jkl"))

    def test_invalid_usv_dhcp_ip(self) -> None:
        with pytest.raises(ValueError, match="usv_dhcp_ip"):
            Config(cmw500=CmwConfig(usv_dhcp_ip="300.1.2.3"))

    def test_valid_ips(self) -> None:
        cfg = Config(cmw500=CmwConfig(
            dau_ip="10.0.0.1",
            dau_subnet_mask="255.255.255.0",
            test_system_ip="10.0.0.100",
            usv_dhcp_ip="10.0.0.200",
        ))
        assert cfg.cmw500.dau_ip == "10.0.0.1"


# --- Валидация VehicleConfig ---


class TestVehicleValidation:
    """Валидация параметров ТС."""

    def test_invalid_vin_length(self) -> None:
        with pytest.raises(ValueError, match="vin.*17"):
            Config(vehicle=VehicleConfig(vin="TOOSHORT"))

    def test_valid_vin(self) -> None:
        cfg = Config(vehicle=VehicleConfig(vin="WBA12345678901234"))
        assert cfg.vehicle.vin == "WBA12345678901234"

    def test_empty_vin_allowed(self) -> None:
        cfg = Config(vehicle=VehicleConfig(vin=""))
        assert cfg.vehicle.vin == ""

    def test_invalid_category(self) -> None:
        with pytest.raises(ValueError, match="category"):
            Config(vehicle=VehicleConfig(category="X9"))

    def test_valid_categories(self) -> None:
        for cat in ("M1", "M2", "M3", "N1", "N2", "N3"):
            cfg = Config(vehicle=VehicleConfig(category=cat))
            assert cfg.vehicle.category == cat

    def test_empty_category_allowed(self) -> None:
        cfg = Config(vehicle=VehicleConfig(category=""))
        assert cfg.vehicle.category == ""


# --- Config.vehicle ---


class TestConfigVehicle:
    """vehicle в Config."""

    def test_vehicle_default(self) -> None:
        cfg = Config()
        assert cfg.vehicle.vin == ""
        assert cfg.vehicle.category == ""
        assert cfg.vehicle.fuel_type == ""

    def test_vehicle_custom(self) -> None:
        cfg = Config(vehicle=VehicleConfig(vin="WBA12345678901234", category="M1"))
        assert cfg.vehicle.vin == "WBA12345678901234"
        assert cfg.vehicle.category == "M1"


# --- from_file с новыми полями ---


class TestFromFileNewFields:
    """Загрузка новых полей из JSON."""

    def test_load_new_cmw_fields(self) -> None:
        data = {
            "cmw500": {
                "visa_resource": "TCPIP::10.0.0.1::inst0::INSTR",
                "network_type": "GSM/EDGE",
                "ps_domain": False,
                "gsm_auth": True,
                "frequency_band": "1800",
                "voice_codec": "HR",
                "arfcn_bch": 12,
                "arfcn_tch": 34,
                "profile_imsi": "250770000000001",
                "smsc_number": "+79001234567",
                "dau_ip": "10.0.0.1",
                "dau_subnet_mask": "255.255.255.0",
                "test_system_ip": "10.0.0.100",
                "usv_dhcp_ip": "10.0.0.200",
            },
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name

        cfg = Config.from_file(path)
        assert cfg.cmw500.visa_resource == "TCPIP::10.0.0.1::inst0::INSTR"
        assert cfg.cmw500.ps_domain is False
        assert cfg.cmw500.gsm_auth is True
        assert cfg.cmw500.frequency_band == "1800"
        assert cfg.cmw500.voice_codec == "HR"
        assert cfg.cmw500.arfcn_bch == 12
        assert cfg.cmw500.arfcn_tch == 34
        assert cfg.cmw500.profile_imsi == "250770000000001"
        assert cfg.cmw500.smsc_number == "+79001234567"
        assert cfg.cmw500.dau_ip == "10.0.0.1"
        assert cfg.cmw500.dau_subnet_mask == "255.255.255.0"
        assert cfg.cmw500.test_system_ip == "10.0.0.100"
        assert cfg.cmw500.usv_dhcp_ip == "10.0.0.200"

    def test_load_vehicle_from_file(self) -> None:
        data = {
            "vehicle": {
                "vin": "WBA12345678901234",
                "category": "M1",
                "fuel_type": "бензин",
            },
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name

        cfg = Config.from_file(path)
        assert cfg.vehicle.vin == "WBA12345678901234"
        assert cfg.vehicle.category == "M1"
        assert cfg.vehicle.fuel_type == "бензин"


# --- CLI merge для vehicle ---


class TestMergeVehicle:
    """merge_with_cli для vehicle."""

    def test_override_vehicle_field(self) -> None:
        cfg = Config()
        merged = cfg.merge_with_cli({"vehicle.vin": "WBA12345678901234"})
        assert merged.vehicle.vin == "WBA12345678901234"

    def test_override_multiple_vehicle_fields(self) -> None:
        cfg = Config()
        merged = cfg.merge_with_cli({
            "vehicle.vin": "WBA12345678901234",
            "vehicle.category": "N1",
        })
        assert merged.vehicle.vin == "WBA12345678901234"
        assert merged.vehicle.category == "N1"
