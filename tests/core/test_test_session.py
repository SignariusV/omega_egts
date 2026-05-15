"""Тесты для TestSession — управление сеансом проверок (ТЗ п. 2.2.5-2.2.6)."""

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.config import Config
from core.credentials import Credentials
from core.engine import CoreEngine
from core.event_bus import EventBus
from core.test_session import SessionState, TestResult, TestSession


def _make_config() -> Config:
    d = Path(tempfile.mkdtemp())
    f = d / "settings.json"
    f.write_text(json.dumps({
        "gost_version": "2015",
        "tcp_port": 8090,
        "tcp_host": "0.0.0.0",
        "cmw500": {"ip": "127.0.0.1"},
        "logging": {"level": "INFO", "dir": "./logs"},
        "vehicle": {"vin": "WBA12345678901234", "category": "M1", "fuel_type": "бензин"},
    }))
    return Config.from_file(str(f))


def _make_credentials() -> Credentials:
    return Credentials(
        imei="123456789012345",
        imsi="250770123456789",
        msisdn="+79001234567",
        term_code="TERM001",
        auth_key="key123",
        device_id="DEV001",
        egts_unit_id=42,
    )


class TestSessionState:
    def test_has_inactive(self) -> None:
        assert SessionState.INACTIVE.value == "inactive"

    def test_has_active(self) -> None:
        assert SessionState.ACTIVE.value == "active"

    def test_has_completed(self) -> None:
        assert SessionState.COMPLETED.value == "completed"


class TestTestResult:
    def test_defaults(self) -> None:
        result = TestResult(
            test_name="7.3",
            passed=False,
            reasons=["timeout"],
            steps_completed=3,
            steps_total=16,
            started_at=1000.0,
        )
        assert result.completed_at is None
        assert result.config_type is None

    def test_with_config_type(self) -> None:
        result = TestResult(
            test_name="7.3",
            passed=True,
            reasons=[],
            steps_completed=16,
            steps_total=16,
            started_at=1000.0,
            completed_at=1010.0,
            config_type="1",
        )
        assert result.config_type == "1"
        assert result.completed_at == 1010.0


class TestTestSessionDefaults:
    def test_initial_state(self) -> None:
        session = TestSession()
        assert session.state == SessionState.INACTIVE
        assert session.started_at is None
        assert session.completed_at is None

    def test_all_statuses_false(self) -> None:
        session = TestSession()
        assert session.cmw_connected is False
        assert session.usv_registered is False
        assert session.gprs_attached is False
        assert session.registered_imsi is None
        assert session.tcp_connected is False
        assert session.config_done is False
        assert session.auth_done is False
        assert session.auth_result is None
        assert session.auth_validation_passed is None
        assert session.vehicle_auth_done is False
        assert session.vehicle_auth_passed is None
        assert session.voice_connected is False

    def test_empty_test_results(self) -> None:
        session = TestSession()
        assert session.test_results == {}

    def test_no_snapshots(self) -> None:
        session = TestSession()
        assert session.config_snapshot is None
        assert session.credentials_snapshot is None


class TestTestSessionActivate:
    def test_sets_active_state(self) -> None:
        session = TestSession()
        session.activate(_make_config(), _make_credentials())
        assert session.state == SessionState.ACTIVE

    def test_sets_started_at(self) -> None:
        session = TestSession()
        before = time.time()
        session.activate(_make_config(), _make_credentials())
        after = time.time()
        assert before <= session.started_at <= after

    def test_resets_statuses(self) -> None:
        session = TestSession()
        session.cmw_connected = True
        session.tcp_connected = True
        session.auth_done = True
        session.activate(_make_config(), _make_credentials())
        assert session.cmw_connected is False
        assert session.tcp_connected is False
        assert session.auth_done is False

    def test_preserves_test_results(self) -> None:
        session = TestSession()
        session.test_results["6.8"] = TestResult(
            test_name="6.8", passed=True, reasons=[],
            steps_completed=18, steps_total=18, started_at=1000.0,
        )
        session.activate(_make_config(), _make_credentials())
        assert "6.8" in session.test_results


