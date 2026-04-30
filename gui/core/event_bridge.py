from PySide6.QtCore import QObject, Signal
from core.engine import EventBus


class EventBridge(QObject):
    """Мост между асинхронным EventBus и Qt сигналами."""

    server_started = Signal(dict)
    server_stopped = Signal(dict)
    cmw_connected = Signal(dict)
    cmw_disconnected = Signal(dict)
    packet_processed = Signal(dict)
    connection_changed = Signal(dict)
    scenario_step = Signal(dict)
    scenario_started = Signal(dict)
    scenario_finished = Signal(dict)

    def __init__(self, bus: EventBus):
        super().__init__()
        self.bus = bus
        self._subscribe()

    def _subscribe(self):
        """Подписка на события EventBus."""
        self.bus.on("server.started", self._on_server_started)
        self.bus.on("server.stopped", self._on_server_stopped)
        self.bus.on("cmw.connected", self._on_cmw_connected)
        self.bus.on("cmw.disconnected", self._on_cmw_disconnected)
        self.bus.on("packet.processed", self._on_packet_processed)
        self.bus.on("connection.changed", self._on_connection_changed)
        self.bus.on("scenario.step", self._on_scenario_step)
        self.bus.on("scenario.started", self._on_scenario_started)
        self.bus.on("scenario.finished", self._on_scenario_finished)

    async def _on_server_started(self, data: dict):
        self.server_started.emit(data)

    async def _on_server_stopped(self, data: dict):
        self.server_stopped.emit(data)

    async def _on_cmw_connected(self, data: dict):
        self.cmw_connected.emit(data)

    async def _on_cmw_disconnected(self, data: dict):
        self.cmw_disconnected.emit(data)

    async def _on_packet_processed(self, data: dict):
        self.packet_processed.emit(data)

    async def _on_connection_changed(self, data: dict):
        self.connection_changed.emit(data)

    async def _on_scenario_step(self, data: dict):
        self.scenario_step.emit(data)

    async def _on_scenario_started(self, data: dict):
        self.scenario_started.emit(data)

    async def _on_scenario_finished(self, data: dict):
        self.scenario_finished.emit(data)
