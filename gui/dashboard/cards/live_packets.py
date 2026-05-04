# OMEGA_EGTS GUI
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView,
    QHeaderView, QLabel, QLineEdit, QComboBox, QPushButton
)
from PySide6.QtCore import Signal, Slot, Qt, QSortFilterProxyModel, QModelIndex
from gui.dashboard.card_base import BaseCard, DisplayState
from gui.widgets.packet_table import PacketTableModel


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

        # Check text search (regex) across all columns
        if self._search_text:
            text_match = False
            for col in range(model.columnCount()):
                index = model.index(source_row, col, source_parent)
                data = model.data(index, Qt.ItemDataRole.DisplayRole)
                if data:
                    try:
                        import re
                        if re.search(self._search_text, str(data), re.IGNORECASE):
                            text_match = True
                            break
                    except re.error:
                        if self._search_text.lower() in str(data).lower():
                            text_match = True
                            break
            if not text_match:
                return False

        # Check exact channel match
        if self._channel != "All" and self._channel_index >= 0:
            channel_index = model.index(source_row, self._channel_index, source_parent)
            channel_data = model.data(channel_index, Qt.ItemDataRole.DisplayRole)
            if channel_data != self._channel:
                return False

        return True


class LivePacketsCard(BaseCard):
    def __init__(self, parent=None):
        super().__init__("Live Packets", parent)
        self._current_widget = None
        self._build_widgets()
        self._show_expanded()
        self.finish_init()

    def _build_widgets(self):
        self._compact_widget = self._create_compact_widget()
        self._expanded_widget = QWidget()
        self._build_expanded_ui()

    def _create_compact_widget(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        self._mini_table = QTableView()
        self._mini_table.setToolTip("Last 5 packets received/transmitted")
        self._mini_model = PacketTableModel()
        self._mini_proxy = QSortFilterProxyModel()
        self._mini_proxy.setSourceModel(self._mini_model)
        self._mini_table.setModel(self._mini_proxy)
        self._mini_table.setMaximumHeight(80)
        header = self._mini_table.horizontalHeader()
        for i in range(3):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self._mini_table)
        self._counter_label = QLabel("Rx: 0 | Tx: 0")
        self._counter_label.setStyleSheet("font-size: 10px;")
        self._counter_label.setToolTip("Total packet counts")
        layout.addWidget(self._counter_label)
        return widget

    def _build_expanded_ui(self):
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
        self._channel_combo.addItems(["All", "EGTS", "SRTC", "FRMR", "VEH"])
        self._channel_combo.setToolTip("Filter by packet channel type")
        self._channel_combo.currentTextChanged.connect(self._on_channel_changed)
        toolbar.addWidget(self._channel_combo)
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setToolTip("Clear all packets from table")
        self._clear_btn.clicked.connect(self._on_clear)
        toolbar.addWidget(self._clear_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self._model = PacketTableModel()
        self._proxy = PacketFilterProxy()
        self._proxy.setSourceModel(self._model)

        # Find channel column index for filtering
        self._channel_column_index = -1
        for i, h in enumerate(PacketTableModel.HEADERS):
            if h.lower() == "channel":
                self._channel_column_index = i
                break

        self._table = QTableView()
        self._table.setToolTip("All captured packets (double-click for details)")
        self._table.setModel(self._proxy)
        header = self._table.horizontalHeader()
        for i in range(self._model.columnCount()):
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
        self._model.clear()
        self._stats_label.setText("Rx: 0 | Tx: 0")

    def _show_compact(self):
        if self._current_widget != self._compact_widget:
            self._clear_content()
            self.set_content_widget(self._compact_widget)
            self._current_widget = self._compact_widget

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
    def on_packet_processed(self, data: dict):
        packet = {
            "timestamp": data.get("timestamp", ""),
            "pid": data.get("pid", ""),
            "service": data.get("service", ""),
            "length": data.get("length", ""),
            "channel": data.get("channel", ""),
            "crc": data.get("crc", ""),
            "duplicate": data.get("duplicate", ""),
            "direction": "rx"
        }
        self._model.add_packet(packet)
        self._mini_model.add_packet(packet)
        self._update_stats()

    @Slot()
    def on_packet_sent(self, data: dict):
        packet = {
            "timestamp": data.get("timestamp", ""),
            "pid": data.get("pid", ""),
            "service": data.get("service", ""),
            "length": data.get("length", ""),
            "channel": data.get("channel", ""),
            "crc": data.get("crc", ""),
            "duplicate": data.get("duplicate", ""),
            "direction": "tx"
        }
        self._model.add_packet(packet)
        self._mini_model.add_packet(packet)
        self._update_stats()

    def _update_stats(self):
        rx = self._model.get_rx_count()
        tx = self._model.get_tx_count()
        text = f"Rx: {rx} | Tx: {tx}"
        self._stats_label.setText(text)
        self._counter_label.setText(text)

    def get_state(self) -> dict:
        return {
            "filter_text": self._filter_input.text(),
            "channel": self._channel_combo.currentText(),
        }

    def set_state(self, state: dict):
        self._filter_input.setText(state.get("filter_text", ""))
        channel = state.get("channel", "All")
        idx = self._channel_combo.findText(channel)
        if idx >= 0:
            self._channel_combo.setCurrentIndex(idx)