# OMEGA_EGTS GUI
from PySide6.QtCore import QObject, Signal
from core.event_bus import EventBus


class EventBridge(QObject):
    """Bridge between CoreEngine EventBus and Qt signals."""

    packet_processed = Signal(dict)
    packet_sent = Signal(dict)
    cmw_status = Signal(dict)
    cmw_connected = Signal(dict)
    cmw_disconnected = Signal()
    cmw_error = Signal(str)
    server_started = Signal(dict)
    server_stopped = Signal()
    connection_changed = Signal(dict)
    scenario_step = Signal(dict)
    command_sent = Signal(dict)
    command_error = Signal(dict)

    def __init__(self, bus: EventBus, parent=None):
        super().__init__(parent)
        self._bus = bus
        self._subscribe()

    def _subscribe(self):
        bus = self._bus
        bus.on("packet.processed", self._on_packet_processed)
        bus.on("packet.sent", self._on_packet_sent)
        bus.on("cmw.status", self._on_cmw_status)
        bus.on("cmw.connected", self._on_cmw_connected)
        bus.on("cmw.disconnected", self._on_cmw_disconnected)
        bus.on("cmw.error", self._on_cmw_error)
        bus.on("server.started", self._on_server_started)
        bus.on("server.stopped", self._on_server_stopped)
        bus.on("connection.changed", self._on_connection_changed)
        bus.on("scenario.step", self._on_scenario_step)
        bus.on("command.sent", self._on_command_sent)
        bus.on("command.error", self._on_command_error)

    def _on_packet_processed(self, data):
        self.packet_processed.emit(data)

    def _on_packet_sent(self, data):
        self.packet_sent.emit(data)

    def _on_cmw_status(self, data):
        self.cmw_status.emit(data)

    def _on_cmw_connected(self, data):
        self.cmw_connected.emit(data)

    def _on_cmw_disconnected(self, data):
        self.cmw_disconnected.emit()

    def _on_cmw_error(self, data):
        error_msg = data.get("error", "") if isinstance(data, dict) else str(data)
        self.cmw_error.emit(error_msg)

    def _on_server_started(self, data):
        self.server_started.emit(data)

    def _on_server_stopped(self, data):
        self.server_stopped.emit()

    def _on_connection_changed(self, data):
        self.connection_changed.emit(data)

    def _on_scenario_step(self, data):
        self.scenario_step.emit(data)

    def _on_command_sent(self, data):
        self.command_sent.emit(data)

    def _on_command_error(self, data):
        self.command_error.emit(data)