class TestTestSessionDeactivate:
    def test_sets_completed_state(self) -> None:
        session = TestSession()
        session.state = SessionState.ACTIVE
        session.deactivate()
        assert session.state == SessionState.COMPLETED

    def test_sets_completed_at(self) -> None:
        session = TestSession()
        session.state = SessionState.ACTIVE
        before = time.time()
        session.deactivate()
        after = time.time()
        assert before <= session.completed_at <= after

    def test_preserves_test_results(self) -> None:
        session = TestSession()
        session.test_results["7.3"] = TestResult(
            test_name="7.3", passed=True, reasons=[],
            steps_completed=16, steps_total=16, started_at=1000.0,
        )
        session.deactivate()
        assert "7.3" in session.test_results


class TestTestSessionResetOnNetworkOff:
    def test_resets_network_statuses(self) -> None:
        session = TestSession()
        session.usv_registered = True
        session.gprs_attached = True
        session.registered_imsi = "250770123456789"
        session.tcp_connected = True
        session.config_done = True
        session.auth_done = True
        session.auth_result = True
        session.auth_validation_passed = True
        session.vehicle_auth_done = True
        session.vehicle_auth_passed = True
        session.voice_connected = True

        session.reset_on_network_off()

        assert session.usv_registered is False
        assert session.gprs_attached is False
        assert session.registered_imsi is None
        assert session.tcp_connected is False
        assert session.config_done is False
        assert session.auth_done is False
        assert session.auth_result is None
        assert session.auth_validation_passed is None
        assert session.vehicle_auth_done is False
        assert session.vehicle_auth_passed is None
        assert session.voice_connected is False

    def test_preserves_test_results(self) -> None:
        session = TestSession()
        session.test_results["7.3"] = TestResult(
            test_name="7.3", passed=True, reasons=[],
            steps_completed=16, steps_total=16, started_at=1000.0,
        )
        session.reset_on_network_off()
        assert "7.3" in session.test_results

    def test_preserves_cmw_connected(self) -> None:
        session = TestSession()
        session.cmw_connected = True
        session.reset_on_network_off()
        assert session.cmw_connected is True

    def test_does_not_change_state(self) -> None:
        session = TestSession()
        session.state = SessionState.ACTIVE
        session.reset_on_network_off()
        assert session.state == SessionState.ACTIVE


class TestTestSessionResetAll:
    def test_full_reset(self) -> None:
        session = TestSession()
        session.state = SessionState.ACTIVE
        session.started_at = 1000.0
        session.completed_at = 1010.0
        session.cmw_connected = True
        session.tcp_connected = True
        session.auth_done = True
        session.test_results["7.3"] = TestResult(
            test_name="7.3", passed=True, reasons=[],
            steps_completed=16, steps_total=16, started_at=1000.0,
        )
        session.config_snapshot = {"cmw500": {}}
        session.credentials_snapshot = {"imei": "123"}

        session.reset_all()

        assert session.state == SessionState.INACTIVE
        assert session.started_at is None
        assert session.completed_at is None
        assert session.cmw_connected is False
        assert session.tcp_connected is False
        assert session.auth_done is False
        assert session.test_results == {}
        assert session.config_snapshot is None
        assert session.credentials_snapshot is None


class TestTestSessionSnapshots:
    def test_config_snapshot(self) -> None:
        config = _make_config()
        snapshot = TestSession._snapshot_config(config)
        assert "cmw500" in snapshot
        assert "vehicle" in snapshot
        assert snapshot["cmw500"]["ip"] == "127.0.0.1"
        assert snapshot["cmw500"]["mcc"] == 250
        assert snapshot["cmw500"]["mnc"] == 77
        assert snapshot["vehicle"]["vin"] == "WBA12345678901234"
        assert snapshot["vehicle"]["category"] == "M1"
        assert snapshot["vehicle"]["fuel_type"] == "бензин"

    def test_credentials_snapshot(self) -> None:
        creds = _make_credentials()
        snapshot = TestSession._snapshot_credentials(creds)
        assert snapshot["imei"] == "123456789012345"
        assert snapshot["imsi"] == "250770123456789"
        assert snapshot["msisdn"] == "+79001234567"
        assert snapshot["egts_unit_id"] == 42
        assert snapshot["term_code"] == "TERM001"
        assert snapshot["device_id"] == "DEV001"

    def test_activate_creates_snapshots(self) -> None:
        session = TestSession()
        config = _make_config()
        creds = _make_credentials()
        session.activate(config, creds)
        assert session.config_snapshot is not None
        assert session.credentials_snapshot is not None
        assert session.config_snapshot["vehicle"]["vin"] == "WBA12345678901234"
        assert session.credentials_snapshot["imei"] == "123456789012345"


