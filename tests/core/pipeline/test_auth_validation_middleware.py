"""Интеграционные тесты AuthValidationMiddleware."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from core.config import Config, VehicleConfig
from core.credentials import Credentials
from core.event_bus import EventBus
from core.pipeline import AuthValidationMiddleware, PacketContext
from core.session import SessionManager
from core.validators.auth_validator import AuthValidator
from core.validators.service_info_validator import ServiceInfoValidator
from libs.egts.models import Packet, ParseResult, Record, Subrecord


@pytest.fixture
def config():
    return Config(vehicle=VehicleConfig(
        vin="WVWZZZ3CZWE123456",
        category="M1",
        fuel_type="бензин",
    ))


@pytest.fixture
def credentials():
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
def mock_protocol():
    proto = MagicMock()
    proto.build_response = MagicMock(return_value=b"\x00" * 20)
    return proto


@pytest.fixture
def mock_connection(mock_protocol):
    conn = MagicMock()
    conn.protocol = mock_protocol
    return conn


@pytest.fixture
def session_mgr(mock_connection):
    mgr = MagicMock(spec=SessionManager)
    mgr.get_session = MagicMock(return_value=mock_connection)
    return mgr


@pytest.fixture
def auth_validator(config, credentials):
    return AuthValidator(config, credentials)


@pytest.fixture
def service_info_validator():
    return ServiceInfoValidator()


@pytest.fixture
def bus():
    b = EventBus()
    return b


@pytest.fixture
def middleware(session_mgr, auth_validator, service_info_validator, bus):
    return AuthValidationMiddleware(
        session_mgr=session_mgr,
        auth_validator=auth_validator,
        service_info_validator=service_info_validator,
        bus=bus,
    )


def _make_ctx(packet, crc_valid=True):
    return PacketContext(
        raw=b"\x00" * 20,
        connection_id="conn-1",
        crc_valid=crc_valid,
        parsed=ParseResult(packet=packet, errors=[], warnings=[]),
    )


def _make_packet(records):
    return Packet(
        packet_id=1,
        packet_type=1,
        records=records,
    )


def _make_auth_record(subrecords):
    return Record(
        record_id=1,
        service_type=1,
        subrecords=subrecords,
    )


def _make_term_identity_subrecord(
    tid=42, imei="351234567890123", imsi="250011234567890",
    msisdn="+79001234567", flags=0x0E, imeie=True, imsie=True, mne=True,
):
    return Subrecord(
        subrecord_type=1,
        data={
            "tid": tid, "flags": flags,
            "hdide": False, "imeie": imeie, "imsie": imsie,
            "lngce": False, "ssra": False, "nide": False,
            "bse": False, "mne": mne,
            "imei": imei, "imsi": imsi, "msisdn": msisdn,
        },
    )


def _make_vehicle_data_subrecord(
    vin="WVWZZZ3CZWE123456", vht=1, vpst=1,
):
    return Subrecord(
        subrecord_type=3,
        data={"vin": vin, "vht": vht, "vpst": vpst},
    )


def _make_service_info_subrecord(services):
    return Subrecord(
        subrecord_type=8,
        data={"srvp": 0, "srva": False, "srvrp": 0, "services": services},
    )


class TestAuthValidationMiddlewareTermIdentity:
    @pytest.mark.asyncio
    async def test_term_identity_match_passes(self, middleware):
        rec = _make_auth_record([_make_term_identity_subrecord()])
        pkt = _make_packet([rec])
        ctx = _make_ctx(pkt)

        await middleware(ctx)

        assert ctx.terminated is False
        assert ctx.response_data is None

    @pytest.mark.asyncio
    async def test_term_identity_imei_mismatch_terminates(self, middleware):
        rec = _make_auth_record([
            _make_term_identity_subrecord(imei="999999999999999"),
        ])
        pkt = _make_packet([rec])
        ctx = _make_ctx(pkt)

        await middleware(ctx)

        assert ctx.terminated is True
        assert ctx.response_data is not None
        assert len(ctx.errors) > 0
        assert "IMEI mismatch" in ctx.errors[0]

    @pytest.mark.asyncio
    async def test_term_identity_imsi_mismatch_terminates(self, middleware):
        rec = _make_auth_record([
            _make_term_identity_subrecord(imsi="999999999999999"),
        ])
        pkt = _make_packet([rec])
        ctx = _make_ctx(pkt)

        await middleware(ctx)

        assert ctx.terminated is True
        assert "IMSI mismatch" in ctx.errors[0]

    @pytest.mark.asyncio
    async def test_term_identity_unit_id_mismatch_terminates(self, middleware):
        rec = _make_auth_record([
            _make_term_identity_subrecord(tid=999),
        ])
        pkt = _make_packet([rec])
        ctx = _make_ctx(pkt)

        await middleware(ctx)

        assert ctx.terminated is True
        assert "UNIT_ID mismatch" in ctx.errors[0]


class TestAuthValidationMiddlewareVehicleData:
    @pytest.mark.asyncio
    async def test_vehicle_data_match_passes(self, middleware):
        rec = _make_auth_record([_make_vehicle_data_subrecord()])
        pkt = _make_packet([rec])
        ctx = _make_ctx(pkt)

        await middleware(ctx)

        assert ctx.terminated is False

    @pytest.mark.asyncio
    async def test_vehicle_data_vin_mismatch_terminates(self, middleware):
        rec = _make_auth_record([
            _make_vehicle_data_subrecord(vin="OTHERVIN123456789"),
        ])
        pkt = _make_packet([rec])
        ctx = _make_ctx(pkt)

        await middleware(ctx)

        assert ctx.terminated is True
        assert "VIN mismatch" in ctx.errors[0]

    @pytest.mark.asyncio
    async def test_vehicle_data_category_mismatch_terminates(self, middleware):
        rec = _make_auth_record([
            _make_vehicle_data_subrecord(vht=2),
        ])
        pkt = _make_packet([rec])
        ctx = _make_ctx(pkt)

        await middleware(ctx)

        assert ctx.terminated is True
        assert "Category mismatch" in ctx.errors[0]


class TestAuthValidationMiddlewareServiceInfo:
    @pytest.mark.asyncio
    async def test_service_info_st10_passes(self, middleware):
        rec = _make_auth_record([
            _make_service_info_subrecord(services=[{"st": 10, "sst": 0, "srvp": 0}]),
        ])
        pkt = _make_packet([rec])
        ctx = _make_ctx(pkt)

        await middleware(ctx)

        assert ctx.terminated is False

    @pytest.mark.asyncio
    async def test_service_info_st5_terminates(self, middleware):
        rec = _make_auth_record([
            _make_service_info_subrecord(services=[{"st": 5, "sst": 0, "srvp": 0}]),
        ])
        pkt = _make_packet([rec])
        ctx = _make_ctx(pkt)

        await middleware(ctx)

        assert ctx.terminated is True
        assert "ST=5" in ctx.errors[0]


class TestAuthValidationMiddlewareSkipConditions:
    @pytest.mark.asyncio
    async def test_skips_when_crc_invalid(self, middleware):
        rec = _make_auth_record([_make_term_identity_subrecord(imei="bad")])
        pkt = _make_packet([rec])
        ctx = _make_ctx(pkt, crc_valid=False)

        await middleware(ctx)

        assert ctx.terminated is False
        assert ctx.response_data is None

    @pytest.mark.asyncio
    async def test_skips_when_parsed_is_none(self, middleware):
        ctx = PacketContext(raw=b"\x00" * 20, connection_id="conn-1", crc_valid=True)

        await middleware(ctx)

        assert ctx.terminated is False

    @pytest.mark.asyncio
    async def test_skips_non_auth_service(self, middleware):
        rec = Record(
            record_id=1,
            service_type=10,
            subrecords=[_make_term_identity_subrecord(imei="bad")],
        )
        pkt = _make_packet([rec])
        ctx = _make_ctx(pkt)

        await middleware(ctx)

        assert ctx.terminated is False

    @pytest.mark.asyncio
    async def test_skips_when_session_not_found(self):
        mgr = MagicMock()
        mgr.get_session = MagicMock(return_value=None)
        mw = AuthValidationMiddleware(mgr, MagicMock(), MagicMock(), MagicMock())

        rec = _make_auth_record([_make_term_identity_subrecord(imei="bad")])
        pkt = _make_packet([rec])
        ctx = _make_ctx(pkt)

        await mw(ctx)

        assert ctx.terminated is False

    @pytest.mark.asyncio
    async def test_skips_when_protocol_is_none(self):
        conn = MagicMock()
        conn.protocol = None
        mgr = MagicMock()
        mgr.get_session = MagicMock(return_value=conn)
        mw = AuthValidationMiddleware(mgr, MagicMock(), MagicMock(), MagicMock())

        rec = _make_auth_record([_make_term_identity_subrecord(imei="bad")])
        pkt = _make_packet([rec])
        ctx = _make_ctx(pkt)

        await mw(ctx)

        assert ctx.terminated is False

    @pytest.mark.asyncio
    async def test_skips_raw_bytes_subrecord(self, middleware):
        rec = _make_auth_record([
            Subrecord(subrecord_type=1, data=b"\x00\x00\x00\x00\x00"),
        ])
        pkt = _make_packet([rec])
        ctx = _make_ctx(pkt)

        await middleware(ctx)

        assert ctx.terminated is False


class TestAuthValidationMiddlewareEvents:
    @pytest.mark.asyncio
    async def test_emits_validation_passed_on_success(self, bus, session_mgr, auth_validator, service_info_validator):
        events = []

        async def capture(data):
            events.append(data)

        bus.on("auth.validation_passed", capture)

        mw = AuthValidationMiddleware(session_mgr, auth_validator, service_info_validator, bus)
        rec = _make_auth_record([_make_term_identity_subrecord()])
        pkt = _make_packet([rec])
        ctx = _make_ctx(pkt)

        await mw(ctx)

        assert len(events) == 1
        assert events[0]["connection_id"] == "conn-1"
        assert events[0]["subrecord"] == "TERM_IDENTITY"

    @pytest.mark.asyncio
    async def test_emits_validation_failed_on_mismatch(self, bus, session_mgr, auth_validator, service_info_validator):
        events = []

        async def capture(data):
            events.append(data)

        bus.on("auth.validation_failed", capture)

        mw = AuthValidationMiddleware(session_mgr, auth_validator, service_info_validator, bus)
        rec = _make_auth_record([_make_term_identity_subrecord(imei="bad")])
        pkt = _make_packet([rec])
        ctx = _make_ctx(pkt)

        await mw(ctx)

        assert len(events) == 1
        assert "IMEI mismatch" in "; ".join(events[0]["reasons"])

    @pytest.mark.asyncio
    async def test_emits_service_info_requested(self, bus, session_mgr, auth_validator, service_info_validator):
        events = []

        async def capture(data):
            events.append(data)

        bus.on("service_info.requested", capture)

        mw = AuthValidationMiddleware(session_mgr, auth_validator, service_info_validator, bus)
        rec = _make_auth_record([
            _make_service_info_subrecord(services=[{"st": 10, "sst": 0, "srvp": 0}]),
        ])
        pkt = _make_packet([rec])
        ctx = _make_ctx(pkt)

        await mw(ctx)

        assert len(events) == 1
        assert events[0]["service_type"] == 10
