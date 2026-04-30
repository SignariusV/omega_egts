from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor


class StepList(QTableWidget):
    """Таблица шагов сценария с отображением статуса."""

    def __init__(self):
        super().__init__()
        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(["№", "Название", "Тип", "Статус"])
        self.setAlternatingRowColors(True)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)  # №
        self.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Статус

    def set_steps(self, steps: list[dict]):
        """Загрузка шагов сценария."""
        self.setRowCount(0)
        for i, step in enumerate(steps, start=1):
            row = self.rowCount()
            self.insertRow(row)

            # №
            num_item = QTableWidgetItem(str(i))
            num_item.setTextAlignment(Qt.AlignCenter)
            self.setItem(row, 0, num_item)

            # Название
            name_item = QTableWidgetItem(step.get("name", f"Step {i}"))
            self.setItem(row, 1, name_item)

            # Тип
            type_item = QTableWidgetItem(step.get("type", ""))
            type_item.setTextAlignment(Qt.AlignCenter)
            self.setItem(row, 2, type_item)

            # Статус (пока PENDING)
            status_item = QTableWidgetItem("⏹ PEND")
            status_item.setTextAlignment(Qt.AlignCenter)
            self.setItem(row, 3, status_item)

    def update_step_status(self, step_name: str, status: str):
        """Обновление статуса конкретного шага."""
        status_icons = {
            "PASS": "✅ PASS",
            "FAIL": "❌ FAIL",
            "WAIT": "⏳ WAIT",
            "PEND": "⏹ PEND",
            "TIMEOUT": "⏱ TIMEOUT"
        }
        status_text = status_icons.get(status, status)
        status_color = self._get_status_color(status)

        for row in range(self.rowCount()):
            name_item = self.item(row, 1)
            if name_item and name_item.text() == step_name:
                status_item = self.item(row, 3)
                if status_item:
                    status_item.setText(status_text)
                    for col in range(4):
                        item = self.item(row, col)
                        if item:
                            item.setBackground(status_color)
                break

    def _get_status_color(self, status):
        """Цвет фона строки в зависимости от статуса."""
        if status == "PASS":
            return QColor(0, 170, 0, 50)  # Зелёный
        elif status in ("FAIL", "ERROR"):
            return QColor(255, 85, 85, 50)  # Красный
        elif status == "TIMEOUT":
            return QColor(255, 170, 0, 50)  # Жёлтый
        elif status in ("PEND", "WAIT"):
            return QColor(150, 150, 150, 50)  # Серый
        return QColor(255, 255, 255, 0)