class TestCoreEngineSessionIntegration:
    def _patch_components(self):
        import sys
        import types

        tcp = MagicMock(start=AsyncMock(), stop=AsyncMock())
        cmw = MagicMock(
            connect=AsyncMock(), disconnect=AsyncMock(),
            get_status=AsyncMock(return_value={}),
            configure_gsm_signaling=AsyncMock(),
            configure_sms=AsyncMock(), configure_dau=AsyncMock(),
        )
        sess = MagicMock()
        log = MagicMock(stop=AsyncMock())
        scen = MagicMock()
        pkt = MagicMock()
        cmd = MagicMock()

        mods = {
            "core.tcp_server": types.ModuleType("core.tcp_server"),
            "core.cmw500": types.ModuleType("core.cmw500"),
            "core.session": types.ModuleType("core.session"),
            "core.logger": types.ModuleType("core.logger"),
            "core.scenario": types.ModuleType("core.scenario"),
            "core.dispatcher": types.ModuleType("core.dispatcher"),
        }
        mods["core.tcp_server"].TcpServerManager = MagicMock(return_value=tcp)
        mods["core.cmw500"].Cmw500Controller = MagicMock(return_value=cmw)
        mods["core.cmw500"].Cmw500Emulator = MagicMock(return_value=cmw)
        mods["core.session"].SessionManager = MagicMock(return_value=sess)
        mods["core.logger"].LogManager = MagicMock(return_value=log)
        mods["core.scenario"].ScenarioManager = MagicMock(return_value=scen)
        mods["core.dispatcher"].PacketDispatcher = MagicMock(return_value=pkt)
        mods["core.dispatcher"].CommandDispatcher = MagicMock(return_value=cmd)

        patchers = [patch.dict(sys.modules, {k: v}) for k, v in mods.items()]
        for p in patchers:
            p.start()
        return patchers, tcp, cmw

    @pytest.mark.asyncio
    async def test_start_subscribes_to_events(self) -> None:
        patchers, *_ = self._patch_components()
        try:
            bus = EventBus()
            config = _make_config()
            engine = CoreEngine(config=config, bus=bus)
            await engine.start()

            assert len(engine._event_handlers) == 5
            event_names = [h[0] for h in engine._event_handlers]
            assert "cmw.connected" in event_names
            assert "cmw.disconnected" in event_names
            assert "connection.changed" in event_names
            assert "auth.validation_passed" in event_names
            assert "auth.validation_failed" in event_names
        finally:
            for p in patchers:
                p.stop()

    @pytest.mark.asyncio
    async def test_stop_unsubscribes_from_events(self) -> None:
        patchers, *_ = self._patch_components()
        try:
            bus = EventBus()
            config = _make_config()
            engine = CoreEngine(config=config, bus=bus)
            await engine.start()
            await engine.stop()

            assert engine._event_handlers == []
        finally:
            for p in patchers:
                p.stop()

    @pytest.mark.asyncio
    async def test_on_cmw_connected_sets_flag(self) -> None:
        bus = EventBus()
        config = _make_config()
        engine = CoreEngine(config=config, bus=bus)
        assert engine.test_session.cmw_connected is False
        await engine._on_cmw_connected({"ip": "127.0.0.1"})
        assert engine.test_session.cmw_connected is True

    @pytest.mark.asyncio
    async def test_on_cmw_disconnected_sets_flag_and_resets(self) -> None:
        bus = EventBus()
        config = _make_config()
        engine = CoreEngine(config=config, bus=bus)
        engine.test_session.cmw_connected = True
        engine.test_session.tcp_connected = True
        engine.test_session.auth_done = True

        await engine._on_cmw_disconnected({})

        assert engine.test_session.cmw_connected is False
        assert engine.test_session.tcp_connected is False
        assert engine.test_session.auth_done is False

    @pytest.mark.asyncio
    async def test_on_connection_connected(self) -> None:
        bus = EventBus()
        config = _make_config()
        engine = CoreEngine(config=config, bus=bus)
        await engine._on_connection_changed({"state": "connected"})
        assert engine.test_session.tcp_connected is True

    @pytest.mark.asyncio
    async def test_on_connection_disconnected(self) -> None:
        bus = EventBus()
        config = _make_config()
        engine = CoreEngine(config=config, bus=bus)
        engine.test_session.tcp_connected = True
        await engine._on_connection_changed({"state": "disconnected"})
        assert engine.test_session.tcp_connected is False

    @pytest.mark.asyncio
    async def test_on_auth_passed(self) -> None:
        bus = EventBus()
        config = _make_config()
        engine = CoreEngine(config=config, bus=bus)
        await engine._on_auth_passed({"connection_id": "1"})
        assert engine.test_session.auth_done is True
        assert engine.test_session.auth_validation_passed is True

    @pytest.mark.asyncio
    async def test_on_auth_failed(self) -> None:
        bus = EventBus()
        config = _make_config()
        engine = CoreEngine(config=config, bus=bus)
        await engine._on_auth_failed({"connection_id": "1", "reasons": ["IMEI mismatch"]})
        assert engine.test_session.auth_done is True
        assert engine.test_session.auth_validation_passed is False

    @pytest.mark.asyncio
    async def test_start_session_activates(self) -> None:
        bus = EventBus()
        config = _make_config()
        engine = CoreEngine(config=config, bus=bus)
        creds = _make_credentials()
        await engine.start_session(creds)
        assert engine.test_session.state == SessionState.ACTIVE
        assert engine.test_session.config_snapshot is not None
        assert engine.test_session.credentials_snapshot is not None

    @pytest.mark.asyncio
    async def test_start_session_emits_event(self) -> None:
        bus = EventBus()
        config = _make_config()
        engine = CoreEngine(config=config, bus=bus)
        received = []
        bus.on("session.started", lambda d: received.append(d))
        await engine.start_session()
        assert len(received) == 1
        assert "timestamp" in received[0]

    @pytest.mark.asyncio
    async def test_stop_session_deactivates(self) -> None:
        bus = EventBus()
        config = _make_config()
        engine = CoreEngine(config=config, bus=bus)
        engine.test_session.state = SessionState.ACTIVE
        await engine.stop_session()
        assert engine.test_session.state == SessionState.COMPLETED
        assert engine.test_session.completed_at is not None

    @pytest.mark.asyncio
    async def test_stop_session_emits_event(self) -> None:
        bus = EventBus()
        config = _make_config()
        engine = CoreEngine(config=config, bus=bus)
        engine.test_session.test_results["7.3"] = TestResult(
            test_name="7.3", passed=True, reasons=[],
            steps_completed=16, steps_total=16, started_at=1000.0,
        )
        received = []
        bus.on("session.completed", lambda d: received.append(d))
        await engine.stop_session()
        assert len(received) == 1
        assert "7.3" in received[0]["test_results"]

    @pytest.mark.asyncio
    async def test_on_network_off_resets_and_emits(self) -> None:
        bus = EventBus()
        config = _make_config()
        engine = CoreEngine(config=config, bus=bus)
        engine.test_session.tcp_connected = True
        engine.test_session.auth_done = True
        received = []
        bus.on("session.statuses_reset", lambda d: received.append(d))

        await engine.on_network_off()

        assert engine.test_session.tcp_connected is False
        assert engine.test_session.auth_done is False
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_start_session_without_credentials_uses_empty(self) -> None:
        bus = EventBus()
        config = _make_config()
        engine = CoreEngine(config=config, bus=bus)
        await engine.start_session()
        assert engine.test_session.state == SessionState.ACTIVE
        assert engine.test_session.credentials_snapshot is not None
        assert engine.test_session.credentials_snapshot["imei"] == ""
