# OMEGA_EGTS GUI
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Qt, Signal
from enum import Enum


class StatusColor(Enum):
    GREEN = "#4EC9B0"
    RED = "#F44747"
    YELLOW = "#CE9178"
    GREY = "#808080"


class StatusIndicator(QWidget):
    clicked = Signal()

    def __init__(self, color: str | StatusColor = StatusColor.YELLOW, parent=None):
        super().__init__(parent)
        self._color = self._parse_color(color)
        self._setup_ui()

    def _parse_color(self, color: str | StatusColor) -> str:
        if isinstance(color, StatusColor):
            return color.value
        return color if color.startswith("#") else StatusColor.YELLOW.value

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self._dot = QLabel()
        self._dot.setFixedSize(10, 10)
        self._dot.setStyleSheet(f"""
            background-color: {self._color};
            border-radius: 5px;
        """)
        layout.addWidget(self._dot)

    def set_color(self, color: str | StatusColor):
        self._color = self._parse_color(color)
        self._dot.setStyleSheet(f"""
            background-color: {self._color};
            border-radius: 5px;
        """)

    def get_color(self) -> str:
        return self._color


class CompactStatusWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(12)

        self._server_indicator = StatusIndicator(StatusColor.GREEN)
        self._server_label = QLabel(":8090")
        layout.addWidget(self._server_indicator)
        layout.addWidget(self._server_label)

        self._cmw_indicator = StatusIndicator(StatusColor.GREEN)
        self._cmw_label = QLabel("Connected")
        layout.addWidget(self._cmw_indicator)
        layout.addWidget(self._cmw_label)

        layout.addStretch()

    def set_server_status(self, running: bool, port: int = 8090):
        color = StatusColor.GREEN if running else StatusColor.RED
        self._server_indicator.set_color(color)
        self._server_label.setText(f":{port}" if running else "Stopped")

    def set_cmw_status(self, connected: bool, status_text: str = ""):
        color = StatusColor.GREEN if connected else StatusColor.RED
        self._cmw_indicator.set_color(color)
        self._cmw_label.setText(status_text if status_text else ("Connected" if connected else "Disconnected"))