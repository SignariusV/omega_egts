"""Config — вложенная конфигурация с загрузкой из JSON и CLI override."""

from __future__ import annotations

import ipaddress
import json
import logging
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CmwConfig:
    """Настройки CMW-500 (ТЗ п. 2.1.1, 2.1.2)."""

    # Существующие поля
    ip: str | None = "192.168.2.2"
    simulate: bool = False
    timeout: float = 5.0
    retries: int = 3
    sms_send_timeout: float = 10.0
    status_poll_interval: float = 2.0

    mcc: int = 250
    mnc: int = 77  # ТЗ: NID=25077, не корректируемо
    rf_level_tch: float = -40.0
    ps_service: str = "TMA"
    ps_tlevel: str = "EGPRS"
    ps_cscheme_ul: str = "MC9"
    ps_dl_carrier: list[str] = field(
        default_factory=lambda: [
            "OFF",
            "OFF",
            "OFF",
            "ON",
            "ON",
            "OFF",
            "OFF",
            "OFF",
        ]
    )
    ps_dl_cscheme: list[str] = field(default_factory=lambda: ["MC9"] * 8)
    sms_dcoding: str = "BIT8"
    sms_pidentifier: int = 1

    # Новые поля (ТЗ 2.1.1)
    visa_resource: str = "TCPIP::192.168.2.2::inst0::INSTR"

    # Новые поля (ТЗ 2.1.2)
    network_type: str = "GSM/EDGE"
    ps_domain: bool = True
    gsm_auth: bool = False
    frequency_band: str = "900"
    voice_codec: str = "FR"
    arfcn_bch: int = 0
    arfcn_tch: int = 0
    rf_level_min: float = -30.0
    rf_level_max: float = 30.0
    pcl_value: str = "MAX"
    profile_imsi: str = ""
    smsc_number: str = ""
    dau_ip: str = "192.168.2.1"
    dau_subnet_mask: str = "255.255.255.0"
    test_system_ip: str = "192.168.2.100"
    usv_dhcp_ip: str = "192.168.2.200"


@dataclass(frozen=True)
class VehicleConfig:
    """Параметры ТС для аутентификации (ТЗ п. 2.1.4)."""

    vin: str = ""
    category: str = ""
    fuel_type: str = ""


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
    python_console_level: str = "ERROR"
    python_file_level: str = "DEBUG"


def _is_valid_ipv4(addr: str) -> bool:
    """Проверить, что строка — валидный IPv4-адрес."""
    try:
        ipaddress.IPv4Address(addr)
        return True
    except (ipaddress.AddressValueError, ValueError):
        return False


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

    # ТЗ п. 2.1.2 в): NID=MCC+MNC=25077, не корректируемы
    if cmw.mcc != 250:
        raise ValueError(f"cmw500.mcc должен быть 250 (ТЗ: NID=25077), получено {cmw.mcc}")
    if cmw.mnc != 77:
        raise ValueError(f"cmw500.mnc должен быть 77 (ТЗ: NID=25077), получено {cmw.mnc}")

    # ТЗ п. 2.1.2 д): диапазоны 900 или 1800 МГц
    if cmw.frequency_band not in {"900", "1800"}:
        raise ValueError(f"cmw500.frequency_band должен быть '900' или '1800', получено {cmw.frequency_band!r}")

    # ТЗ п. 2.1.2 л): IMSI профиля должен начинаться с NID=25077
    if cmw.profile_imsi and not cmw.profile_imsi.startswith("25077"):
        raise ValueError(
            f"cmw500.profile_imsi должен начинаться с '25077' (ТЗ: NID=25077), получено {cmw.profile_imsi!r}"
        )

    # Валидация IPv4-адресов (ТЗ п. 2.1.2 н, о, п, р)
    if cmw.dau_ip and not _is_valid_ipv4(cmw.dau_ip):
        raise ValueError(f"cmw500.dau_ip — невалидный IPv4: {cmw.dau_ip!r}")
    if cmw.dau_subnet_mask and not _is_valid_ipv4(cmw.dau_subnet_mask):
        raise ValueError(f"cmw500.dau_subnet_mask — невалидный IPv4: {cmw.dau_subnet_mask!r}")
    if cmw.test_system_ip and not _is_valid_ipv4(cmw.test_system_ip):
        raise ValueError(f"cmw500.test_system_ip — невалидный IPv4: {cmw.test_system_ip!r}")
    if cmw.usv_dhcp_ip and not _is_valid_ipv4(cmw.usv_dhcp_ip):
        raise ValueError(f"cmw500.usv_dhcp_ip — невалидный IPv4: {cmw.usv_dhcp_ip!r}")


