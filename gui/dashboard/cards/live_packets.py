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
from gui.dashboard.cards.packet_detail import PacketDetailCard
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
    MAX_DETAIL_CARDS = 6

    def __init__(self, card_id: str = "live_packets", parent=None):
        super().__init__("Live Packets", card_id=card_id, parent=parent)
        self.icon_path = str(PROJECT_ROOT / "gui" / "resources" / "icons" / "packets.svg")
        self._open_detail_cards: dict[str, PacketDetailCard] = {}
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
        """Handle double-click on packet table - open detail card."""
        proxy = self._table.model()
        source_index = proxy.mapToSource(index)
        if not source_index.isValid():
            return

        row = source_index.row()
        packet = self._packet_model.get_packet(row)
        if not packet:
            return

        # Generate unique ID for this packet using robust method
        import hashlib
        sig_parts = [
            str(packet.get('timestamp', '0')),
            str(packet.get('pid', '0')),
            str(packet.get('direction', 'unknown')),
            str(packet.get('hex', '')[:30])
        ]
        content = "_".join(sig_parts)
        packet_id = "pkt_" + hashlib.md5(content.encode()).hexdigest()[:16]

        # If already open - raise it and return
        if packet_id in self._open_detail_cards:
            try:
                card = self._open_detail_cards[packet_id]
                if card and not card.isHidden():
                    card.raise_()
                    return
            except:
                if packet_id in self._open_detail_cards:
                    del self._open_detail_cards[packet_id]

        # If already open - raise it
        if packet_id in self._open_detail_cards:
            self._open_detail_cards[packet_id].raise_()
            return

        # Check limit
        if len(self._open_detail_cards) >= self.MAX_DETAIL_CARDS:
            # Close oldest
            oldest_id = next(iter(self._open_detail_cards))
            self._close_detail_card(oldest_id)

        # Create new card
        card = PacketDetailCard(packet, card_id=packet_id)
        card.closed.connect(lambda cid=packet_id: self._on_detail_card_closed(cid))

        # Store reference
        self._open_detail_cards[packet_id] = card

        # Show as floating window
        self._position_floating_card(card)
        card.show()
        card.toggle_floating()  # Switch to floating mode

    def _position_floating_card(self, card: PacketDetailCard):
        """Position floating card with cascade offset."""
        main_window = self.window()
        if not main_window:
            return

        main_geo = main_window.geometry()
        base_x = main_geo.x() + main_geo.width() // 4
        base_y = main_geo.y() + main_geo.height() // 4

        # Cascade: 30px offset per existing card
        offset = len(self._open_detail_cards) * 30
        x = base_x + offset
        y = base_y + offset

        # Bounds check - don't go beyond main window
        if x + 500 > main_geo.right():
            x = base_x
            y = base_y  # Reset cascade

        card.set_floating_position(x, y)

    def _on_detail_card_closed(self, card_id: str):
        """Remove closed detail card from tracking dict."""
        if card_id in self._open_detail_cards:
            del self._open_detail_cards[card_id]

    def _close_all_detail_cards(self):
        """Close all detail cards."""
        # Get all cards before clearing dict
        cards_to_close = list(self._open_detail_cards.values())
        # Clear tracking dict to prevent double-delete from signals
        self._open_detail_cards.clear()
        # Close all cards (disconnect signals first)
        for card in cards_to_close:
            try:
                card.closed.disconnect()
            except:
                pass
            card.close()

    def _close_detail_card(self, card_id: str):
        """Close a specific detail card."""
        if card_id in self._open_detail_cards:
            card = self._open_detail_cards.pop(card_id)
            try:
                card.closed.disconnect()
            except:
                pass
            card.close()

    def hideEvent(self, event):
        """Close all detail cards when LivePacketsCard is hidden."""
        self._close_all_detail_cards()
        super().hideEvent(event)

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
        
        # Handle None values for pid
        pid = data.get("pid")
        if pid is None:
            pid = ""
        
        packet = {
            "timestamp": data.get("timestamp", ""),
            "pid": str(pid),
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
        """Handle outgoing packet - try to parse if hex data exists."""
        # Try both possible keys for hex data
        hex_data = data.get("packet_bytes") or data.get("hex", "")
        
        # Try to parse outgoing packet if hex data exists
        parsed = {}
        if hex_data:
            try:
                from core.egts.protocol import get_protocol
                protocol = get_protocol("2015")  # Default GOST version
                result = protocol.parse(bytes.fromhex(hex_data))
                if result:
                    parsed = {
                        "packet_id": result.packet_id,
                        "packet_type": result.packet_type,
                        "service": result.service,
                        "records_count": len(result.records) if result.records else 0,
                    }
            except:
                pass  # Ignore parse errors for outgoing packets
        
        # Generate packet_id - handle None values
        pid = data.get("pid")
        if pid is None:
            pid = ""
        
        packet = {
            "timestamp": data.get("timestamp", ""),
            "pid": str(pid),
            "service": str(parsed.get("service", "?")),
            "length": len(hex_data) // 2 if hex_data else 0,
            "channel": data.get("channel", ""),
            "crc": "OK",
            "duplicate": "No",
            "hex": hex_data,
            "parsed": parsed,
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
