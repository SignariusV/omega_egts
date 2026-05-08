# OMEGA_EGTS GUI - Packet Detail Card
import re
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QTabWidget, QTextEdit, QTreeWidget, QTreeWidgetItem,
    QScrollArea, QToolButton, QFrame
)
from PySide6.QtCore import Signal, Slot, Qt
from PySide6.QtGui import QFont, QColor

from gui.dashboard.card_base import BaseCard, DisplayState
from gui.dashboard.layout_engine import GRID_COLS, GRID_ROWS


class PacketDetailCard(BaseCard):
    """Detailed packet view card with floating mode support."""

    closed = Signal(str)  # card_id

    def __init__(self, packet_data: dict, card_id: str, parent=None):
        title = f"Packet {packet_data.get('pid', '?')}"
        super().__init__(title, card_id=card_id, parent=parent)
        self._packet = packet_data
        self._floating = False
        
        # Add pin button to title bar for floating mode toggle
        self._pin_btn = QToolButton()
        self._pin_btn.setObjectName("pinButton")
        self._pin_btn.setText("📌")  # Pin emoji
        self._pin_btn.setFixedSize(20, 20)
        self._pin_btn.setCheckable(True)
        self._pin_btn.setChecked(False)
        self._pin_btn.setToolTip("Toggle floating mode")
        self._pin_btn.clicked.connect(self.toggle_floating)
        
        # Insert pin button before collapse button in title bar
        title_layout = self._title_bar.layout()
        title_layout.insertWidget(title_layout.count() - 1, self._pin_btn)
        
        self._build_widgets()
        self.finish_init()

    def _build_widgets(self):
        self._build_compact_ui()
        self._build_expanded_ui()
        self.set_views(self._compact_widget, self._expanded_widget)

    def _is_packet_ok(self) -> bool:
        """Check if packet has no errors."""
        return (
            self._packet.get("crc", "OK") == "OK"
            and self._packet.get("duplicate", "No") == "No"
            and bool(self._packet.get("parsed"))
        )

    def _build_compact_ui(self):
        self._compact_widget = QFrame()
        layout = QVBoxLayout(self._compact_widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # Status indicator
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

        # Brief info
        pid = self._packet.get("pid", "?")
        service = self._packet.get("service", "?")
        direction = self._packet.get("direction", "rx")
        dir_color = "#4EC9B0" if direction == "rx" else "#569CD6"

        info_text = f"PID: {pid} | SVC: {service}"
        self._info_label = QLabel(info_text)
        self._info_label.setStyleSheet(f"color: {dir_color}; font-size: 10px;")
        layout.addWidget(self._info_label)

        # Error summary if any
        errors = self._get_error_summary()
        if errors:
            error_label = QLabel(errors)
            error_label.setStyleSheet("color: #CE9178; font-size: 9px;")
            error_label.setWordWrap(True)
            layout.addWidget(error_label)

    def _get_error_summary(self) -> str:
        """Get brief error summary."""
        errors = []
        if self._packet.get("crc", "OK") != "OK":
            errors.append("CRC FAIL")
        if self._packet.get("duplicate", "No") == "Yes":
            errors.append("DUP")
        if not self._packet.get("parsed"):
            errors.append("NO PARSE")
        return " | ".join(errors) if errors else ""

    def _build_expanded_ui(self):
        self._expanded_widget = QWidget()
        layout = QVBoxLayout(self._expanded_widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Tab widget
        self._tabs = QTabWidget()
        self._tabs.setTabPosition(QTabWidget.TabPosition.North)

        # Tab 1: Raw Data
        self._tabs.addTab(self._build_raw_tab(), "Raw Data")

        # Tab 2: Transport Layer
        self._tabs.addTab(self._build_transport_tab(), "Transport")

        # Tab 3: Service Layer
        self._tabs.addTab(self._build_service_tab(), "Service")

        # Tab 4: Metadata
        self._tabs.addTab(self._build_metadata_tab(), "Metadata")

        layout.addWidget(self._tabs)

    def _build_raw_tab(self) -> QWidget:
        """Build raw hex dump tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)

        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setFont(QFont("Consolas", 10))
        text_edit.setStyleSheet(
            "background-color: #1E1E1E; color: #CCCCCC; border: 1px solid #3E3E42;"
        )

        hex_data = self._packet.get("hex", "")
        if hex_data:
            formatted = self._format_hex_dump(hex_data)
            text_edit.setPlainText(formatted)
        else:
            text_edit.setPlainText("(no data)")

        layout.addWidget(text_edit)
        return widget

    def _format_hex_dump(self, hex_str: str, bytes_per_line: int = 16) -> str:
        """Format hex string as dump with ASCII."""
        if not hex_str:
            return "(empty)"

        lines = []
        for i in range(0, len(hex_str), bytes_per_line * 2):
            chunk = hex_str[i:i + bytes_per_line * 2]

            # Offset
            offset = f"{i:04X}: "

            # Hex bytes
            hex_bytes = " ".join(
                chunk[j:j+2] for j in range(0, len(chunk), 2)
            ).ljust(bytes_per_line * 3)

            # ASCII
            ascii_repr = "".join(
                chr(int(chunk[j:j+2], 16)) if 32 <= int(chunk[j:j+2], 16) < 127
                else "." for j in range(0, len(chunk), 2)
            )

            lines.append(f"{offset}{hex_bytes} {ascii_repr}")

        return "\n".join(lines)

    def _build_transport_tab(self) -> QWidget:
        """Build transport layer tab."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        parsed = self._packet.get("parsed", {})

        # Transport layer fields
        fields = [
            ("Packet ID (PID)", str(parsed.get("packet_id", "?"))),
            ("Packet Type", str(parsed.get("packet_type", "?"))),
            ("Header Length (HL)", str(parsed.get("header_length", "?"))),
            ("Records Count", str(parsed.get("records_count", "?"))),
            ("Priority", str(parsed.get("priority", "?"))),
            ("Compression", str(parsed.get("compression", "?"))),
        ]

        for label, value in fields:
            label_widget = QLabel(label)
            label_widget.setStyleSheet("color: #9CDCFE;")
            value_widget = QLabel(value)
            value_widget.setStyleSheet("color: #CCCCCC;")
            layout.addRow(label_widget, value_widget)

        # CRC info
        crc_label = QLabel("CRC Valid")
        crc_label.setStyleSheet("color: #9CDCFE;")
        crc_value = QLabel(self._packet.get("crc", "?"))
        crc_color = "#4EC9B0" if self._packet.get("crc") == "OK" else "#F44747"
        crc_value.setStyleSheet(f"color: {crc_color};")
        layout.addRow(crc_label, crc_value)

        # Duplicate info
        dup_label = QLabel("Duplicate")
        dup_label.setStyleSheet("color: #9CDCFE;")
        dup_value = QLabel(self._packet.get("duplicate", "No"))
        dup_color = "#CE9178" if self._packet.get("duplicate") == "Yes" else "#CCCCCC"
        dup_value.setStyleSheet(f"color: {dup_color};")
        layout.addRow(dup_label, dup_value)

        scroll.setWidget(widget)
        return scroll

    def _build_service_tab(self) -> QWidget:
        """Build service layer tab with tree view."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)

        tree = QTreeWidget()
        tree.setHeaderLabels(["Field", "Value"])
        tree.setStyleSheet(
            "background-color: #1E1E1E; color: #CCCCCC; border: 1px solid #3E3E42;"
        )

        parsed = self._packet.get("parsed", {})

        if parsed:
            # Service type
            svc_item = QTreeWidgetItem(tree, ["Service", str(parsed.get("service", "?"))])

            # Records
            records = parsed.get("records", [])
            if records:
                rec_root = QTreeWidgetItem(tree, ["Records", f"({len(records)} items)"])

                for i, rec in enumerate(records):
                    rec_item = QTreeWidgetItem(rec_root, [f"Record {i+1}", ""])

                    # Record fields
                    for key, value in rec.items():
                        if key == "subrecords":
                            continue
                        QTreeWidgetItem(rec_item, [str(key), str(value)])

                    # Subrecords
                    subrecords = rec.get("subrecords", [])
                    if subrecords:
                        sub_root = QTreeWidgetItem(rec_item, ["Subrecords", f"({len(subrecords)})"])

                        for j, sub in enumerate(subrecords):
                            sub_item = QTreeWidgetItem(sub_root, [f"Subrec {j+1}", ""])
                            for sub_key, sub_value in sub.items():
                                if isinstance(sub_value, dict):
                                    sub_value = str(sub_value)
                                QTreeWidgetItem(sub_item, [str(sub_key), str(sub_value)])

            tree.expandAll()
        else:
            QTreeWidgetItem(tree, ["(no parsed data)", ""])

        layout.addWidget(tree)
        return widget

    def _build_metadata_tab(self) -> QWidget:
        """Build metadata tab."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # Metadata fields
        fields = [
            ("Timestamp", self._packet.get("timestamp", "?")),
            ("Channel", self._packet.get("channel", "?")),
            ("Direction", self._packet.get("direction", "?")),
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
        """Switch between floating dialog and grid card mode."""
        if self._floating:
            self._attach_to_grid()
        else:
            self._detach_to_floating()
        # Update pin button state and resize handles visibility
        self._pin_btn.setChecked(self._floating)
        # Show/hide resize handles based on mode
        for grip in self._grips:
            grip.setVisible(not self._floating)

    def _detach_to_floating(self):
        """Detach card to floating window mode."""
        self._floating = True
        self.setParent(None)
        # Use Qt.Window to allow resizing, remove FramelessWindowHint to enable resize handles
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        # Set minimum size for floating window
        self.setMinimumSize(400, 300)
        self.show()

    def _attach_to_grid(self):
        """Attach card back to grid."""
        self._floating = False
        self.setWindowFlags(Qt.WindowType.Widget)
        self.setParent(None)
        # Note: Caller must add card back to DashboardContainer

    def set_floating_position(self, x: int, y: int):
        """Set position for floating window."""
        self.move(x, y)

    def closeEvent(self, event):
        """Handle close event - emit signal."""
        self.closed.emit(self.card_id)
        super().closeEvent(event)

    def get_state(self) -> dict:
        """Return empty state (not persisted)."""
        return {}

    def set_state(self, state: dict):
        """No state to restore for floating cards."""
        pass
