# OMEGA_EGTS GUI
from PySide6.QtCore import QObject, Signal
from core.event_bus import EventBus
from typing import Any


class EventBridge(QObject):
    """Bridge between CoreEngine EventBus and Qt signals."""

    packet_processed = Signal(dict)
    packet_sent = Signal(dict)
    cmw_status = Signal(dict)
    cmw_connected = Signal(dict)
    cmw_disconnected = Signal(dict)
    cmw_error = Signal(dict)
    server_started = Signal(dict)
    server_stopped = Signal(dict)
    connection_changed = Signal(dict)
    scenario_step = Signal(dict)
    command_sent = Signal(dict)
    command_error = Signal(dict)

    def __init__(self, bus: EventBus, parent=None):
        super().__init__(parent)
        self._bus = bus
        self._subscribed = False
        self._subscribe()

    def _subscribe(self) -> None:
        if self._subscribed:
            return

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
        self._subscribed = True

    def unsubscribe(self) -> None:
        """Unsubscribe all handlers from the EventBus to prevent memory leaks."""
        if not self._subscribed:
            return

        bus = self._bus
        bus.off("packet.processed", self._on_packet_processed)
        bus.off("packet.sent", self._on_packet_sent)
        bus.off("cmw.status", self._on_cmw_status)
        bus.off("cmw.connected", self._on_cmw_connected)
        bus.off("cmw.disconnected", self._on_cmw_disconnected)
        bus.off("cmw.error", self._on_cmw_error)
        bus.off("server.started", self._on_server_started)
        bus.off("server.stopped", self._on_server_stopped)
        bus.off("connection.changed", self._on_connection_changed)
        bus.off("scenario.step", self._on_scenario_step)
        bus.off("command.sent", self._on_command_sent)
        bus.off("command.error", self._on_command_error)
        self._subscribed = False

    def _on_packet_processed(self, data: dict[str, Any]) -> None:
        self.packet_processed.emit(data)

    def _on_packet_sent(self, data: dict[str, Any]) -> None:
        self.packet_sent.emit(data)

    def _on_cmw_status(self, data: dict[str, Any]) -> None:
        self.cmw_status.emit(data)

    def _on_cmw_connected(self, data: dict[str, Any]) -> None:
        self.cmw_connected.emit(data)

    def _on_cmw_disconnected(self, data: dict[str, Any]) -> None:
        self.cmw_disconnected.emit(data)

    def _on_cmw_error(self, data: dict[str, Any]) -> None:
        if not isinstance(data, dict):
            data = {"error": str(data)}
        self.cmw_error.emit(data)

    def _on_server_started(self, data: dict[str, Any]) -> None:
        self.server_started.emit(data)

    def _on_server_stopped(self, data: dict[str, Any]) -> None:
        self.server_stopped.emit(data)

    def _on_connection_changed(self, data: dict[str, Any]) -> None:
        self.connection_changed.emit(data)

    def _on_scenario_step(self, data: dict[str, Any]) -> None:
        self.scenario_step.emit(data)

    def _on_command_sent(self, data: dict[str, Any]) -> None:
        self.command_sent.emit(data)

    def _on_command_error(self, data: dict[str, Any]) -> None:
        self.command_error.emit(data)
