"""Тесты CoreEngine API для CLI (задача 9.0)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.config import Config
from core.event_bus import EventBus


def _make_config(tmp_path: Path | None = None) -> Config:
    """Создать минимальную конфигурацию через JSON-файл."""
    if tmp_path is None:
        import tempfile
        tmp_path = Path(tempfile.mkdtemp())

    cfg_file = tmp_path / "settings.json"
    cfg_data = {
        "gost_version": "2015",
        "tcp_port": 3001,
        "tcp_host": "0.0.0.0",
        "cmw500": {"ip": "192.168.1.100", "timeout": 5, "retries": 3},
        "timeouts": {"TL_RESPONSE_TO": 5, "TL_RESEND_ATTEMPTS": 3, "TL_RECONNECT_TO": 30},
        "logging": {"level": "INFO", "dir": "./logs", "rotation": "daily"},
    }
    cfg_file.write_text(json.dumps(cfg_data))
    return Config.from_file(str(cfg_file))


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


@pytest.fixture
def config(tmp_path: Path) -> Config:
    return _make_config(tmp_path)


# ===== Вспомогательные моки =====


def _patch_all_components():
    """Замокать все компоненты через patch.dict sys.modules."""
    import sys
    import types

    # TcpServerManager
    tcp_mock = MagicMock()
    tcp_mock.start = AsyncMock()
    tcp_mock.stop = AsyncMock()
    tcp_cls = MagicMock(return_value=tcp_mock)

    # Cmw500Controller
    cmw_mock = MagicMock()
    cmw_mock.connect = AsyncMock()
    cmw_mock.disconnect = AsyncMock()
    cmw_mock.get_status = AsyncMock(return_value={
        "IMEI": "351234567890123",
        "IMSI": "250011234567890",
        "RSSI": -65,
        "status": "registered",
    })
    cmw_mock.is_connected = True
    cmw_cls = MagicMock(return_value=cmw_mock)

    # SessionManager
    sess_cls = MagicMock()

    # LogManager
    log_mock = MagicMock()
    log_mock.get_stats = MagicMock(return_value={"packets": 42, "connections": 3})
    log_cls = MagicMock(return_value=log_mock)

    # ScenarioManager
    scenario_ctx = MagicMock()
    scenario_ctx.history = []
    scenario_metadata = MagicMock()
    scenario_metadata.name = "test"
    scenario_mock = MagicMock()
    scenario_mock.load = MagicMock()
    scenario_mock.execute = AsyncMock(return_value="PASS")
    scenario_mock.context = scenario_ctx
    scenario_mock.metadata = scenario_metadata
    scenario_cls = MagicMock(return_value=scenario_mock)

    # ScenarioParser (нужны для start())
    parser_v1 = MagicMock()
    parser_registry_cls = MagicMock()
    parser_registry_instance = MagicMock()
    parser_registry_instance.detect_and_create = MagicMock(return_value=parser_v1)
    parser_registry_cls.return_value = parser_registry_instance
    parser_factory_cls = MagicMock()
    parser_factory_instance = MagicMock()
    parser_factory_instance.create = MagicMock(return_value=parser_v1)
    parser_factory_cls.return_value = parser_factory_instance

    # PacketDispatcher
    pkt_cls = MagicMock()

    # CommandDispatcher
    cmd_cls = MagicMock()

    # ReplaySource
    replay_mock = MagicMock()
    replay_mock.replay = AsyncMock(return_value={
        "packets_processed": 10,
        "duplicates_skipped": 2,
        "errors": 0,
    })
    replay_cls = MagicMock(return_value=replay_mock)

    # Export
    export_mod = types.ModuleType("core.export")
    export_mod.export_csv = MagicMock(return_value={"rows": 10, "file": "out.csv"})
    export_mod.export_json = MagicMock(return_value={"rows": 10, "file": "out.json"})

    patchers = []
    parser_mod = types.ModuleType("core.scenario_parser")
    parser_mod.ScenarioParserV1 = parser_v1
    parser_mod.ScenarioParserRegistry = parser_registry_cls
    parser_mod.ScenarioParserFactory = parser_factory_cls

    mod_map = {
        "core.tcp_server": types.ModuleType("core.tcp_server"),
        "core.session": types.ModuleType("core.session"),
        "core.logger": types.ModuleType("core.logger"),
        "core.scenario": types.ModuleType("core.scenario"),
        "core.dispatcher": types.ModuleType("core.dispatcher"),
        "core.cmw500": types.ModuleType("core.cmw500"),
        "core.packet_source": types.ModuleType("core.packet_source"),
        "core.export": export_mod,
        "core.scenario_parser": parser_mod,
    }

    mod_map["core.tcp_server"].TcpServerManager = tcp_cls
    mod_map["core.session"].SessionManager = sess_cls
    mod_map["core.logger"].LogManager = log_cls
    mod_map["core.scenario"].ScenarioManager = scenario_cls
    mod_map["core.dispatcher"].PacketDispatcher = pkt_cls
    mod_map["core.dispatcher"].CommandDispatcher = cmd_cls
    mod_map["core.cmw500"].Cmw500Controller = cmw_cls
    mod_map["core.packet_source"].ReplaySource = replay_cls

    for mod_name, mod in mod_map.items():
        p = patch.dict(sys.modules, {mod_name: mod})
        p.start()
        patchers.append(p)

    return patchers, cmw_mock, scenario_mock, replay_mock, log_mock


# ===== Тесты get_status =====


@pytest.mark.asyncio
async def test_get_status_not_running(config: Config, bus: EventBus):
    """get_status до вызова start() — не запущен."""
    from core.engine import CoreEngine

    engine = CoreEngine(config=config, bus=bus)
    status = await engine.get_status()

    assert status["running"] is False
    assert status["port"] == 3001
    assert status["gost_version"] == "2015"


@pytest.mark.asyncio
async def test_get_status_running(config: Config, bus: EventBus):
    """get_status после start() — запущен, компоненты созданы."""
    patchers, *_ = _patch_all_components()
    try:
        from core.engine import CoreEngine

        engine = CoreEngine(config=config, bus=bus)
        await engine.start()

        status = await engine.get_status()

        assert status["running"] is True
        assert status["tcp_server"] == "running"
        assert status["cmw500"] == "connected"
        assert status["session_mgr"] is True
        assert status["log_mgr"] is True
        assert status["scenario_mgr"] is True

        await engine.stop()
    finally:
        for p in reversed(patchers):
            p.stop()


@pytest.mark.asyncio
async def test_get_status_includes_cmw(config: Config, bus: EventBus):
    """get_status включает данные CMW-500."""
    patchers, _cmw_mock, *_ = _patch_all_components()
    try:
        from core.engine import CoreEngine

        engine = CoreEngine(config=config, bus=bus)
        await engine.start()

        status = await engine.get_status()

        assert "cmw_details" in status
        assert status["cmw_details"]["IMEI"] == "351234567890123"

        await engine.stop()
    finally:
        for p in reversed(patchers):
            p.stop()


# ===== Тесты cmw_status =====


@pytest.mark.asyncio
async def test_cmw_status_connected(config: Config, bus: EventBus):
    """cmw_status возвращает статус от контроллера."""
    patchers, *_ = _patch_all_components()
    try:
        from core.engine import CoreEngine

        engine = CoreEngine(config=config, bus=bus)
        await engine.start()

        status = await engine.cmw_status()

        assert status["connected"] is True
        assert "status" in status

        await engine.stop()
    finally:
        for p in reversed(patchers):
            p.stop()


@pytest.mark.asyncio
async def test_cmw_status_not_started(config: Config, bus: EventBus):
    """cmw_status до start() — CMW не подключён."""
    from core.engine import CoreEngine

    engine = CoreEngine(config=config, bus=bus)
    status = await engine.cmw_status()

    assert status["connected"] is False
    assert status["error"] is not None


# ===== Тесты run_scenario =====


@pytest.mark.asyncio
async def test_run_scenario_with_connection_id(config: Config, bus: EventBus):
    """run_scenario передаёт connection_id в execute()."""
    patchers, *_ = _patch_all_components()
    try:
        from core.engine import CoreEngine

        engine = CoreEngine(config=config, bus=bus)
        await engine.start()

        scenario_instance = engine.scenario_mgr
        scenario_instance.execute = AsyncMock(return_value="PASS")
        scenario_instance.context.history = [MagicMock(status="PASS")]
        scenario_instance.metadata = MagicMock(name="auth")
        scenario_instance.load = MagicMock()

        result = await engine.run_scenario("scenarios/auth/", connection_id="conn-123")

        assert result["status"] == "PASS"
        scenario_instance.execute.assert_awaited_once()
        call_kwargs = scenario_instance.execute.call_args
        assert call_kwargs[1]["connection_id"] == "conn-123"

        await engine.stop()
    finally:
        for p in reversed(patchers):
            p.stop()


@pytest.mark.asyncio
async def test_run_scenario_not_started(config: Config, bus: EventBus):
    """run_scenario без start() — ошибка."""
    from core.engine import CoreEngine

    engine = CoreEngine(config=config, bus=bus)

    with pytest.raises(RuntimeError, match="не запущен"):
        await engine.run_scenario("scenarios/auth/")


@pytest.mark.asyncio
async def test_run_scenario_error(config: Config, bus: EventBus):
    """run_scenario — execute() выбрасывает исключение."""
    patchers, *_ = _patch_all_components()
    try:
        from core.engine import CoreEngine

        engine = CoreEngine(config=config, bus=bus)
        await engine.start()

        engine.scenario_mgr.load.side_effect = FileNotFoundError("scenario.json not found")

        result = await engine.run_scenario("scenarios/bad/")

        assert result["status"] == "error"
        assert "scenario.json not found" in result["error"]

        await engine.stop()
    finally:
        for p in reversed(patchers):
            p.stop()


# ===== Тесты replay =====


@pytest.mark.asyncio
async def test_replay_success(config: Config, bus: EventBus):
    """replay вызывает ReplaySource.replay."""
    patchers, _, _, _replay_mock, *_ = _patch_all_components()
    try:
        from core.engine import CoreEngine

        engine = CoreEngine(config=config, bus=bus)
        await engine.start()

        result = await engine.replay("logs/session.jsonl", "scenarios/auth/")

        assert result["packets_processed"] == 10
        assert result["duplicates_skipped"] == 2

        await engine.stop()
    finally:
        for p in reversed(patchers):
            p.stop()


@pytest.mark.asyncio
async def test_replay_not_started(config: Config, bus: EventBus):
    """replay без start() — ошибка."""
    from core.engine import CoreEngine

    engine = CoreEngine(config=config, bus=bus)

    with pytest.raises(RuntimeError, match="не запущен"):
        await engine.replay("logs/session.jsonl", None)


# ===== Тесты export =====


@pytest.mark.asyncio
async def test_export_csv(config: Config, bus: EventBus):
    """export в CSV вызывает export_csv."""
    patchers, *_ = _patch_all_components()
    try:
        from core.engine import CoreEngine

        engine = CoreEngine(config=config, bus=bus)
        await engine.start()

        result = await engine.export("packets", "csv", "out.csv")

        assert result["file"] == "out.csv"
        assert result["rows"] == 10

        await engine.stop()
    finally:
        for p in reversed(patchers):
            p.stop()


@pytest.mark.asyncio
async def test_export_json(config: Config, bus: EventBus):
    """export в JSON вызывает export_json."""
    patchers, *_ = _patch_all_components()
    try:
        from core.engine import CoreEngine

        engine = CoreEngine(config=config, bus=bus)
        await engine.start()

        result = await engine.export("scenarios", "json", "out.json")

        assert result["rows"] == 10

        await engine.stop()
    finally:
        for p in reversed(patchers):
            p.stop()


@pytest.mark.asyncio
async def test_export_not_started(config: Config, bus: EventBus):
    """export без start() — ошибка."""
    from core.engine import CoreEngine

    engine = CoreEngine(config=config, bus=bus)

    with pytest.raises(RuntimeError, match="не запущен"):
        await engine.export("packets", "csv", "out.csv")


@pytest.mark.asyncio
async def test_export_unsupported_format(config: Config, bus: EventBus):
    """export с неподдерживаемым форматом — ошибка."""
    patchers, *_ = _patch_all_components()
    try:
        from core.engine import CoreEngine

        engine = CoreEngine(config=config, bus=bus)
        await engine.start()

        with pytest.raises(ValueError, match="Неподдерживаемый формат"):
            await engine.export("packets", "xml", "out.xml")

        await engine.stop()
    finally:
        for p in reversed(patchers):
            p.stop()


# ===== Тесты get_log_stats =====


@pytest.mark.asyncio
async def test_get_log_stats(config: Config, bus: EventBus):
    """get_log_stats возвращает статистику LogManager."""
    patchers, _, _, _, _log_mock = _patch_all_components()
    try:
        from core.engine import CoreEngine

        engine = CoreEngine(config=config, bus=bus)
        await engine.start()

        stats = await engine.get_log_stats()

        assert stats["packets"] == 42
        assert stats["connections"] == 3

        await engine.stop()
    finally:
        for p in reversed(patchers):
            p.stop()


@pytest.mark.asyncio
async def test_get_log_stats_not_started(config: Config, bus: EventBus):
    """get_log_stats без start() — пустая статистика."""
    from core.engine import CoreEngine

    engine = CoreEngine(config=config, bus=bus)

    stats = await engine.get_log_stats()

    assert stats["packets"] == 0
    assert stats["running"] is False


# ===== Интеграция: статус после остановки =====


@pytest.mark.asyncio
async def test_status_after_stop(config: Config, bus: EventBus):
    """get_status после stop() показывает остановленное состояние."""
    patchers, *_ = _patch_all_components()
    try:
        from core.engine import CoreEngine

        engine = CoreEngine(config=config, bus=bus)
        await engine.start()
        await engine.stop()

        status = await engine.get_status()

        assert status["running"] is False
        assert status["tcp_server"] == "stopped"
        assert status["cmw500"] == "disconnected"
    finally:
        for p in reversed(patchers):
            p.stop()


# ===== Дополнительные ветки покрытия =====


@pytest.mark.asyncio
async def test_start_idempotent(config: Config, bus: EventBus):
    """Повторный вызов start() игнорируется."""
    patchers, *_ = _patch_all_components()
    try:
        from core.engine import CoreEngine

        engine = CoreEngine(config=config, bus=bus)
        await engine.start()
        await engine.start()  # не должен вызвать ошибки

        assert engine.is_running

        await engine.stop()
    finally:
        for p in reversed(patchers):
            p.stop()


@pytest.mark.asyncio
async def test_stop_idempotent(config: Config, bus: EventBus):
    """Повторный вызов stop() игнорируется."""
    from core.engine import CoreEngine

    engine = CoreEngine(config=config, bus=bus)
    await engine.stop()  # не должен вызвать ошибки
    assert not engine.is_running


@pytest.mark.asyncio
async def test_str_representation(config: Config, bus: EventBus):
    """__str__ возвращает компактное представление."""
    from core.engine import CoreEngine

    engine = CoreEngine(config=config, bus=bus)
    s = str(engine)

    assert "stopped" in s
    assert "disconnected" in s
    assert str(config.tcp_port) in s

    # После start()
    patchers, *_ = _patch_all_components()
    try:
        engine2 = CoreEngine(config=config, bus=bus)
        await engine2.start()
        s2 = str(engine2)
        assert "running" in s2
        assert "connected" in s2
        await engine2.stop()
    finally:
        for p in reversed(patchers):
            p.stop()


@pytest.mark.asyncio
async def test_start_failure_cleans_up(config: Config, bus: EventBus):
    """Ошибка при start() корректно чистит компоненты."""
    patchers, cmw_mock, *_ = _patch_all_components()
    try:
        # Сломать подключение CMW
        cmw_mock.connect.side_effect = RuntimeError("CMW недоступен")

        from core.engine import CoreEngine

        engine = CoreEngine(config=config, bus=bus)

        with pytest.raises(RuntimeError, match="CMW недоступен"):
            await engine.start()

        # Все компоненты должны быть очищены
        assert engine.cmw500 is None
        assert engine.tcp_server is None
        assert engine.session_mgr is None
    finally:
        for p in reversed(patchers):
            p.stop()


@pytest.mark.asyncio
async def test_get_status_cmw_error(config: Config, bus: EventBus):
    """get_status — CMW подключён, но get_status() падает."""
    patchers, cmw_mock, *_ = _patch_all_components()
    try:
        cmw_mock.get_status.side_effect = RuntimeError("SCPI timeout")

        from core.engine import CoreEngine

        engine = CoreEngine(config=config, bus=bus)
        await engine.start()

        status = await engine.get_status()

        assert status["running"] is True
        assert status["cmw_details"] is None  # ошибка перехвачена

        await engine.stop()
    finally:
        for p in reversed(patchers):
            p.stop()


@pytest.mark.asyncio
async def test_cmw_status_get_status_error(config: Config, bus: EventBus):
    """cmw_status — get_status() выбрасывает исключение."""
    patchers, cmw_mock, *_ = _patch_all_components()
    try:
        cmw_mock.get_status.side_effect = RuntimeError("SCPI timeout")

        from core.engine import CoreEngine

        engine = CoreEngine(config=config, bus=bus)
        await engine.start()

        status = await engine.cmw_status()

        assert status["connected"] is False
        assert "SCPI timeout" in status["error"]

        await engine.stop()
    finally:
        for p in reversed(patchers):
            p.stop()


@pytest.mark.asyncio
async def test_run_scenario_scenario_mgr_none(config: Config, bus: EventBus):
    """run_scenario — scenario_mgr не инициализирован."""
    patchers, *_ = _patch_all_components()
    try:
        from core.engine import CoreEngine

        engine = CoreEngine(config=config, bus=bus)
        await engine.start()
        engine.scenario_mgr = None  # симулируем потерю

        result = await engine.run_scenario("scenarios/auth/")

        assert result["status"] == "error"
        assert "не инициализирован" in result["error"]

        await engine.stop()
    finally:
        for p in reversed(patchers):
            p.stop()


@pytest.mark.asyncio
async def test_get_log_stats_exception(config: Config, bus: EventBus):
    """get_log_stats — LogManager.get_stats() выбрасывает исключение."""
    patchers, _, _, _, log_mock = _patch_all_components()
    try:
        log_mock.get_stats.side_effect = RuntimeError("log dir not found")

        from core.engine import CoreEngine

        engine = CoreEngine(config=config, bus=bus)
        await engine.start()

        stats = await engine.get_log_stats()

        assert stats["packets"] == 0
        assert stats["running"] is True

        await engine.stop()
    finally:
        for p in reversed(patchers):
            p.stop()


@pytest.mark.asyncio
async def test_cleanup_calls_dispatcher_stop(config: Config, bus: EventBus):
    """_cleanup вызывает stop() у диспетчеров."""
    patchers, *_ = _patch_all_components()
    try:
        from core.engine import CoreEngine

        engine = CoreEngine(config=config, bus=bus)
        await engine.start()

        # Запомним что stop был вызван
        pkt_stop_called = False
        cmd_stop_called = False
        orig_pkt_stop = engine.packet_dispatcher.stop
        orig_cmd_stop = engine.command_dispatcher.stop

        def pkt_stop():
            nonlocal pkt_stop_called
            pkt_stop_called = True
            return orig_pkt_stop()

        def cmd_stop():
            nonlocal cmd_stop_called
            cmd_stop_called = True
            return orig_cmd_stop()

        engine.packet_dispatcher.stop = pkt_stop  # type: ignore
        engine.command_dispatcher.stop = cmd_stop  # type: ignore

        await engine.stop()

        assert pkt_stop_called, "PacketDispatcher.stop() не вызван"
        assert cmd_stop_called, "CommandDispatcher.stop() не вызван"
    finally:
        for p in reversed(patchers):
            p.stop()
