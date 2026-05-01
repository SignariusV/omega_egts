# OMEGA_EGTS GUI
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPlainTextEdit
from PySide6.QtCore import Qt
from datetime import datetime


LEVEL_COLORS = {
    "DEBUG": "#808080",
    "INFO": "#CCCCCC",
    "WARNING": "#CE9178",
    "ERROR": "#F44747",
    "CRITICAL": "#F44747",
}


class LogViewer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._text_edit = QPlainTextEdit()
        self._text_edit.setReadOnly(True)
        self._text_edit.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1E1E1E;
                color: #CCCCCC;
                font-family: Consolas, monospace;
                font-size: 11px;
            }
        """)
        layout.addWidget(self._text_edit)

    def append_log(self, level: str, message: str, timestamp: float = None):
        ts = datetime.fromtimestamp(timestamp).strftime("%H:%M:%S.%f")[:-3] if timestamp else ""
        color = LEVEL_COLORS.get(level, "#CCCCCC")
        formatted = f"[{ts}] {level}: {message}"
        self._text_edit.appendHtml(f'<span style="color: {color};">{formatted}</span>')

    def clear(self):
        self._text_edit.clear()

    def get_content(self) -> str:
        return self._text_edit.toPlainText()