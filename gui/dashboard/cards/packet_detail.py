# OMEGA_EGTS GUI - Packet Detail Card
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout,
    QLabel, QTabWidget, QTreeWidget, QTreeWidgetItem,
    QScrollArea, QToolButton, QFrame, QSplitter, QHeaderView,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor

from gui.dashboard.card_base import BaseCard
from gui.utils.name_mappings import (
    format_service, format_direction, format_channel,
)
from gui.utils.byte_layout import compute_layout, ByteField
from gui.utils.hex_viewer import HexDumpWidget


class PacketDetailCard(BaseCard):
    """Detailed packet view card with floating mode support."""

    closed = Signal(str)  # card_id

    def __init__(self, packet_data: dict, card_id: str, parent=None):
        svc = packet_data.get("parsed", {}).get("service", packet_data.get("service", "?"))
        try:
            self._svc_display = format_service(int(svc))
        except (ValueError, TypeError):
            self._svc_display = f"SVC: {svc}"
        title = f"Packet {packet_data.get('pid', '?')} — {self._svc_display}"
        super().__init__(title, card_id=card_id, parent=parent)
        self._packet = packet_data
        self._floating = False

        self._pin_btn = QToolButton()
        self._pin_btn.setObjectName("pinButton")
        self._pin_btn.setText("📌")
        self._pin_btn.setFixedSize(20, 20)
        self._pin_btn.setCheckable(True)
        self._pin_btn.setChecked(False)
        self._pin_btn.setToolTip("Toggle floating mode")
        self._pin_btn.clicked.connect(self.toggle_floating)

        title_layout = self._title_bar.layout()
        title_layout.insertWidget(title_layout.count() - 1, self._pin_btn)

        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setMinimumSize(400, 300)
        self._hex_viewer = None
        self._build_widgets()
        self.finish_init()

    def _build_widgets(self):
        self._build_compact_ui()
        self._build_expanded_ui()
        self.set_views(self._compact_widget, self._expanded_widget)

    def _error_summary(self) -> str:
        errors = []
        if self._packet.get("crc", "OK") != "OK":
            errors.append("CRC Invalid")
        if self._packet.get("duplicate", "No") == "Yes":
            errors.append("Duplicate")
        if not self._packet.get("parsed"):
            errors.append("No Parse")
        return " | ".join(errors) if errors else ""

    def _is_packet_ok(self) -> bool:
        return not self._error_summary()

    def _build_compact_ui(self):
        self._compact_widget = QFrame()
        layout = QVBoxLayout(self._compact_widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        is_ok = self._is_packet_ok()
        status_text = "OK" if is_ok else "ERROR"
        bg_color = "#1E3A2E" if is_ok else "#3A1E1E"
        text_color = "#4EC9B0" if is_ok else "#F44747"

        self._status_label = QLabel(status_text)
        self._status_label.setStyleSheet(
            f"color: {text_color}; background-color: {bg_color};"
            f"padding: 4px; border-radius: 4px; font-weight: bold;"
        )
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status_label)

        pid = self._packet.get("pid", "?")
        direction = self._packet.get("direction", "rx")
        dir_color = "#4EC9B0" if direction == "rx" else "#569CD6"

        dir_label = "RX" if direction == "rx" else "TX"
        info_text = f"PID: {pid} | {self._svc_display} | {dir_label}"
        self._info_label = QLabel(info_text)
        self._info_label.setStyleSheet(f"color: {dir_color}; font-size: 10px;")
        layout.addWidget(self._info_label)

        errors = self._error_summary()
        if errors:
            error_label = QLabel(errors)
            error_label.setStyleSheet("color: #CE9178; font-size: 9px;")
            error_label.setWordWrap(True)
            layout.addWidget(error_label)

    def _build_expanded_ui(self):
        self._expanded_widget = QWidget()
        layout = QVBoxLayout(self._expanded_widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self._tabs = QTabWidget()
        self._tabs.setTabPosition(QTabWidget.TabPosition.North)
        self._tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #3E3E42; background: #1E1E1E; }
            QTabBar::tab { color: #CCCCCC; background: #2D2D30; border: 1px solid #3E3E42;
                           padding: 6px 16px; margin: 1px; }
            QTabBar::tab:selected { color: #FFFFFF; background: #1E1E1E; border-bottom: 1px solid #1E1E1E; }
            QTabBar::tab:hover { color: #FFFFFF; background: #3E3E42; }
        """)

        self._tabs.addTab(self._build_protocol_tab(), "Protocol")
        self._tabs.addTab(self._build_metadata_tab(), "Metadata")

        layout.addWidget(self._tabs)

    def _build_protocol_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)

        splitter = QSplitter(Qt.Horizontal)

        tree = QTreeWidget()
        tree.setHeaderLabels(["Offset", "Field → Value", "Hex"])
        tree.setColumnWidth(0, 120)
        tree.setColumnWidth(2, 140)
        tree.setIndentation(16)
        tree.setAlternatingRowColors(False)
        tree.setStyleSheet(
            "QTreeWidget { background-color: #1E1E1E; color: #CCCCCC;"
            " border: 1px solid #3E3E42; font-family: Consolas; font-size: 14px; }"
            "QTreeWidget::item { padding: 2px; }"
            "QHeaderView::section { background-color: #2D2D30; color: #CCCCCC;"
            " border: 1px solid #3E3E42; padding: 2px; font-weight: bold; font-size: 14px; }"
            "QTreeWidget::item:selected { background-color: #264F78; }"
        )

        header = tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)

        hex_str = self._packet.get("hex", "")
        parsed = self._packet.get("parsed", {})
        fields = compute_layout(hex_str, parsed)

        for bf in fields:
            self._add_field_item(tree, None, bf)

        tree.itemClicked.connect(self._on_tree_item_clicked)

        self._hex_viewer = HexDumpWidget()
        self._hex_viewer.set_hex_data(hex_str)

        splitter.addWidget(tree)
        splitter.addWidget(self._hex_viewer)
        splitter.setSizes([550, 300])

        layout.addWidget(splitter)
        return widget

    def _add_field_item(self, tree: QTreeWidget, parent: QTreeWidgetItem | None,
                        bf: ByteField):
        """Recursively add a ByteField to the tree."""
        offset_str = self._format_offset(bf.offset_start, bf.offset_end)
        field_str = self._format_field(bf)
        hex_str = bf.hex_display

        parts = [offset_str, field_str, hex_str]
        if parent:
            item = QTreeWidgetItem(parent, parts)
        else:
            item = QTreeWidgetItem(tree, parts)

        item.setForeground(0, QColor("#9CDCFE"))
        item.setForeground(2, QColor("#DCDCAA"))

        if bf.error:
            for c in range(3):
                item.setForeground(c, QColor("#F44747"))
        elif bf.field_type == "section":
            font = QFont("Segoe UI", pointSize=12)
            font.setBold(True)
            for c in range(3):
                item.setFont(c, font)
                item.setForeground(c, QColor("#4EC9B0"))

        if bf.field_type == "bitfield":
            item.setForeground(1, QColor("#CE9178"))

        item.setData(0, Qt.ItemDataRole.UserRole,
                     (bf.offset_start, bf.offset_end))

        for child in bf.children:
            self._add_field_item(tree, item, child)

    def _format_offset(self, start: int, end: int) -> str:
        if start == end:
            return str(start)
        return f"{start}-{end}"

    def _format_field(self, bf: ByteField) -> str:
        if bf.field_type == "section":
            return f"{bf.full_name} {bf.value_display}"
        if bf.abbr:
            parts = [bf.abbr]
            if bf.full_name:
                parts.append(f"({bf.full_name})")
            if bf.description:
                parts.append(f"— {bf.description}")
            if bf.value_display:
                parts.append(f"→  {bf.value_display}")
            return " ".join(parts)
        return bf.value_display

    def _on_tree_item_clicked(self, item: QTreeWidgetItem, column: int):
        """Handle tree item click — highlight bytes in hex viewer."""
        byte_range = item.data(0, Qt.ItemDataRole.UserRole)
        if byte_range and self._hex_viewer:
            start, end = byte_range
            self._hex_viewer.clear_highlight()
            self._hex_viewer.highlight(start, end)

    def _build_metadata_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        direction_raw = self._packet.get("direction", "?")
        direction_display = format_direction(direction_raw)
        channel_raw = self._packet.get("channel", "?")
        channel_display = format_channel(channel_raw)

        fields = [
            ("Timestamp", self._packet.get("timestamp", "?")),
            ("Channel", channel_display),
            ("Direction", direction_display),
            ("Length", f"{self._packet.get('length', 0)} bytes"),
        ]

        for label, value in fields:
            label_widget = QLabel(label)
            label_widget.setStyleSheet("color: #9CDCFE;")
            value_widget = QLabel(str(value))
            value_widget.setStyleSheet("color: #CCCCCC;")
            layout.addRow(label_widget, value_widget)

        scroll.setWidget(widget)
        return scroll

    def toggle_floating(self):
        flags = Qt.WindowType.Window
        if not self._floating:
            self._floating = True
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            self._floating = False
        self.setWindowFlags(flags)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.show()
        self._pin_btn.setChecked(self._floating)

    def set_floating_position(self, x: int, y: int):
        self.move(x, y)

    def closeEvent(self, event):
        self.closed.emit(self.card_id)
        event.accept()

    def get_state(self) -> dict:
        return {}

    def set_state(self, state: dict):
        pass
