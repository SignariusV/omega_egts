# OMEGA_EGTS GUI
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QFormLayout, QLabel, QPushButton
)
from PySide6.QtCore import Signal, Slot
from gui.dashboard.card_base import BaseCard, DisplayState
from gui.widgets.status_indicator import CompactStatusWidget


class SystemStatusCard(BaseCard):
    toggle_server_requested = Signal()

    def __init__(self, card_id: str = "system_status", cmw_ip: str = "", parent=None):
        super().__init__("System Status", card_id=card_id, parent=parent)
        self._server_running = False
        self._cmw_connected = False
        self._server_port = 8090
        self._cmw_data = {}
        self._cmw_ip = cmw_ip
        self._expanded_ui_ready = False
        self._build_widgets()
        self.finish_init()

    def _build_widgets(self):
        self._compact_widget = CompactStatusWidget()
        self._build_expanded_ui()
        self.set_views(self._compact_widget, self._expanded_widget)

    def _build_expanded_ui(self):
        self._expanded_widget = QWidget()
        layout = QVBoxLayout(self._expanded_widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        server_group = QGroupBox("Server")
        server_layout = QFormLayout(server_group)
        self._server_status_label = QLabel("Stopped")
        self._server_port_label = QLabel("-")
        server_layout.addRow("Status:", self._server_status_label)
        server_layout.addRow("Port:", self._server_port_label)

        self._toggle_server_btn = QPushButton("Start Server")
        self._toggle_server_btn.setObjectName("toggleServerButton")
        self._toggle_server_btn.setToolTip("Toggle server (Ctrl+R)")
        self._toggle_server_btn.setProperty("serverState", "stopped")
        self._toggle_server_btn.clicked.connect(self.toggle_server_requested.emit)
        server_layout.addRow(self._toggle_server_btn)
        layout.addWidget(server_group)

        cmw_group = QGroupBox("CMW-500")
        cmw_layout = QFormLayout(cmw_group)
        self._cmw_status_label = QLabel("Disconnected")
        self._cmw_ip_label = QLabel(self._cmw_ip or "-")
        self._cmw_mode_label = QLabel("-")
        self._cmw_imei_label = QLabel("-")
        self._cmw_imsi_label = QLabel("-")
        self._cmw_rssi_label = QLabel("-")
        cmw_layout.addRow("Status:", self._cmw_status_label)
        cmw_layout.addRow("IP:", self._cmw_ip_label)
        cmw_layout.addRow("Mode:", self._cmw_mode_label)
        cmw_layout.addRow("IMEI:", self._cmw_imei_label)
        cmw_layout.addRow("IMSI:", self._cmw_imsi_label)
        cmw_layout.addRow("RSSI:", self._cmw_rssi_label)
        layout.addWidget(cmw_group)
        layout.addStretch()
        self._expanded_ui_ready = True
        self._update_server_ui()
        self._update_cmw_ui()

    def update_content_visibility(self, state: DisplayState):
        super().update_content_visibility(state)
        self._update_compact_server()
        self._update_compact_cmw()

    @Slot(dict)
    def on_server_started(self, data: dict):
        self._server_running = True
        self._server_port = data.get("port", 8090)
        self._update_server_ui()
        self._update_compact_server()

    @Slot(dict)
    def on_server_stopped(self, data: dict = None):
        self._server_running = False
        self._update_server_ui()
        self._update_compact_server()

    @Slot(dict)
    def on_cmw_connected(self, data: dict):
        self._cmw_connected = True
        self._cmw_data.update(data)
        if "ip" in data:
            self._cmw_ip = data["ip"]
        self._update_cmw_ui()
        self._update_compact_cmw()

    @Slot()
    def on_cmw_disconnected(self):
        self._cmw_connected = False
        self._cmw_data.clear()
        self._update_cmw_ui()
        self._update_compact_cmw()

    @Slot(dict)
    def on_cmw_status(self, data: dict):
        if data:
            self._cmw_data.update(data)
            self._update_cmw_ui()

    def _update_server_ui(self):
        if not self._expanded_ui_ready:
            return
        self._server_status_label.setText("Running" if self._server_running else "Stopped")
        self._server_port_label.setText(str(self._server_port) if self._server_running else "-")
        if self._server_running:
            self._toggle_server_btn.setText("Stop Server")
            self._toggle_server_btn.setProperty("serverState", "running")
        else:
            self._toggle_server_btn.setText("Start Server")
            self._toggle_server_btn.setProperty("serverState", "stopped")
        self._toggle_server_btn.style().unpolish(self._toggle_server_btn)
        self._toggle_server_btn.style().polish(self._toggle_server_btn)

    def _update_cmw_ui(self):
        if not self._expanded_ui_ready:
            return
        status = "Connected" if self._cmw_connected else "Disconnected"
        self._cmw_status_label.setText(status)
        self._cmw_ip_label.setText(self._cmw_ip or "-")
        self._cmw_imei_label.setText(str(self._cmw_data.get("imei", "-")))
        self._cmw_imsi_label.setText(str(self._cmw_data.get("imsi", "-")))
        self._cmw_rssi_label.setText(str(self._cmw_data.get("rssi", "-")))
        mode = "Simulator" if self._cmw_data.get("simulate", False) else "Real"
        self._cmw_mode_label.setText(mode)

    def _update_compact_server(self):
        if hasattr(self._compact_widget, 'set_server_status'):
            self._compact_widget.set_server_status(self._server_running, self._server_port)

    def _update_compact_cmw(self):
        if hasattr(self._compact_widget, 'set_cmw_status'):
            status = "Connected" if self._cmw_connected else "Disconnected"
            mode = ""
            if self._cmw_connected:
                mode = "Simulator" if self._cmw_data.get("simulate", False) else "Real"
            self._compact_widget.set_cmw_status(self._cmw_connected, status, mode)

    def is_server_running(self) -> bool:
        return self._server_running

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
