# OMEGA_EGTS GUI
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView,
    QHeaderView, QLabel, QLineEdit, QComboBox, QPushButton
)
from PySide6.QtCore import Signal, Slot, Qt, QSortFilterProxyModel
from gui.dashboard.card_base import BaseCard, DisplayState
from gui.widgets.packet_table import PacketTableModel


class LivePacketsCard(BaseCard):
    def __init__(self, parent=None):
        super().__init__("Live Packets", parent)
        self._current_widget = None
        self._build_widgets()
        self._show_expanded()

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
        self._filter_input.textChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self._filter_input)
        toolbar.addWidget(QLabel("Channel:"))
        self._channel_combo = QComboBox()
        self._channel_combo.addItems(["All", "EGTS", "SRTC", "FRMR", "VEH"])
        self._channel_combo.currentTextChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self._channel_combo)
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.clicked.connect(self._on_clear)
        toolbar.addWidget(self._clear_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self._model = PacketTableModel()
        self._proxy = QSortFilterProxyModel()
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterKeyColumn(-1)

        self._table = QTableView()
        self._table.setModel(self._proxy)
        header = self._table.horizontalHeader()
        for i in range(self._model.columnCount()):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        layout.addWidget(self._table)

        self._stats_label = QLabel("Rx: 0 | Tx: 0")
        layout.addWidget(self._stats_label)

    def _on_filter_changed(self, text):
        self._proxy.setFilterRegularExpression(text)
        channel = self._channel_combo.currentText()
        if channel == "All":
            self._proxy.setFilterKeyColumn(-1)
        else:
            for i, h in enumerate(PacketTableModel.HEADERS):
                if h.lower() == "channel":
                    self._proxy.setFilterKeyColumn(i)
                    self._proxy.setFilterFixedString(channel)
                    break

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