# OMEGA_EGTS GUI
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Qt, Signal, Property, QSize


class ProgressBarWidget(QWidget):
    value_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0
        self._segments = 10
        self._completed_color = "#4EC9B0"
        self._pending_color = "#3E3E42"
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self._segment_labels = []
        for i in range(self._segments):
            seg = QLabel()
            seg.setFixedSize(20, 8)
            seg.setStyleSheet(f"background-color: {self._pending_color}; border-radius: 2px;")
            layout.addWidget(seg)
            self._segment_labels.append(seg)
        self._percent_label = QLabel("0%")
        self._percent_label.setMinimumWidth(40)
        layout.addWidget(self._percent_label)

    def get_value(self) -> int:
        return self._value

    def set_value(self, value: int):
        self._value = max(0, min(100, value))
        self._update_segments()
        self.value_changed.emit(self._value)

    def _update_segments(self):
        filled = (self._value * self._segments) // 100
        for i, seg in enumerate(self._segment_labels):
            if i < filled:
                seg.setStyleSheet(f"background-color: {self._completed_color}; border-radius: 2px;")
            else:
                seg.setStyleSheet(f"background-color: {self._pending_color}; border-radius: 2px;")
        self._percent_label.setText(f"{self._value}%")

    value = Property(int, get_value, set_value)