def _validate_vehicle(v: VehicleConfig) -> None:
    """Валидация параметров ТС (ТЗ п. 2.1.4)."""
    if v.vin and len(v.vin) != 17:
        raise ValueError(f"vehicle.vin должен содержать 17 символов, получено {len(v.vin)}")
    if v.category and v.category not in {"M1", "M2", "M3", "N1", "N2", "N3"}:
        raise ValueError(f"vehicle.category — недопустимое значение: {v.category!r}")


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
        raise ValueError(f"logging.level должен быть одним из {_VALID_LOG_LEVELS}, получено {log.level!r}")
    if log.max_size_mb <= 0:
        raise ValueError(f"logging.max_size_mb должен быть > 0, получено {log.max_size_mb}")
    if log.retention_days < 0:
        raise ValueError(f"logging.retention_days не может быть отрицательным, получено {log.retention_days}")


@dataclass(frozen=True)
class Config:
    """Корневая конфигурация системы."""

    gost_version: str = "2015"
    tcp_host: str = "0.0.0.0"
    tcp_port: int = 8090
    cmw500: CmwConfig = field(default_factory=CmwConfig)
    timeouts: TimeoutsConfig = field(default_factory=TimeoutsConfig)
    logging: LogConfig = field(default_factory=LogConfig)
    vehicle: VehicleConfig = field(default_factory=VehicleConfig)
    credentials_path: str = "config/credentials.json"

    def __post_init__(self) -> None:
        """Валидация после создания."""
        if not (1 <= self.tcp_port <= 65535):
            raise ValueError(f"tcp_port должен быть в диапазоне 1–65535, получено {self.tcp_port}")
        _validate_cmw(self.cmw500)
        _validate_timeouts(self.timeouts)
        _validate_log(self.logging)
        _validate_vehicle(self.vehicle)

    @classmethod
    def from_file(cls, path: str) -> Config:
        """Загрузить конфигурацию из JSON-файла."""
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
        vehicle_data = data.get("vehicle", {})

        # Вспомогательная функция: ищет ключ в обоих регистрах
        def get_key(data_dict, key, default):
            # Пробуем строчный (новый) и верхний (старый) регистры
            return data_dict.get(key, data_dict.get(key.upper(), default))

        return cls(
            gost_version=data.get("gost_version", cls.gost_version),
            tcp_host=data.get("tcp_host", cls.tcp_host),
            tcp_port=data.get("tcp_port", cls.tcp_port),
            cmw500=CmwConfig(
                ip=cmw_data.get("ip", CmwConfig.ip),
                simulate=cmw_data.get("simulate", CmwConfig.simulate),
                timeout=float(get_key(cmw_data, "timeout", CmwConfig.timeout)),
                retries=cmw_data.get("retries", CmwConfig.retries),
                sms_send_timeout=float(get_key(cmw_data, "sms_send_timeout", CmwConfig.sms_send_timeout)),
                status_poll_interval=float(get_key(cmw_data, "status_poll_interval", CmwConfig.status_poll_interval)),
                mcc=cmw_data.get("mcc", CmwConfig.mcc),
                mnc=cmw_data.get("mnc", CmwConfig.mnc),
                rf_level_tch=float(get_key(cmw_data, "rf_level_tch", CmwConfig.rf_level_tch)),
                ps_service=cmw_data.get("ps_service", CmwConfig.ps_service),
                ps_tlevel=cmw_data.get("ps_tlevel", CmwConfig.ps_tlevel),
                ps_cscheme_ul=cmw_data.get("ps_cscheme_ul", CmwConfig.ps_cscheme_ul),
                ps_dl_carrier=cmw_data.get(
                    "ps_dl_carrier",
                    [
                        "OFF",
                        "OFF",
                        "OFF",
                        "ON",
                        "ON",
                        "OFF",
                        "OFF",
                        "OFF",
                    ],
                ),
                ps_dl_cscheme=cmw_data.get("ps_dl_cscheme", ["MC9"] * 8),
                sms_dcoding=cmw_data.get("sms_dcoding", CmwConfig.sms_dcoding),
                sms_pidentifier=cmw_data.get("sms_pidentifier", CmwConfig.sms_pidentifier),
                visa_resource=cmw_data.get("visa_resource", CmwConfig.visa_resource),
                network_type=cmw_data.get("network_type", CmwConfig.network_type),
                ps_domain=cmw_data.get("ps_domain", CmwConfig.ps_domain),
                gsm_auth=cmw_data.get("gsm_auth", CmwConfig.gsm_auth),
                frequency_band=cmw_data.get("frequency_band", CmwConfig.frequency_band),
                voice_codec=cmw_data.get("voice_codec", CmwConfig.voice_codec),
                arfcn_bch=cmw_data.get("arfcn_bch", CmwConfig.arfcn_bch),
                arfcn_tch=cmw_data.get("arfcn_tch", CmwConfig.arfcn_tch),
                rf_level_min=cmw_data.get("rf_level_min", CmwConfig.rf_level_min),
                rf_level_max=cmw_data.get("rf_level_max", CmwConfig.rf_level_max),
                pcl_value=cmw_data.get("pcl_value", CmwConfig.pcl_value),
                profile_imsi=cmw_data.get("profile_imsi", CmwConfig.profile_imsi),
                smsc_number=cmw_data.get("smsc_number", CmwConfig.smsc_number),
                dau_ip=cmw_data.get("dau_ip", CmwConfig.dau_ip),
                dau_subnet_mask=cmw_data.get("dau_subnet_mask", CmwConfig.dau_subnet_mask),
                test_system_ip=cmw_data.get("test_system_ip", CmwConfig.test_system_ip),
                usv_dhcp_ip=cmw_data.get("usv_dhcp_ip", CmwConfig.usv_dhcp_ip),
            ),
            timeouts=TimeoutsConfig(
                tl_response_to=float(get_key(timeouts_data, "tl_response_to", TimeoutsConfig.tl_response_to)),
                tl_resend_attempts=get_key(timeouts_data, "tl_resend_attempts", TimeoutsConfig.tl_resend_attempts),
                tl_reconnect_to=float(get_key(timeouts_data, "tl_reconnect_to", TimeoutsConfig.tl_reconnect_to)),
                egts_sl_not_auth_to=float(get_key(timeouts_data, "egts_sl_not_auth_to", TimeoutsConfig.egts_sl_not_auth_to)),
            ),
            logging=LogConfig(
                level=get_key(logging_data, "level", LogConfig.level),
                dir=get_key(logging_data, "dir", LogConfig.dir),
                rotation=get_key(logging_data, "rotation", LogConfig.rotation),
                max_size_mb=get_key(logging_data, "max_size_mb", LogConfig.max_size_mb),
                retention_days=get_key(logging_data, "retention_days", LogConfig.retention_days),
            ),
            vehicle=VehicleConfig(
                vin=vehicle_data.get("vin", VehicleConfig.vin),
                category=vehicle_data.get("category", VehicleConfig.category),
                fuel_type=vehicle_data.get("fuel_type", VehicleConfig.fuel_type),
            ),
            credentials_path=data.get("credentials_path", cls.credentials_path),
        )

    def merge_with_cli(self, cli_args: dict[str, Any]) -> Config:
        """Создать новый Config с переопределениями из CLI."""
        if not cli_args:
            return replace(self)

        top_level: dict[str, Any] = {}
        nested: dict[str, dict[str, Any]] = {"cmw500": {}, "timeouts": {}, "logging": {}, "vehicle": {}}

        for key, value in cli_args.items():
            if "." in key:
                section, field_name = key.split(".", 1)
                if section in nested:
                    nested[section][field_name] = value
            else:
                top_level[key] = value

        kwargs: dict[str, Any] = {}
        if top_level:
            kwargs.update(top_level)

        if nested["cmw500"]:
            kwargs["cmw500"] = replace(self.cmw500, **nested["cmw500"])
        if nested["timeouts"]:
            kwargs["timeouts"] = replace(self.timeouts, **nested["timeouts"])
        if nested["logging"]:
            kwargs["logging"] = replace(self.logging, **nested["logging"])
        if nested["vehicle"]:
            kwargs["vehicle"] = replace(self.vehicle, **nested["vehicle"])

        return replace(self, **kwargs) if kwargs else replace(self)

    def __str__(self) -> str:
        """Компактное строковое представление для логов."""
        cmw_ip = self.cmw500.ip or "не настроен"
        return f"Config(gost={self.gost_version}, tcp={self.tcp_host}:{self.tcp_port}, cmw={cmw_ip})"
