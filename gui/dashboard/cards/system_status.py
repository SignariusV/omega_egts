# OMEGA_EGTS GUI
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QFormLayout, QLabel, QPushButton, QFrame
)
from PySide6.QtCore import Signal, Slot
from gui.dashboard.card_base import BaseCard, DisplayState
from gui.widgets.status_indicator import StatusIndicator, StatusColor, CompactStatusWidget


class SystemStatusCard(BaseCard):
    start_requested = Signal()
    stop_requested = Signal()

    def __init__(self, parent=None):
        super().__init__("System Status", parent)
        self._server_running = False
        self._cmw_connected = False
        self._server_port = 8090
        self._cmw_data = {}
        self._current_widget = None
        self._build_widgets()
        self._show_expanded()

    def _build_widgets(self):
        self._compact_widget = CompactStatusWidget()
        self._expanded_widget = QWidget()
        self._build_expanded_ui()

    def _build_expanded_ui(self):
        layout = QVBoxLayout(self._expanded_widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        server_group = QGroupBox("Server")
        server_layout = QFormLayout(server_group)
        self._server_status_label = QLabel("Stopped")
        self._server_port_label = QLabel("-")
        self._server_uptime_label = QLabel("-")
        server_layout.addRow("Status:", self._server_status_label)
        server_layout.addRow("Port:", self._server_port_label)
        server_layout.addRow("Uptime:", self._server_uptime_label)

        server_buttons = QHBoxLayout()
        self._start_btn = QPushButton("Start Server")
        self._stop_btn = QPushButton("Stop Server")
        self._stop_btn.setEnabled(False)
        self._start_btn.clicked.connect(self.start_requested.emit)
        self._stop_btn.clicked.connect(self.stop_requested.emit)
        server_buttons.addWidget(self._start_btn)
        server_buttons.addWidget(self._stop_btn)
        server_layout.addRow(server_buttons)
        layout.addWidget(server_group)

        cmw_group = QGroupBox("CMW-500")
        cmw_layout = QFormLayout(cmw_group)
        self._cmw_imei_label = QLabel("-")
        self._cmw_imsi_label = QLabel("-")
        self._cmw_rssi_label = QLabel("-")
        self._cmw_ber_label = QLabel("-")
        self._cmw_cs_label = QLabel("-")
        self._cmw_ps_label = QLabel("-")
        cmw_layout.addRow("IMEI:", self._cmw_imei_label)
        cmw_layout.addRow("IMSI:", self._cmw_imsi_label)
        cmw_layout.addRow("RSSI:", self._cmw_rssi_label)
        cmw_layout.addRow("BER:", self._cmw_ber_label)
        cmw_layout.addRow("CS State:", self._cmw_cs_label)
        cmw_layout.addRow("PS State:", self._cmw_ps_label)
        layout.addWidget(cmw_group)
        layout.addStretch()

    def _show_compact(self):
        if self._current_widget != self._compact_widget:
            self._clear_content()
            self.set_content_widget(self._compact_widget)
            self._current_widget = self._compact_widget
            self._update_compact_server()
            self._update_compact_cmw()

    def _show_expanded(self):
        if self._current_widget != self._expanded_widget:
            self._clear_content()
            self.set_content_widget(self._expanded_widget)
            self._current_widget = self._expanded_widget

    def _clear_content(self):
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

    def update_content_visibility(self, state: DisplayState):
        if state == DisplayState.COMPACT:
            self._show_compact()
        else:
            self._show_expanded()

    @Slot()
    def on_server_started(self, data: dict):
        self._server_running = True
        self._server_port = data.get("port", 8090)
        self._update_server_ui()
        self._update_compact_server()

    @Slot()
    def on_server_stopped(self):
        self._server_running = False
        self._update_server_ui()
        self._update_compact_server()

    @Slot()
    def on_cmw_connected(self, data: dict):
        self._cmw_connected = True
        self._cmw_data.update(data)
        self._update_cmw_ui()
        self._update_compact_cmw()

    @Slot()
    def on_cmw_disconnected(self):
        self._cmw_connected = False
        self._cmw_data.clear()
        self._update_cmw_ui()
        self._update_compact_cmw()

    @Slot()
    def on_cmw_status(self, data: dict):
        self._cmw_data.update(data)
        self._update_cmw_ui()

    def _update_server_ui(self):
        if hasattr(self, '_server_status_label'):
            self._server_status_label.setText("Running" if self._server_running else "Stopped")
            self._server_port_label.setText(str(self._server_port) if self._server_running else "-")
            self._start_btn.setEnabled(not self._server_running)
            self._stop_btn.setEnabled(self._server_running)

    def _update_cmw_ui(self):
        if not hasattr(self, '_cmw_imei_label'):
            return
        self._cmw_imei_label.setText(self._cmw_data.get("imei", "-"))
        self._cmw_imsi_label.setText(self._cmw_data.get("imsi", "-"))
        self._cmw_rssi_label.setText(self._cmw_data.get("rssi", "-"))
        self._cmw_ber_label.setText(self._cmw_data.get("ber", "-"))
        self._cmw_cs_label.setText(self._cmw_data.get("cs_state", "-"))
        self._cmw_ps_label.setText(self._cmw_data.get("ps_state", "-"))

    def _update_compact_server(self):
        if hasattr(self._compact_widget, 'set_server_status'):
            self._compact_widget.set_server_status(self._server_running, self._server_port)

    def _update_compact_cmw(self):
        if hasattr(self._compact_widget, 'set_cmw_status'):
            status = "Connected" if self._cmw_connected else "Disconnected"
            self._compact_widget.set_cmw_status(self._cmw_connected, status)

    def get_state(self) -> dict:
        return {
            "server_running": self._server_running,
            "server_port": self._server_port,
            "cmw_connected": self._cmw_connected,
        }

    def set_state(self, state: dict):
        self._server_running = state.get("server_running", False)
        self._server_port = state.get("server_port", 8090)
        self._cmw_connected = state.get("cmw_connected", False)
        self._update_server_ui()
        self._update_cmw_ui()
        self._update_compact_server()
        self._update_compact_cmw()