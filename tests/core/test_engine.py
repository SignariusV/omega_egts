"""Тесты для CoreEngine — базовые свойства (без реальных компонентов)."""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.config import Config
from core.engine import CoreEngine
from core.event_bus import EventBus


def _tmp_config() -> Config:
    """Создать конфигурацию из временного JSON-файла."""
    d = Path(tempfile.mkdtemp())
    f = d / "settings.json"
    f.write_text(json.dumps({
        "gost_version": "2015",
        "tcp_port": 8090,
        "tcp_host": "0.0.0.0",
        "cmw500": {"ip": "127.0.0.1", "timeout": 5, "retries": 3},
        "timeouts": {"TL_RESPONSE_TO": 5},
        "logging": {"level": "INFO", "dir": "./logs", "rotation": "daily"},
    }))
    return Config.from_file(str(f))


def _patch_components():
    """Замокать все модули компонентов."""
    import sys
    import types

    tcp = MagicMock(start=AsyncMock(), stop=AsyncMock())
    cmw = MagicMock(connect=AsyncMock(), disconnect=AsyncMock(),
                     get_status=AsyncMock(return_value={}),
                     configure_gsm_signaling=AsyncMock(),
                     configure_sms=AsyncMock(),
                     configure_dau=AsyncMock())
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

    ps = [patch.dict(sys.modules, {k: v}) for k, v in mods.items()]
    for p in ps:
        p.start()
    return ps, tcp, cmw


class TestCoreEngineStartStop:
    """Тесты запуска и остановки CoreEngine."""

    @pytest.mark.asyncio
    async def test_start_emits_server_started(self) -> None:
        """start() публикует событие server.started с портом и версией ГОСТ."""
        patchers, *_ = _patch_components()
        try:
            bus = EventBus()
            config = _tmp_config()
            engine = CoreEngine(config=config, bus=bus)

            received_events: list = []
            bus.on("server.started", lambda data: received_events.append(data))

            await engine.start()

            assert len(received_events) == 1
            assert received_events[0]["port"] == 8090
            assert received_events[0]["gost_version"] == "2015"
        finally:
            for p in reversed(patchers):
                p.stop()

    @pytest.mark.asyncio
    async def test_stop_emits_server_stopped(self) -> None:
        """stop() публикует событие server.stopped с причиной."""
        patchers, *_ = _patch_components()
        try:
            bus = EventBus()
            config = _tmp_config()
            engine = CoreEngine(config=config, bus=bus)

            received_events: list = []
            bus.on("server.stopped", lambda data: received_events.append(data))

            await engine.start()
            await engine.stop()

            assert len(received_events) == 1
            assert received_events[0]["reason"] == "shutdown"
        finally:
            for p in reversed(patchers):
                p.stop()

    @pytest.mark.asyncio
    async def test_stop_without_start_does_not_crash(self) -> None:
        """stop() без вызова start() не падает."""
        bus = EventBus()
        config = _tmp_config()
        engine = CoreEngine(config=config, bus=bus)

        await engine.stop()  # Должно пройти без исключений


class TestCoreEngineIdempotency:
    """Тесты идемпотентности и повторного запуска."""

    @pytest.mark.asyncio
    async def test_start_is_idempotent(self) -> None:
        """Повторный start() не дублирует событие server.started."""
        patchers, *_ = _patch_components()
        try:
            bus = EventBus()
            config = _tmp_config()
            engine = CoreEngine(config=config, bus=bus)

            received_events: list = []
            bus.on("server.started", lambda data: received_events.append(data))

            await engine.start()
            await engine.start()  # Второй вызов — игнорируется

            assert len(received_events) == 1
        finally:
            for p in reversed(patchers):
                p.stop()

    @pytest.mark.asyncio
    async def test_restart_after_stop(self) -> None:
        """После stop() можно снова вызвать start()."""
        patchers, *_ = _patch_components()
        try:
            bus = EventBus()
            config = _tmp_config()
            engine = CoreEngine(config=config, bus=bus)

            start_events: list = []
            bus.on("server.started", lambda data: start_events.append(data))

            await engine.start()
            await engine.stop()
            await engine.start()

            assert len(start_events) == 2  # Два start — два события
        finally:
            for p in reversed(patchers):
                p.stop()


class TestCoreEngineState:
    """Тесты проверки состояния."""

    @pytest.mark.asyncio
    async def test_is_running_after_start(self) -> None:
        """is_running == True после start()."""
        patchers, *_ = _patch_components()
        try:
            bus = EventBus()
            config = _tmp_config()
            engine = CoreEngine(config=config, bus=bus)

            assert not engine.is_running
            await engine.start()
            assert engine.is_running
        finally:
            for p in reversed(patchers):
                p.stop()

    @pytest.mark.asyncio
    async def test_is_running_after_stop(self) -> None:
        """is_running == False после stop()."""
        patchers, *_ = _patch_components()
        try:
            bus = EventBus()
            config = _tmp_config()
            engine = CoreEngine(config=config, bus=bus)

            await engine.start()
            await engine.stop()
            assert not engine.is_running
        finally:
            for p in reversed(patchers):
                p.stop()


class TestCoreEngineCleanup:
    """Тесты корректной очистки при ошибке."""

    @pytest.mark.asyncio
    async def test_cleanup_on_start_failure(self) -> None:
        """Если компонент не запустился — остальные очищаются."""
        patchers, _, cmw_mock = _patch_components()
        try:
            cmw_mock.connect.side_effect = RuntimeError("CMW недоступен")

            bus = EventBus()
            config = _tmp_config()
            engine = CoreEngine(config=config, bus=bus)

            with pytest.raises(RuntimeError, match="CMW недоступен"):
                await engine.start()

            assert engine.cmw500 is None
            assert engine.tcp_server is None
            assert engine.session_mgr is None
        finally:
            for p in reversed(patchers):
                p.stop()

    @pytest.mark.asyncio
    async def test_cleanup_is_idempotent(self) -> None:
        """Многократный вызов _cleanup не падает."""
        bus = EventBus()
        config = _tmp_config()
        engine = CoreEngine(config=config, bus=bus)

        await engine._cleanup()
        await engine._cleanup()  # Второй вызов — без ошибок
        assert not engine._started


class TestCoreEngineStr:
    """Тесты строкового представления."""

    @pytest.mark.asyncio
    async def test_str_when_stopped(self) -> None:
        """__str__ показывает stopped, когда система не запущена."""
        bus = EventBus()
        config = _tmp_config()
        engine = CoreEngine(config=config, bus=bus)

        result = str(engine)
        assert "stopped" in result
        assert "port=8090" in result
        assert "cmw=disconnected" in result
        assert "gost=2015" in result

    @pytest.mark.asyncio
    async def test_str_when_running(self) -> None:
        """__str__ показывает running, когда система запущена."""
        patchers, *_ = _patch_components()
        try:
            bus = EventBus()
            config = _tmp_config()
            engine = CoreEngine(config=config, bus=bus)

            await engine.start()
            result = str(engine)
            assert "running" in result
            assert "cmw=connected" in result
        finally:
            for p in reversed(patchers):
                p.stop()
