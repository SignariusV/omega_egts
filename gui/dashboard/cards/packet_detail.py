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
from gui.utils.name_mappings import (
    format_service, format_packet_type, format_subrecord_type,
    format_priority, format_bool, format_direction, format_channel,
    format_crc_status, format_duplicate, format_value, get_field_label,
)


class PacketDetailCard(BaseCard):
    """Detailed packet view card with floating mode support."""

    closed = Signal(str)  # card_id

    def __init__(self, packet_data: dict, card_id: str, parent=None):
        svc = packet_data.get("parsed", {}).get("service", packet_data.get("service", "?"))
        try:
            svc_name = format_service(int(svc))
        except (ValueError, TypeError):
            svc_name = f"SVC: {svc}"
        title = f"Packet {packet_data.get('pid', '?')} — {svc_name}"
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

        self._build_widgets()
        self.finish_init()

    def _build_widgets(self):
        self._build_compact_ui()
        self._build_expanded_ui()
        self.set_views(self._compact_widget, self._expanded_widget)

    def _is_packet_ok(self) -> bool:
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

        parsed = self._packet.get("parsed", {})
        svc_raw = parsed.get("service", self._packet.get("service", "?"))
        try:
            svc_display = format_service(int(svc_raw))
        except (ValueError, TypeError):
            svc_display = f"SVC: {svc_raw}"

        dir_label = "RX" if direction == "rx" else "TX"
        info_text = f"PID: {pid} | {svc_display} | {dir_label}"
        self._info_label = QLabel(info_text)
        self._info_label.setStyleSheet(f"color: {dir_color}; font-size: 10px;")
        layout.addWidget(self._info_label)

        errors = self._get_error_summary()
        if errors:
            error_label = QLabel(errors)
            error_label.setStyleSheet("color: #CE9178; font-size: 9px;")
            error_label.setWordWrap(True)
            layout.addWidget(error_label)

    def _get_error_summary(self) -> str:
        errors = []
        if self._packet.get("crc", "OK") != "OK":
            errors.append("CRC Invalid")
        if self._packet.get("duplicate", "No") == "Yes":
            errors.append("Duplicate")
        if not self._packet.get("parsed"):
            errors.append("No Parse")
        return " | ".join(errors) if errors else ""

    def _build_expanded_ui(self):
        self._expanded_widget = QWidget()
        layout = QVBoxLayout(self._expanded_widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self._tabs = QTabWidget()
        self._tabs.setTabPosition(QTabWidget.TabPosition.North)

        self._tabs.addTab(self._build_raw_tab(), "Raw Data")
        self._tabs.addTab(self._build_transport_tab(), "Transport")
        self._tabs.addTab(self._build_service_tab(), "Service")
        self._tabs.addTab(self._build_metadata_tab(), "Metadata")

        layout.addWidget(self._tabs)

    def _build_raw_tab(self) -> QWidget:
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
        if not hex_str:
            return "(empty)"

        if isinstance(hex_str, bytes):
            hex_str = hex_str.hex()

        lines = []
        for i in range(0, len(hex_str), bytes_per_line * 2):
            chunk = hex_str[i:i + bytes_per_line * 2]
            offset = f"{i:04X}: "
            hex_bytes = " ".join(
                chunk[j:j+2] for j in range(0, len(chunk), 2)
            ).ljust(bytes_per_line * 3)
            ascii_repr = "".join(
                chr(int(chunk[j:j+2], 16)) if 32 <= int(chunk[j:j+2], 16) < 127
                else "." for j in range(0, len(chunk), 2)
            )
            lines.append(f"{offset}{hex_bytes} {ascii_repr}")

        return "\n".join(lines)

    def _build_transport_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        parsed = self._packet.get("parsed", {})

        pid_val = parsed.get("packet_id", "?")
        pt_val = parsed.get("packet_type", "?")
        try:
            pt_display = format_packet_type(int(pt_val))
        except (ValueError, TypeError):
            pt_display = pt_val
        hl_val = parsed.get("header_length", "?")
        rc_val = parsed.get("records_count", "?")
        pr_val = parsed.get("priority", "?")
        try:
            pr_display = format_priority(int(pr_val))
        except (ValueError, TypeError):
            pr_display = pr_val
        cmp_val = parsed.get("compression", "?")
        cmp_display = format_bool(cmp_val)

        fields = [
            ("Packet ID (PID)", str(pid_val)),
            ("Packet Type (PT)", pt_display),
            ("Header Length (HL)", str(hl_val)),
            ("Records Count", str(rc_val)),
            ("Priority (PR)", pr_display),
            ("Compressed (CMP)", cmp_display),
        ]

        for label, value in fields:
            label_widget = QLabel(label)
            label_widget.setStyleSheet("color: #9CDCFE;")
            value_widget = QLabel(value)
            value_widget.setStyleSheet("color: #CCCCCC;")
            layout.addRow(label_widget, value_widget)

        crc_label = QLabel("CRC Status")
        crc_label.setStyleSheet("color: #9CDCFE;")
        crc_raw = self._packet.get("crc", "?")
        crc_display = format_crc_status(crc_raw)
        crc_value = QLabel(crc_display)
        crc_color = "#4EC9B0" if crc_raw == "OK" else "#F44747"
        crc_value.setStyleSheet(f"color: {crc_color};")
        layout.addRow(crc_label, crc_value)

        dup_label = QLabel("Duplicate Status")
        dup_label.setStyleSheet("color: #9CDCFE;")
        dup_raw = self._packet.get("duplicate", "No")
        dup_display = format_duplicate(dup_raw)
        dup_value = QLabel(dup_display)
        dup_color = "#CE9178" if dup_raw == "Yes" else "#CCCCCC"
        dup_value.setStyleSheet(f"color: {dup_color};")
        layout.addRow(dup_label, dup_value)

        scroll.setWidget(widget)
        return scroll

    def _build_service_tab(self) -> QWidget:
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
            svc_raw = parsed.get("service", "?")
            try:
                svc_display = format_service(int(svc_raw))
            except (ValueError, TypeError):
                svc_display = svc_raw
            QTreeWidgetItem(tree, [get_field_label("service"), svc_display])

            packet_type = parsed.get("packet_type")
            if packet_type is not None:
                try:
                    pt_display = format_packet_type(int(packet_type))
                except (ValueError, TypeError):
                    pt_display = str(packet_type)
                QTreeWidgetItem(tree, [get_field_label("packet_type"), pt_display])

            records = parsed.get("records", [])
            if records:
                rec_root = QTreeWidgetItem(tree, ["Records", f"({len(records)} items)"])

                for i, rec in enumerate(records):
                    rec_item = QTreeWidgetItem(rec_root, [f"Record {i+1}", ""])

                    for key, value in rec.items():
                        if key == "subrecords":
                            continue
                        label = get_field_label(key)
                        formatted = format_value(key, value)
                        QTreeWidgetItem(rec_item, [label, formatted])

                    subrecords = rec.get("subrecords", [])
                    if subrecords:
                        sub_root = QTreeWidgetItem(rec_item, ["Subrecords", f"({len(subrecords)})"])

                        for j, sub in enumerate(subrecords):
                            sub_item = QTreeWidgetItem(sub_root, [f"Subrecord {j+1}", ""])
                            for sub_key, sub_value in sub.items():
                                label = get_field_label(sub_key)
                                formatted = format_value(sub_key, sub_value)
                                QTreeWidgetItem(sub_item, [label, formatted])

            tree.expandAll()
        else:
            QTreeWidgetItem(tree, ["(no parsed data)", ""])

        layout.addWidget(tree)
        return widget

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
        if self._floating:
            self._attach_to_grid()
        else:
            self._detach_to_floating()
        self._pin_btn.setChecked(self._floating)
        for grip in self._grips:
            grip.setVisible(not self._floating)

    def _detach_to_floating(self):
        self._floating = True
        self.setParent(None)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setMinimumSize(400, 300)
        self.show()

    def _attach_to_grid(self):
        self._floating = False
        self.setWindowFlags(Qt.WindowType.Widget)
        self.setParent(None)

    def set_floating_position(self, x: int, y: int):
        self.move(x, y)

    def closeEvent(self, event):
        self.closed.emit(self.card_id)
        super().closeEvent(event)

    def get_state(self) -> dict:
        return {}

    def set_state(self, state: dict):
        pass
