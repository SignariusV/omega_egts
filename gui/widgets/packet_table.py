from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QTableWidget, QTableWidgetItem, QLabel, QPushButton,
    QComboBox, QLineEdit, QCheckBox, QHeaderView
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QFont, QColor


class PacketTable(QTableWidget):
    """Таблица пакетов (RX/TX) с обновлением в реальном времени."""

    packet_selected = Signal(dict)  # Сигнал при двойном клике

    def __init__(self):
        super().__init__()
        self.setColumnCount(6)
        self.setHorizontalHeaderLabels(["Время", "Напр.", "PID", "RN", "Размер", "Service"])
        self.setAlternatingRowColors(True)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.cellDoubleClicked.connect(self._on_double_click)

        # Фильтры
        self.filter_direction = "Все"
        self.filter_text = ""

    def add_packet(self, packet_info: dict):
        """Добавление нового пакета в таблицу."""
        row = self.rowCount()
        self.insertRow(row)

        # Время
        time_item = QTableWidgetItem(packet_info.get("time", ""))
        self.setItem(row, 0, time_item)

        # Направление
        direction = packet_info.get("direction", "")
        dir_text = "▶RX" if direction == "RX" else "◀TX"
        dir_item = QTableWidgetItem(dir_text)
        dir_item.setTextAlignment(Qt.AlignCenter)
        self.setItem(row, 1, dir_item)

        # PID
        pid_item = QTableWidgetItem(str(packet_info.get("pid", "-")))
        pid_item.setTextAlignment(Qt.AlignCenter)
        self.setItem(row, 2, pid_item)

        # RN
        rn_item = QTableWidgetItem(str(packet_info.get("rn", "-")))
        rn_item.setTextAlignment(Qt.AlignCenter)
        self.setItem(row, 3, rn_item)

        # Размер
        size_item = QTableWidgetItem(packet_info.get("size", ""))
        size_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.setItem(row, 4, size_item)

        # Service
        service_item = QTableWidgetItem(packet_info.get("service", ""))
        self.setItem(row, 5, service_item)

        # Подсветка строки (если есть статус)
        status = packet_info.get("status")
        if status:
            color = self._get_status_color(status)
            for col in range(6):
                self.item(row, col).setBackground(color)

        # Автопрокрутка
        self.scrollToBottom()

    def _get_status_color(self, status):
        """Цвет строки в зависимости от статуса."""
        if status == "PASS":
            return QColor(0, 170, 0, 50)  # Зелёный
        elif status in ("FAIL", "ERROR"):
            return QColor(255, 85, 85, 50)  # Красный
        elif status == "TIMEOUT":
            return QColor(255, 170, 0, 50)  # Жёлтый
        elif status == "PENDING":
            return QColor(150, 150, 150, 50)  # Серый
        return QColor(255, 255, 255, 0)

    def set_filter(self, direction: str = None, text: str = None):
        """Установка фильтров."""
        if direction is not None:
            self.filter_direction = direction
        if text is not None:
            self.filter_text = text
        # Перерисовка таблицы (упрощённо: скрытие неподходящих строк)
        for row in range(self.rowCount()):
            item = self.item(row, 1)  # Направление
            if item:
                show = True
                if self.filter_direction != "Все":
                    if self.filter_direction == "RX" and "RX" not in item.text():
                        show = False
                    elif self.filter_direction == "TX" and "TX" not in item.text():
                        show = False
                if self.filter_text:
                    # Поиск по всем колонкам
                    row_text = " ".join(self.item(row, col).text() for col in range(self.columnCount()) if self.item(row, col))
                    if self.filter_text.lower() not in row_text.lower():
                        show = False
                self.setRowHidden(row, not show)

    def _on_double_click(self, row, column):
        """Обработка двойного клика — открытие деталей пакета."""
        packet_data = {
            "time": self.item(row, 0).text() if self.item(row, 0) else "",
            "direction": self.item(row, 1).text() if self.item(row, 1) else "",
            "pid": self.item(row, 2).text() if self.item(row, 2) else "",
            "rn": self.item(row, 3).text() if self.item(row, 3) else "",
            "size": self.item(row, 4).text() if self.item(row, 4) else "",
            "service": self.item(row, 5).text() if self.item(row, 5) else "",
        }
        self.packet_selected.emit(packet_data)
