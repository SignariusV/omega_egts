import pytest
from unittest.mock import MagicMock, AsyncMock
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Signal

from gui.core.event_bridge import EventBridge


@pytest.fixture
def event_bus():
    """Мок EventBus."""
    bus = MagicMock()
    bus.on = MagicMock()
    return bus


@pytest.fixture
def event_bridge(event_bus):
    """Экземпляр EventBridge."""
    return EventBridge(event_bus)


def test_event_bridge_signals(event_bridge):
    """Проверка наличия всех сигналов."""
    signals = [
        "server_started", "server_stopped",
        "cmw_connected", "cmw_disconnected",
        "packet_processed", "connection_changed",
        "scenario_step", "scenario_started", "scenario_finished"
    ]
    for signal_name in signals:
        assert hasattr(event_bridge, signal_name), f"Signal {signal_name} not found"
        assert isinstance(getattr(event_bridge, signal_name), Signal)


def test_event_bridge_subscribes_to_events(event_bus):
    """Проверка подписки на события при инициализации."""
    bridge = EventBridge(event_bus)
    # Проверяем, что bus.on был вызван нужное количество раз
    assert event_bus.on.call_count == 9


@pytest.mark.asyncio
async def test_event_bridge_emits_signal(event_bridge):
    """Проверка, что при вызове обработчика сигнал испускается."""
    received_data = None

    def slot(data):
        nonlocal received_data
        received_data = data

    event_bridge.server_started.connect(slot)
    test_data = {"port": 3001}
    await event_bridge._on_server_started(test_data)
    # Даем время на обработку сигнала
    # В реальности Signal emit синхронный, поэтому данные должны быть сразу
    assert received_data == test_data
