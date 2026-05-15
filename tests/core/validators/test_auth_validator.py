"""Тесты AuthValidator и форматной валидации (ТЗ п. 2.3.1 шаг 8, 10)."""

from __future__ import annotations

import pytest

from core.config import Config, VehicleConfig
from core.credentials import Credentials, validate_imei, validate_imsi, validate_msisdn
from core.validators.auth_validator import AuthValidator


class TestValidateImei:
    def test_valid_imei_15_digits(self):
        assert validate_imei("351234567890123") is True

    def test_invalid_imei_too_short(self):
        assert validate_imei("35123456789012") is False

    def test_invalid_imei_too_long(self):
        assert validate_imei("3512345678901234") is False

    def test_invalid_imei_with_letters(self):
        assert validate_imei("35123456789012A") is False

    def test_invalid_imei_empty(self):
        assert validate_imei("") is False


class TestValidateImsi:
    def test_valid_imsi_15_digits(self):
        assert validate_imsi("250011234567890") is True

    def test_valid_imsi_5_digits(self):
        assert validate_imsi("25001") is True

    def test_invalid_imsi_too_short(self):
        assert validate_imsi("2500") is False

    def test_invalid_imsi_too_long(self):
        assert validate_imsi("2500112345678901") is False

    def test_invalid_imsi_with_letters(self):
        assert validate_imsi("25001123456789A") is False


class TestValidateMsisdn:
    def test_valid_msisdn_with_plus(self):
        assert validate_msisdn("+79001234567") is True

    def test_valid_msisdn_without_plus(self):
        assert validate_msisdn("79001234567") is True

    def test_valid_msisdn_7_digits(self):
        assert validate_msisdn("7900123") is True

    def test_valid_msisdn_15_digits(self):
        assert validate_msisdn("+123456789012345") is True

    def test_invalid_msisdn_too_short(self):
        assert validate_msisdn("123456") is False

    def test_invalid_msisdn_too_long(self):
        assert validate_msisdn("+1234567890123456") is False

    def test_empty_msisdn_is_valid(self):
        assert validate_msisdn("") is True

    def test_invalid_msisdn_with_letters(self):
        assert validate_msisdn("+7900123456A") is False


class TestCredentialsValidateFormat:
    def test_valid_credentials(self):
        creds = Credentials(
            imei="351234567890123",
            imsi="250011234567890",
            term_code="TEST001",
            auth_key="key1",
            device_id="USV-001",
            msisdn="+79001234567",
        )
        assert creds.validate_format() == []

    def test_invalid_imei(self):
        with pytest.raises(ValueError, match="IMEI"):
            Credentials(
                imei="123",
                imsi="250011234567890",
                term_code="TEST001",
                auth_key="key1",
                device_id="USV-001",
            )

    def test_invalid_imsi(self):
        with pytest.raises(ValueError, match="IMSI"):
            Credentials(
                imei="351234567890123",
                imsi="12",
                term_code="TEST001",
                auth_key="key1",
                device_id="USV-001",
            )

    def test_invalid_msisdn(self):
        with pytest.raises(ValueError, match="MSISDN"):
            Credentials(
                imei="351234567890123",
                imsi="250011234567890",
                term_code="TEST001",
                auth_key="key1",
                device_id="USV-001",
                msisdn="abc",
            )

    def test_multiple_format_errors(self):
        with pytest.raises(ValueError, match="IMEI"):
            Credentials(
                imei="short",
                imsi="12",
                term_code="TEST001",
                auth_key="key1",
                device_id="USV-001",
                msisdn="abc",
            )


