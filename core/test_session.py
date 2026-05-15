"""TestSession — управление сеансом проверок (ТЗ п. 2.2.5-2.2.6)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from core.config import Config
from core.credentials import Credentials


class SessionState(Enum):
    """Состояние сеанса проверок."""

    INACTIVE = "inactive"
    ACTIVE = "active"
    COMPLETED = "completed"


@dataclass
class TestResult:
    """Результат одной проверки."""

    test_name: str
    passed: bool
    reasons: list[str]
    steps_completed: int
    steps_total: int
    started_at: float
    completed_at: float | None = None
    config_type: str | None = None


@dataclass
class TestSession:
    """Сеанс проверок (ТЗ п. 2.2.5-2.2.6)."""

    state: SessionState = SessionState.INACTIVE
    started_at: float | None = None
    completed_at: float | None = None

    # Статусы (ТЗ п. 2.2.2)
    cmw_connected: bool = False
    usv_registered: bool = False
    gprs_attached: bool = False
    registered_imsi: str | None = None
    tcp_connected: bool = False
    config_done: bool = False
    auth_done: bool = False
    auth_result: bool | None = None
    auth_validation_passed: bool | None = None
    vehicle_auth_done: bool = False
    vehicle_auth_passed: bool | None = None
    voice_connected: bool = False

    # Результаты тестов
    test_results: dict[str, TestResult] = field(default_factory=dict)

    # Snapshot конфигурации (для отчёта)
    config_snapshot: dict[str, Any] | None = None
    credentials_snapshot: dict[str, Any] | None = None

    def activate(self, config: Config, credentials: Credentials) -> None:
        """Начать новый сеанс (ТЗ п. 2.2.1)."""
        self.state = SessionState.ACTIVE
        self.started_at = time.time()
        self.config_snapshot = self._snapshot_config(config)
        self.credentials_snapshot = self._snapshot_credentials(credentials)
        self._reset_statuses()

    def deactivate(self) -> None:
        """Завершить сеанс (ТЗ п. 2.2.5)."""
        self.state = SessionState.COMPLETED
        self.completed_at = time.time()

    def reset_on_network_off(self) -> None:
        """Сброс при выключении сети (ТЗ п. 2.2.5)."""
        self.usv_registered = False
        self.gprs_attached = False
        self.registered_imsi = None
        self.tcp_connected = False
        self.auth_done = False
        self.auth_result = None
        self.auth_validation_passed = None
        self.config_done = False
        self.vehicle_auth_done = False
        self.vehicle_auth_passed = None
        self.voice_connected = False

    def reset_all(self) -> None:
        """Полный сброс при повторной активации (ТЗ п. 2.2.6)."""
        self.__init__()

    def _reset_statuses(self) -> None:
        """Сбросить статусы в значения по умолчанию."""
        self.cmw_connected = False
        self.usv_registered = False
        self.gprs_attached = False
        self.registered_imsi = None
        self.tcp_connected = False
        self.config_done = False
        self.auth_done = False
        self.auth_result = None
        self.auth_validation_passed = None
        self.vehicle_auth_done = False
        self.vehicle_auth_passed = None
        self.voice_connected = False

    @staticmethod
    def _snapshot_config(config: Config) -> dict[str, Any]:
        cmw = config.cmw500
        return {
            "cmw500": {
                "ip": cmw.ip,
                "mcc": cmw.mcc,
                "mnc": cmw.mnc,
                "dau_ip": cmw.dau_ip,
                "test_system_ip": cmw.test_system_ip,
                "usv_dhcp_ip": cmw.usv_dhcp_ip,
                "network_type": cmw.network_type,
                "ps_domain": cmw.ps_domain,
                "gsm_auth": cmw.gsm_auth,
                "frequency_band": cmw.frequency_band,
                "voice_codec": cmw.voice_codec,
                "rf_level_tch": cmw.rf_level_tch,
            },
            "vehicle": {
                "vin": config.vehicle.vin,
                "category": config.vehicle.category,
                "fuel_type": config.vehicle.fuel_type,
            },
        }

    @staticmethod
    def _snapshot_credentials(creds: Credentials) -> dict[str, Any]:
        return {
            "imsi": creds.imsi,
            "imei": creds.imei,
            "msisdn": creds.msisdn,
            "egts_unit_id": creds.egts_unit_id,
            "term_code": creds.term_code,
            "device_id": creds.device_id,
        }
