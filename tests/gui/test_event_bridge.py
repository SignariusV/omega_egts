# OMEGA_EGTS GUI
import pytest
import asyncio
from core.event_bus import EventBus
from gui.bridge.event_bridge import EventBridge


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def bridge(bus, qtbot):
    return EventBridge(bus)


@pytest.mark.asyncio
async def test_packet_processed_signal(bridge, bus, qtbot):
    with qtbot.waitSignal(bridge.packet_processed, timeout=100) as blocker:
        await bus.emit("packet.processed", {"ctx": "test"})
    assert blocker.signal_triggered


@pytest.mark.asyncio
async def test_packet_sent_signal(bridge, bus, qtbot):
    with qtbot.waitSignal(bridge.packet_sent, timeout=100) as blocker:
        await bus.emit("packet.sent", {"data": "sent"})
    assert blocker.signal_triggered


@pytest.mark.asyncio
async def test_cmw_status_signal(bridge, bus, qtbot):
    data = {"rssi": "-65", "imsi": "12345"}
    with qtbot.waitSignal(bridge.cmw_status, timeout=100) as blocker:
        await bus.emit("cmw.status", data)
    assert blocker.args[0]["rssi"] == "-65"


@pytest.mark.asyncio
async def test_cmw_connected_signal(bridge, bus, qtbot):
    data = {"imei": "123456789012345"}
    with qtbot.waitSignal(bridge.cmw_connected, timeout=100) as blocker:
        await bus.emit("cmw.connected", data)
    assert blocker.signal_triggered


@pytest.mark.asyncio
async def test_cmw_disconnected_signal(bridge, bus, qtbot):
    with qtbot.waitSignal(bridge.cmw_disconnected, timeout=100) as blocker:
        await bus.emit("cmw.disconnected", {})
    assert blocker.signal_triggered


@pytest.mark.asyncio
async def test_cmw_error_signal(bridge, bus, qtbot):
    with qtbot.waitSignal(bridge.cmw_error, timeout=100) as blocker:
        await bus.emit("cmw.error", {"error": "Connection lost"})
    assert "Connection lost" in blocker.args[0]


@pytest.mark.asyncio
async def test_server_started_signal(bridge, bus, qtbot):
    data = {"port": 8090}
    with qtbot.waitSignal(bridge.server_started, timeout=100) as blocker:
        await bus.emit("server.started", data)
    assert blocker.args[0]["port"] == 8090


@pytest.mark.asyncio
async def test_server_stopped_signal(bridge, bus, qtbot):
    with qtbot.waitSignal(bridge.server_stopped, timeout=100) as blocker:
        await bus.emit("server.stopped", {})
    assert blocker.signal_triggered


@pytest.mark.asyncio
async def test_connection_changed_signal(bridge, bus, qtbot):
    data = {"state": "connected", "peer": "127.0.0.1"}
    with qtbot.waitSignal(bridge.connection_changed, timeout=100) as blocker:
        await bus.emit("connection.changed", data)
    assert blocker.args[0]["state"] == "connected"


@pytest.mark.asyncio
async def test_scenario_step_signal(bridge, bus, qtbot):
    data = {"step": "auth", "status": "passed", "duration": 1.5}
    with qtbot.waitSignal(bridge.scenario_step, timeout=100) as blocker:
        await bus.emit("scenario.step", data)
    assert blocker.args[0]["step"] == "auth"


@pytest.mark.asyncio
async def test_command_sent_signal(bridge, bus, qtbot):
    data = {"command": "SEND_SMS", "result": "ok"}
    with qtbot.waitSignal(bridge.command_sent, timeout=100) as blocker:
        await bus.emit("command.sent", data)
    assert blocker.args[0]["command"] == "SEND_SMS"


@pytest.mark.asyncio
async def test_command_error_signal(bridge, bus, qtbot):
    data = {"command": "SEND_SMS", "error": "timeout"}
    with qtbot.waitSignal(bridge.command_error, timeout=100) as blocker:
        await bus.emit("command.error", data)
    assert blocker.args[0]["error"] == "timeout"