class TestAuthValidatorValidateTermIdentity:
    @pytest.fixture
    def config(self):
        return Config()

    @pytest.fixture
    def credentials(self):
        return Credentials(
            imei="351234567890123",
            imsi="250011234567890",
            term_code="TEST001",
            auth_key="key1",
            device_id="USV-001",
            msisdn="+79001234567",
            egts_unit_id=42,
        )

    @pytest.fixture
    def validator(self, config, credentials):
        return AuthValidator(config, credentials)

    def test_all_match(self, validator):
        result = validator.validate_term_identity(
            unit_id=42,
            imsi="250011234567890",
            imei="351234567890123",
            msisdn="+79001234567",
        )
        assert result.passed is True
        assert result.reasons == []

    def test_imei_mismatch(self, validator):
        result = validator.validate_term_identity(
            imei="999999999999999",
        )
        assert result.passed is False
        assert len(result.reasons) == 1
        assert "IMEI mismatch" in result.reasons[0]

    def test_imsi_mismatch(self, validator):
        result = validator.validate_term_identity(
            imsi="999999999999999",
        )
        assert result.passed is False
        assert "IMSI mismatch" in result.reasons[0]

    def test_msisdn_mismatch(self, validator):
        result = validator.validate_term_identity(
            msisdn="+79999999999",
        )
        assert result.passed is False
        assert "MSISDN mismatch" in result.reasons[0]

    def test_unit_id_mismatch(self, validator):
        result = validator.validate_term_identity(
            unit_id=999,
        )
        assert result.passed is False
        assert "UNIT_ID mismatch" in result.reasons[0]

    def test_empty_credentials_skip_check(self, config):
        creds = Credentials(
            imei="351234567890123",
            imsi="250011234567890",
            term_code="TEST001",
            auth_key="key1",
            device_id="USV-001",
            msisdn="",
            egts_unit_id=0,
        )
        v = AuthValidator(config, creds)
        result = v.validate_term_identity(
            imsi="250011234567890",
            imei="351234567890123",
            msisdn="+79001234567",
            unit_id=42,
        )
        assert result.passed is True

    def test_none_values_skip_check(self, validator):
        result = validator.validate_term_identity()
        assert result.passed is True

    def test_multiple_mismatches(self, validator):
        result = validator.validate_term_identity(
            imsi="bad",
            imei="bad",
        )
        assert result.passed is False
        assert len(result.reasons) == 2


class TestAuthValidatorValidateVehicleData:
    @pytest.fixture
    def credentials(self):
        return Credentials(
            imei="351234567890123",
            imsi="250011234567890",
            term_code="TEST001",
            auth_key="key1",
            device_id="USV-001",
        )

    def test_all_match(self, credentials):
        config = Config(vehicle=VehicleConfig(
            vin="WVWZZZ3CZWE123456",
            category="M1",
            fuel_type="бензин",
        ))
        validator = AuthValidator(config, credentials)
        result = validator.validate_vehicle_data(
            vin="WVWZZZ3CZWE123456",
            category=1,
            fuel_type=1,
        )
        assert result.passed is True

    def test_vin_mismatch(self, credentials):
        config = Config(vehicle=VehicleConfig(vin="WVWZZZ3CZWE123456"))
        validator = AuthValidator(config, credentials)
        result = validator.validate_vehicle_data(vin="OTHERVIN123456789")
        assert result.passed is False
        assert "VIN mismatch" in result.reasons[0]

    def test_category_mismatch(self, credentials):
        config = Config(vehicle=VehicleConfig(category="M1"))
        validator = AuthValidator(config, credentials)
        result = validator.validate_vehicle_data(category=2)
        assert result.passed is False
        assert "Category mismatch" in result.reasons[0]

    def test_fuel_type_mismatch(self, credentials):
        config = Config(vehicle=VehicleConfig(fuel_type="бензин"))
        validator = AuthValidator(config, credentials)
        result = validator.validate_vehicle_data(fuel_type=2)
        assert result.passed is False
        assert "Fuel type mismatch" in result.reasons[0]

    def test_empty_vehicle_config_skip(self, credentials):
        config = Config()
        validator = AuthValidator(config, credentials)
        result = validator.validate_vehicle_data(
            vin="ANYVIN12345678901",
            category=99,
            fuel_type=99,
        )
        assert result.passed is True

    def test_none_values_skip(self, credentials):
        config = Config(vehicle=VehicleConfig(vin="WVWZZZ3CZWE123456"))
        validator = AuthValidator(config, credentials)
        result = validator.validate_vehicle_data()
        assert result.passed is True

    def test_category_mapping_n3(self, credentials):
        config = Config(vehicle=VehicleConfig(category="N3"))
        validator = AuthValidator(config, credentials)
        result = validator.validate_vehicle_data(category=6)
        assert result.passed is True

    def test_fuel_mapping_electric(self, credentials):
        config = Config(vehicle=VehicleConfig(fuel_type="электричество"))
        validator = AuthValidator(config, credentials)
        result = validator.validate_vehicle_data(fuel_type=4)
        assert result.passed is True
