"""Тесты ServiceInfoValidator (ТЗ п. 2.3.1 шаг 11)."""

from __future__ import annotations

import pytest

from core.validators.service_info_validator import ServiceInfoValidator


class TestServiceInfoValidatorValidateRequest:
    @pytest.fixture
    def validator(self):
        return ServiceInfoValidator()

    def test_allowed_service_st10(self, validator):
        result = validator.validate_request(10)
        assert result.passed is True
        assert result.reasons == []

    def test_rejected_service_st5(self, validator):
        result = validator.validate_request(5)
        assert result.passed is False
        assert len(result.reasons) == 1
        assert "ST=5" in result.reasons[0]

    def test_rejected_service_st2(self, validator):
        result = validator.validate_request(2)
        assert result.passed is False
        assert "ST=2" in result.reasons[0]

    def test_rejected_service_st0(self, validator):
        result = validator.validate_request(0)
        assert result.passed is False


class TestServiceInfoValidatorBuildAcceptResponse:
    @pytest.fixture
    def validator(self):
        return ServiceInfoValidator()

    def test_accept_response_structure(self, validator):
        resp = validator.build_accept_response()
        assert resp["st"] == 10
        assert resp["sst"] == 0
        assert resp["srva"] is False
        assert (resp["srvp"] & 0x80) == 0

    def test_accept_response_status_available(self, validator):
        resp = validator.build_accept_response()
        assert resp["sst"] == 0


class TestServiceInfoValidatorBuildRejectResponse:
    @pytest.fixture
    def validator(self):
        return ServiceInfoValidator()

    def test_reject_response_structure(self, validator):
        resp = validator.build_reject_response(5)
        assert resp["st"] == 5
        assert resp["srva"] is True
        assert (resp["srvp"] & 0x80) != 0

    def test_reject_response_preserves_requested_type(self, validator):
        resp = validator.build_reject_response(42)
        assert resp["st"] == 42

    def test_reject_response_status_unavailable(self, validator):
        resp = validator.build_reject_response(10)
        assert resp["sst"] == 0
