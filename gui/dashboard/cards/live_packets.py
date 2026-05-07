# OMEGA_EGTS GUI
import re
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView,
    QHeaderView, QLabel, QLineEdit, QComboBox, QPushButton,
    QMessageBox
)
from PySide6.QtCore import Signal, Slot, Qt, QSortFilterProxyModel, QModelIndex
from gui.dashboard.card_base import BaseCard, DisplayState
from gui.widgets.packet_table import PacketTableModel

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


class PacketFilterProxy(QSortFilterProxyModel):
    """Custom filter proxy that supports both text search and channel filtering."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._search_text = ""
        self._channel = "All"
        self._channel_index = -1

    def set_search_text(self, text):
        self._search_text = text

    def set_channel(self, channel, channel_index):
        self._channel = channel
        self._channel_index = channel_index

    def filterAcceptsRow(self, source_row, source_parent):
        model = self.sourceModel()
        if not model:
            return True

        if self._search_text:
            text_match = False
            for col in range(model.columnCount()):
                index = model.index(source_row, col, source_parent)
                data = model.data(index, Qt.ItemDataRole.DisplayRole)
                if data:
                    try:
                        if re.search(self._search_text, str(data), re.IGNORECASE):
                            text_match = True
                            break
                    except re.error:
                        if self._search_text.lower() in str(data).lower():
                            text_match = True
                            break
            if not text_match:
                return False

        if self._channel != "All":
            if self._channel_index < 0:
                return True
            channel_index = model.index(source_row, self._channel_index, source_parent)
            channel_data = model.data(channel_index, Qt.ItemDataRole.DisplayRole)
            if channel_data != self._channel:
                return False

        return True


class CompactProxyModel(QSortFilterProxyModel):
    """Proxy that shows only last N rows."""

    def __init__(self, max_rows=5, parent=None):
        super().__init__(parent)
        self._max_rows = max_rows

    def filterAcceptsRow(self, source_row, source_parent):
        total = self.sourceModel().rowCount()
        return source_row >= total - self._max_rows


class LivePacketsCard(BaseCard):
    def __init__(self, card_id: str = "live_packets", parent=None):
        super().__init__("Live Packets", card_id=card_id, parent=parent)
        self.icon_path = str(PROJECT_ROOT / "gui" / "resources" / "icons" / "packets.svg")
        self._build_widgets()
        self.finish_init()

    def _build_widgets(self):
        self._packet_model = PacketTableModel()
        self._build_expanded_ui()
        self._build_compact_ui()

        self.set_views(self._compact_widget, self._expanded_widget)

    def _build_compact_ui(self):
        self._compact_widget = QWidget()
        layout = QVBoxLayout(self._compact_widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        self._compact_proxy = CompactProxyModel(max_rows=5)
        self._compact_proxy.setSourceModel(self._packet_model)

        self._compact_table = QTableView()
        self._compact_table.setToolTip("Last 5 packets received/transmitted")
        self._compact_table.setModel(self._compact_proxy)
        self._compact_table.setMaximumHeight(80)
        header = self._compact_table.horizontalHeader()
        for i in range(3):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self._compact_table)

        self._counter_label = QLabel("Rx: 0 | Tx: 0")
        self._counter_label.setStyleSheet("font-size: 10px;")
        self._counter_label.setToolTip("Total packet counts")
        layout.addWidget(self._counter_label)

    def _build_expanded_ui(self):
        self._expanded_widget = QWidget()
        layout = QVBoxLayout(self._expanded_widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Filter:"))
        self._filter_input = QLineEdit()
        self._filter_input.setPlaceholderText("Search packets...")
        self._filter_input.setToolTip("Filter packets by any field (regex supported)")
        self._filter_input.textChanged.connect(self._on_search_text_changed)
        toolbar.addWidget(self._filter_input)
        toolbar.addWidget(QLabel("Channel:"))
        self._channel_combo = QComboBox()
        self._channel_combo.addItems(["All", "tcp", "sms"])
        self._channel_combo.setToolTip("Filter by packet channel type (tcp or sms)")
        self._channel_combo.currentTextChanged.connect(self._on_channel_changed)
        toolbar.addWidget(self._channel_combo)
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setToolTip("Clear all packets from table")
        self._clear_btn.clicked.connect(self._on_clear)
        toolbar.addWidget(self._clear_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self._proxy = PacketFilterProxy()
        self._proxy.setSourceModel(self._packet_model)

        self._channel_column_index = -1
        for i, h in enumerate(PacketTableModel.HEADERS):
            if h.lower() == "channel":
                self._channel_column_index = i
                break
        if self._channel_column_index < 0:
            logger = __import__("logging").getLogger(__name__)
            logger.warning("Channel column not found in PacketTableModel.HEADERS")

        self._table = QTableView()
        self._table.setToolTip("All captured packets (double-click for details)")
        self._table.setModel(self._proxy)
        self._table.doubleClicked.connect(self._on_table_double_clicked)
        header = self._table.horizontalHeader()
        for i in range(self._packet_model.columnCount()):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        layout.addWidget(self._table)

        self._stats_label = QLabel("Rx: 0 | Tx: 0")
        self._stats_label.setToolTip("Total received/transmitted packet counts")
        layout.addWidget(self._stats_label)

    def _on_search_text_changed(self, text):
        self._proxy.set_search_text(text)
        self._proxy.invalidateFilter()

    def _on_channel_changed(self, channel):
        self._proxy.set_channel(channel, self._channel_column_index)
        self._proxy.invalidateFilter()

    def _on_clear(self):
        self._packet_model.clear()
        self._stats_label.setText("Rx: 0 | Tx: 0")
        self._counter_label.setText("Rx: 0 | Tx: 0")

    @Slot(QModelIndex)
    def _on_table_double_clicked(self, index):
        proxy = self._table.model()
        source_index = proxy.mapToSource(index)
        if not source_index.isValid():
            return
        row = source_index.row()
        packet = self._packet_model.get_packet(row)
        direction = "RECEIVED" if packet.get("direction") == "rx" else "SENT"
        parts = [
            f"=== {direction} PACKET ===",
            f"Timestamp: {packet.get('timestamp', '')}",
            f"Channel: {packet.get('channel', '')}",
            f"Length: {packet.get('length', 0)} bytes",
            "",
            "--- Basic Info ---",
            f"PID: {packet.get('pid', '')}",
            f"Service: {packet.get('service', '')}",
            f"CRC: {packet.get('crc', '')}",
            f"Duplicate: {packet.get('duplicate', '')}",
        ]
        hex_data = packet.get("hex", "")
        if hex_data:
            parts.extend([
                "",
                "--- Hex Dump ---",
                self._format_hex_dump(hex_data),
            ])
        parsed = packet.get("parsed", {})
        if parsed:
            parts.extend([
                "",
                "--- Parsed Data ---",
            ])
            for key, value in parsed.items():
                if key != "timestamp":
                    parts.append(f"  {key}: {value}")
        QMessageBox.information(self, "Packet Details", "\n".join(parts))

    def _format_hex_dump(self, hex_str: str, bytes_per_line: int = 16) -> str:
        if not hex_str:
            return "(empty)"
        lines = []
        for i in range(0, len(hex_str), bytes_per_line * 2):
            chunk = hex_str[i:i + bytes_per_line * 2]
            ascii_repr = "".join(
                chr(int(chunk[j:j+2], 16)) if 32 <= int(chunk[j:j+2], 16) < 127 else "."
                for j in range(0, len(chunk), 2)
            )
            lines.append(f"  {chunk}  {ascii_repr}")
        return "\n".join(lines)

    def update_content_visibility(self, state: DisplayState):
        super().update_content_visibility(state)

    @Slot()
    def on_packet_processed(self, data: dict):
        ctx = data.get("ctx", {})
        hex_data = ctx.get("hex", "") if ctx else ""
        parsed = ctx.get("parsed", {}) if ctx else {}
        service = parsed.get("service", "?") if parsed else "?"
        packet = {
            "timestamp": data.get("timestamp", ""),
            "pid": data.get("pid", ""),
            "service": service,
            "length": len(hex_data) // 2 if hex_data else 0,
            "channel": data.get("channel", ""),
            "crc": "OK" if ctx.get("crc_valid", False) else "FAIL" if ctx else "",
            "duplicate": "Yes" if ctx.get("is_duplicate", False) else "No" if ctx else "",
            "hex": hex_data,
            "parsed": parsed,
            "direction": "rx"
        }
        self._packet_model.add_packet(packet)
        self._update_stats()

    @Slot()
    def on_packet_sent(self, data: dict):
        hex_data = data.get("hex", "")
        packet = {
            "timestamp": data.get("timestamp", ""),
            "pid": data.get("pid", ""),
            "service": "?",
            "length": len(hex_data) // 2 if hex_data else 0,
            "channel": data.get("channel", ""),
            "crc": "OK",
            "duplicate": "No",
            "hex": hex_data,
            "parsed": {},
            "direction": "tx"
        }
        self._packet_model.add_packet(packet)
        self._update_stats()

    def _update_stats(self):
        rx = self._packet_model.get_rx_count()
        tx = self._packet_model.get_tx_count()
        text = f"Rx: {rx} | Tx: {tx}"
        self._stats_label.setText(text)
        self._counter_label.setText(text)

    def get_state(self) -> dict:
        return {
            "filter_text": self._filter_input.text(),
            "channel": self._channel_combo.currentText(),
        }

    def set_state(self, state: dict):
        if hasattr(self, '_filter_input'):
            self._filter_input.setText(state.get("filter_text", ""))
        if hasattr(self, '_channel_combo'):
            channel = state.get("channel", "All")
            idx = self._channel_combo.findText(channel)
            if idx >= 0:
                self._channel_combo.setCurrentIndex(idx)
