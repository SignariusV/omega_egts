# OMEGA_EGTS GUI
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
    QComboBox, QPushButton, QLabel
)
from PySide6.QtCore import Signal, Slot
from gui.dashboard.card_base import BaseCard, DisplayState
from gui.widgets.log_viewer import LogViewer
from gui.utils.qt_log_handler import QLogHandler
import logging


class SystemLogsCard(BaseCard):
    def __init__(self, parent=None):
        super().__init__("System Logs", parent)
        self._log_handler = QLogHandler()
        self._log_handler.log_message.connect(self._on_log_message)
        logging.getLogger().addHandler(self._log_handler)
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
        self._compact_edit = QPlainTextEdit()
        self._compact_edit.setReadOnly(True)
        self._compact_edit.setMaximumHeight(60)
        self._compact_edit.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1E1E1E;
                color: #CCCCCC;
                font-family: Consolas, monospace;
                font-size: 10px;
            }
        """)
        layout.addWidget(self._compact_edit)
        return widget

    def _build_expanded_ui(self):
        layout = QVBoxLayout(self._expanded_widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Level:"))
        self._level_combo = QComboBox()
        self._level_combo.addItems(["All", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self._level_combo.setCurrentText("All")
        self._level_combo.currentTextChanged.connect(self._on_level_changed)
        toolbar.addWidget(self._level_combo)
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.clicked.connect(self._on_clear)
        toolbar.addWidget(self._clear_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self._log_viewer = LogViewer()
        layout.addWidget(self._log_viewer)

    def _on_log_message(self, data: dict):
        level = data.get("level", "INFO")
        message = data.get("message", "")
        timestamp = data.get("timestamp")
        selected = self._level_combo.currentText()
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

    def _on_level_changed(self, text: str):
        pass

    def _on_clear(self):
        self._log_viewer.clear()
        self._compact_edit.clear()

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

    def get_state(self) -> dict:
        return {
            "level": self._level_combo.currentText(),
        }

    def set_state(self, state: dict):
        level = state.get("level", "All")
        idx = self._level_combo.findText(level)
        if idx >= 0:
            self._level_combo.setCurrentIndex(idx)