"""Валидаторы авторизации и аутентификации EGTS (ТЗ п. 2.3.1 шаг 8, 10)."""

from __future__ import annotations

import re
from dataclasses import dataclass


def validate_imei(imei: str) -> bool:
    """Проверить формат IMEI (15 цифр, ГОСТ 33465-2015)."""
    return bool(re.fullmatch(r"\d{15}", imei))


def validate_imsi(imsi: str) -> bool:
    """Проверить формат IMSI (5-15 цифр, начинается с MCC)."""
    return bool(re.fullmatch(r"\d{5,15}", imsi))


def validate_msisdn(msisdn: str) -> bool:
    """Проверить формат MSISDN (E.164: +7XXXXXXXXXX или 7XXXXXXXXXX, до 15 цифр)."""
    if not msisdn:
        return True
    return bool(re.fullmatch(r"\+?\d{7,15}", msisdn))


@dataclass
class AuthValidationResult:
    """Результат валидации авторизации/аутентификации."""
    passed: bool
    reasons: list[str]


class AuthValidator:
    """Валидация авторизации и аутентификации (ТЗ п. 2.3.1 шаг 8, 10).

    Сравнивает параметры из TERM_IDENTITY и VEHICLE_DATA с конфигурацией.
    """

    CATEGORY_MAP = {"M1": 1, "M2": 2, "M3": 3, "N1": 4, "N2": 5, "N3": 6}
    FUEL_MAP = {"бензин": 1, "дизель": 2, "газ": 3, "электричество": 4}

    def __init__(self, config, credentials):
        self._config = config
        self._credentials = credentials

    def validate_term_identity(
        self,
        unit_id: int | None = None,
        imsi: str | None = None,
        imei: str | None = None,
        msisdn: str | None = None,
    ) -> AuthValidationResult:
        """Сверка параметров TERM_IDENTITY с настройками (ТЗ п. 2.1.3)."""
        reasons: list[str] = []
        creds = self._credentials

        if imsi and creds.imsi and imsi != creds.imsi:
            reasons.append(f"IMSI mismatch: {imsi} != {creds.imsi}")
        if imei and creds.imei and imei != creds.imei:
            reasons.append(f"IMEI mismatch: {imei} != {creds.imei}")
        if msisdn and creds.msisdn and msisdn != creds.msisdn:
            reasons.append(f"MSISDN mismatch: {msisdn} != {creds.msisdn}")
        if unit_id is not None and creds.egts_unit_id and unit_id != creds.egts_unit_id:
            reasons.append(f"UNIT_ID mismatch: {unit_id} != {creds.egts_unit_id}")

        return AuthValidationResult(passed=len(reasons) == 0, reasons=reasons)

    def validate_vehicle_data(
        self,
        vin: str | None = None,
        category: int | None = None,
        fuel_type: int | None = None,
    ) -> AuthValidationResult:
        """Сверка параметров VEHICLE_DATA с настройками (ТЗ п. 2.1.4)."""
        reasons: list[str] = []
        vehicle = self._config.vehicle

        if vin and vehicle.vin and vin != vehicle.vin:
            reasons.append(f"VIN mismatch: {vin} != {vehicle.vin}")
        if category is not None and vehicle.category:
            expected = self.CATEGORY_MAP.get(vehicle.category)
            if expected is not None and category != expected:
                reasons.append(f"Category mismatch: {category} != {expected}")
        if fuel_type is not None and vehicle.fuel_type:
            expected = self.FUEL_MAP.get(vehicle.fuel_type)
            if expected is not None and fuel_type != expected:
                reasons.append(f"Fuel type mismatch: {fuel_type} != {expected}")

        return AuthValidationResult(passed=len(reasons) == 0, reasons=reasons)
