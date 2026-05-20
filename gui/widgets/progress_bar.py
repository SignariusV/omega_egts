# OMEGA_EGTS GUI
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Qt, Signal, Property


STATUS_COLORS = {
    "PASS": "#4EC9B0",
    "FAIL": "#F44747",
    "TIMEOUT": "#DCDCAA",
    "ERROR": "#F44747",
    "RUNNING": "#569CD6",
    "PENDING": "#3E3E42",
    "CANCELLED": "#808080",
}


class ProgressBarWidget(QWidget):
    value_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0
        self._segments = 10
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self._segment_labels = []
        for i in range(self._segments):
            seg = QLabel()
            seg.setFixedSize(20, 8)
            seg.setStyleSheet(f"background-color: {STATUS_COLORS['PENDING']}; border-radius: 2px;")
            layout.addWidget(seg)
            self._segment_labels.append(seg)
        self._percent_label = QLabel("0%")
        self._percent_label.setMinimumWidth(40)
        layout.addWidget(self._percent_label)

    def set_segments(self, count: int):
        """Установить число сегментов = число шагов сценария."""
        if count == self._segments:
            return
        # Удаляем старые
        for seg in self._segment_labels:
            seg.deleteLater()
        self._segment_labels.clear()
        # Создаём новые
        for i in range(count):
            seg = QLabel()
            seg.setFixedSize(20, 8)
            seg.setStyleSheet(f"background-color: {STATUS_COLORS['PENDING']}; border-radius: 2px;")
            self.layout().insertWidget(self.layout().count() - 1, seg)
            self._segment_labels.append(seg)
        self._segments = count
        self._update_segments()

    def set_step_status(self, index: int, status: str):
        """Подсветить конкретный сегмент по статусу."""
        if 0 <= index < len(self._segment_labels):
            color = STATUS_COLORS.get(status, STATUS_COLORS["PENDING"])
            self._segment_labels[index].setStyleSheet(
                f"background-color: {color}; border-radius: 2px;"
            )

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
                seg.setStyleSheet(f"background-color: {STATUS_COLORS['PASS']}; border-radius: 2px;")
            else:
                seg.setStyleSheet(f"background-color: {STATUS_COLORS['PENDING']}; border-radius: 2px;")
        self._percent_label.setText(f"{self._value}%")

    def reset(self):
        """Сбросить прогресс и все сегменты в PENDING."""
        self._value = 0
        for seg in self._segment_labels:
            seg.setStyleSheet(f"background-color: {STATUS_COLORS['PENDING']}; border-radius: 2px;")
        self._percent_label.setText("0%")

    value = Property(int, get_value, set_value)
