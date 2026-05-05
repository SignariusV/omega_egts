# OMEGA_EGTS GUI
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
    QComboBox, QPushButton, QLabel
)
from PySide6.QtCore import Slot
from gui.dashboard.card_base import BaseCard, DisplayState
from gui.widgets.log_viewer import LogViewer
from gui.utils.qt_log_handler import QLogHandler
import logging


class SystemLogsCard(BaseCard):
    def __init__(self, card_id: str = "system_logs", parent=None):
        super().__init__("System Logs", card_id=card_id, parent=parent)
        self._log_handler = QLogHandler()
        self._log_handler.log_message.connect(self._on_log_message)
        logging.getLogger().addHandler(self._log_handler)
        self._log_buffer = []
        self._max_buffer_size = 1000
        self._build_widgets()
        self.finish_init()
        self.destroyed.connect(self._detach_handler)

    def _detach_handler(self):
        """Remove log handler when card is destroyed."""
        logging.getLogger().removeHandler(self._log_handler)

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
        toolbar.addWidget(QLabel("Level:"))
        self._level_combo = QComboBox()
        self._level_combo.addItems(["All", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self._level_combo.setCurrentText("All")
        self._level_combo.setToolTip("Filter log messages by level")
        self._level_combo.currentTextChanged.connect(self._on_level_changed)
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

    def _on_log_message(self, data: dict):
        if not hasattr(self, '_level_combo'):
            return
        level = data.get("level", "INFO")
        message = data.get("message", "")
        timestamp = data.get("timestamp")
        selected = self._level_combo.currentText()
        
        entry = {"level": level, "message": message, "timestamp": timestamp}
        self._log_buffer.append(entry)
        if len(self._log_buffer) > self._max_buffer_size:
            self._log_buffer = self._log_buffer[-self._max_buffer_size:]
        
        if selected != "All" and level != selected:
            return
        self._log_viewer.append_log(level, message, timestamp)
        self._append_compact(level, message)

    def _append_compact(self, level: str, message: str):
        lines = self._compact_edit.toPlainText().split("\n")
        if len(lines) >= 3:
            lines = lines[1:]
        lines.append(f"[{level}] {message}")
        self._compact_edit.setPlainText("\n".join(lines))
        self._compact_edit.verticalScrollBar().setValue(
            self._compact_edit.verticalScrollBar().maximum()
        )

    def _on_level_changed(self, text):
        self._log_viewer.clear()
        self._compact_edit.clear()
        for entry in self._log_buffer:
            if text == "All" or entry["level"] == text:
                self._log_viewer.append_log(entry["level"], entry["message"], entry["timestamp"])
                self._append_compact(entry["level"], entry["message"])

    def _on_clear(self):
        self._log_buffer.clear()
        self._log_viewer.clear()
        self._compact_edit.clear()

    def update_content_visibility(self, state: DisplayState):
        super().update_content_visibility(state)

    def get_state(self) -> dict:
        return {
            "level": self._level_combo.currentText(),
        }

    def set_state(self, state: dict):
        level = state.get("level", "All")
        idx = self._level_combo.findText(level)
        if idx >= 0:
            self._level_combo.setCurrentIndex(idx)