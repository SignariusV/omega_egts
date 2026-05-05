# OMEGA_EGTS GUI
from typing import Any
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
    QComboBox, QPushButton, QLabel
)
from PySide6.QtCore import Slot
from gui.dashboard.card_base import BaseCard, DisplayState
from gui.widgets.log_viewer import LogViewer
from gui.utils.qt_log_handler import QLogHandler
from gui.bridge.event_bridge import EventBridge
import logging


FILTER_ALL = "All"
FILTER_PYTHON = "Python"
FILTER_PACKETS = "Packets"
FILTER_CONNECTIONS = "Connections"
FILTER_SCENARIOS = "Scenarios"
FILTER_COMMANDS = "Commands"

FILTER_OPTIONS = [
    FILTER_ALL,
    FILTER_PYTHON,
    FILTER_PACKETS,
    FILTER_CONNECTIONS,
    FILTER_SCENARIOS,
    FILTER_COMMANDS,
]

LEVEL_ALL = "All"
LEVEL_OPTIONS = [LEVEL_ALL, "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class SystemLogsCard(BaseCard):
    def __init__(self, card_id: str = "system_logs", event_bridge: EventBridge | None = None, parent=None):
        super().__init__("System Logs", card_id=card_id, parent=parent)
        self._event_bridge = event_bridge
        self._log_handler = QLogHandler()
        self._log_handler.log_message.connect(self._on_python_log)
        logging.getLogger().addHandler(self._log_handler)
        self._log_buffer: list[dict[str, Any]] = []
        self._max_buffer_size = 5000
        self._build_widgets()
        self._connect_event_bridge()
        self.finish_init()
        self.destroyed.connect(self._detach_handlers)

    def _connect_event_bridge(self):
        if self._event_bridge is None:
            return
        eb = self._event_bridge
        eb.packet_processed.connect(self._on_packet_processed)
        eb.packet_sent.connect(self._on_packet_sent)
        eb.connection_changed.connect(self._on_connection_changed)
        eb.scenario_step.connect(self._on_scenario_step)
        eb.command_sent.connect(self._on_command_sent)
        eb.command_error.connect(self._on_command_error)

    def _detach_handlers(self):
        logging.getLogger().removeHandler(self._log_handler)
        if self._event_bridge is None:
            return
        eb = self._event_bridge
        try:
            eb.packet_processed.disconnect(self._on_packet_processed)
            eb.packet_sent.disconnect(self._on_packet_sent)
            eb.connection_changed.disconnect(self._on_connection_changed)
            eb.scenario_step.disconnect(self._on_scenario_step)
            eb.command_sent.disconnect(self._on_command_sent)
            eb.command_error.disconnect(self._on_command_error)
        except Exception:
            pass

    def _build_widgets(self):
        self._build_compact_ui()
        self._build_expanded_ui()
        self.set_views(self._compact_widget, self._expanded_widget)

    def _build_compact_ui(self):
        self._compact_widget = QWidget()
        layout = QVBoxLayout(self._compact_widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        self._compact_edit = QPlainTextEdit()
        self._compact_edit.setObjectName("compactLogEdit")
        self._compact_edit.setReadOnly(True)
        self._compact_edit.setMaximumHeight(60)
        self._compact_edit.setToolTip("Last 3 log messages")
        layout.addWidget(self._compact_edit)

    def _build_expanded_ui(self):
        self._expanded_widget = QWidget()
        layout = QVBoxLayout(self._expanded_widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Source:"))
        self._source_combo = QComboBox()
        self._source_combo.addItems(FILTER_OPTIONS)
        self._source_combo.setCurrentText(FILTER_ALL)
        self._source_combo.setToolTip("Filter log messages by source")
        self._source_combo.currentTextChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self._source_combo)
        toolbar.addWidget(QLabel(" Level:"))
        self._level_combo = QComboBox()
        self._level_combo.addItems(LEVEL_OPTIONS)
        self._level_combo.setCurrentText(LEVEL_ALL)
        self._level_combo.setToolTip("Filter log messages by level")
        self._level_combo.currentTextChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self._level_combo)
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setToolTip("Clear all log messages")
        self._clear_btn.clicked.connect(self._on_clear)
        toolbar.addWidget(self._clear_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self._log_viewer = LogViewer()
        self._log_viewer.setToolTip("System log messages with color-coded levels")
        layout.addWidget(self._log_viewer)

    def _add_entry(self, source: str, level: str, message: str, timestamp: float | None = None):
        if not hasattr(self, '_source_combo'):
            return
        entry = {
            "source": source,
            "level": level,
            "message": message,
            "timestamp": timestamp,
        }
        self._log_buffer.append(entry)
        if len(self._log_buffer) > self._max_buffer_size:
            self._log_buffer = self._log_buffer[-self._max_buffer_size:]

        source_filter = self._source_combo.currentText()
        level_filter = self._level_combo.currentText()

        if source_filter != FILTER_ALL and source != source_filter:
            return
        if level_filter != LEVEL_ALL and level != level_filter:
            return
        self._log_viewer.append_log(level, message, timestamp, source)
        self._append_compact(level, message)

    @Slot(dict)
    def _on_python_log(self, data: dict):
        level = data.get("level", "INFO")
        message = data.get("message", "")
        timestamp = data.get("timestamp")
        self._add_entry(FILTER_PYTHON, level, message, timestamp)

    @Slot(dict)
    def _on_packet_processed(self, data: dict):
        ctx = data.get("ctx")
        if ctx is None:
            return
        hex_str = ctx.get("raw", b"").hex().upper() if ctx.get("raw") else ""
        service = ctx.get("parsed", {}).get("service", "?") if ctx.get("parsed") else "?"
        crc = "OK" if ctx.get("crc_valid") else "FAIL"
        message = f"PACKET RECV | hex={hex_str[:32]}... | service={service} | crc={crc}"
        self._add_entry(FILTER_PACKETS, "INFO", message, ctx.get("timestamp"))

    @Slot(dict)
    def _on_packet_sent(self, data: dict):
        hex_str = data.get("hex", "")[:32]
        channel = data.get("channel", "?")
        step = data.get("step_name", "?")
        message = f"PACKET SENT | {channel} | {step} | hex={hex_str}..."
        self._add_entry(FILTER_PACKETS, "INFO", message, data.get("timestamp"))

    @Slot(dict)
    def _on_connection_changed(self, data: dict):
        state = data.get("state", "?")
        prev = data.get("prev_state", "?")
        conn_id = data.get("connection_id", "?")
        message = f"CONNECTION | {conn_id} | {prev} → {state}"
        self._add_entry(FILTER_CONNECTIONS, "INFO", message, data.get("timestamp"))

    @Slot(dict)
    def _on_scenario_step(self, data: dict):
        step_name = data.get("step_name", "?")
        result = data.get("result", "?")
        scenario = data.get("scenario_name", "?")
        message = f"SCENARIO | {scenario} | {step_name} | {result}"
        level = "ERROR" if result == "error" else "INFO"
        self._add_entry(FILTER_SCENARIOS, level, message, data.get("timestamp"))

    @Slot(dict)
    def _on_command_sent(self, data: dict):
        channel = data.get("channel", "?")
        step = data.get("step_name", "?")
        message = f"COMMAND SENT | {channel} | {step}"
        self._add_entry(FILTER_COMMANDS, "INFO", message, data.get("timestamp"))

    @Slot(str)
    def _on_command_error(self, error: str):
        message = f"COMMAND ERROR | {error}"
        self._add_entry(FILTER_COMMANDS, "ERROR", message)

    def _append_compact(self, level: str, message: str):
        lines = self._compact_edit.toPlainText().split("\n")
        if len(lines) >= 3:
            lines = lines[1:]
        lines.append(f"[{level}] {message}")
        self._compact_edit.setPlainText("\n".join(lines))
        self._compact_edit.verticalScrollBar().setValue(
            self._compact_edit.verticalScrollBar().maximum()
        )

    @Slot(str)
    def _on_filter_changed(self, text: str):
        self._log_viewer.clear()
        self._compact_edit.clear()
        source_filter = self._source_combo.currentText()
        level_filter = self._level_combo.currentText()
        for entry in self._log_buffer:
            if source_filter != FILTER_ALL and entry["source"] != source_filter:
                continue
            if level_filter != LEVEL_ALL and entry["level"] != level_filter:
                continue
            self._log_viewer.append_log(entry["level"], entry["message"], entry["timestamp"], entry["source"])
            self._append_compact(entry["level"], entry["message"])

    def _on_clear(self):
        self._log_buffer.clear()
        self._log_viewer.clear()
        self._compact_edit.clear()

    def update_content_visibility(self, state: DisplayState):
        super().update_content_visibility(state)

    def get_state(self) -> dict:
        return {
            "source_filter": self._source_combo.currentText(),
            "level_filter": self._level_combo.currentText(),
        }

    def set_state(self, state: dict):
        source_text = state.get("source_filter", FILTER_ALL)
        idx = self._source_combo.findText(source_text)
        if idx >= 0:
            self._source_combo.setCurrentIndex(idx)
        level_text = state.get("level_filter", LEVEL_ALL)
        idx = self._level_combo.findText(level_text)
        if idx >= 0:
            self._level_combo.setCurrentIndex(idx)