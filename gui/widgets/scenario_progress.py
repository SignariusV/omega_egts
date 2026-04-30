from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar
from PySide6.QtCore import Qt, QTimer, QTime, Signal
from PySide6.QtGui import QFont, QColor


class ScenarioProgress(QWidget):
    """Виджет прогресса выполнения сценария."""

    def __init__(self):
        super().__init__()
        self.start_time = None
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_time)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Название сценария
        self.name_label = QLabel("Сценарий: Не выбран")
        self.name_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.name_label.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(self.name_label)

        # Статус
        self.status_label = QLabel("⏹ ОСТАНОВЛЕН")
        self.status_label.setStyleSheet("color: #FF5555; font-weight: bold;")
        layout.addWidget(self.status_label)

        # Прогресс-бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #3C3C3C;
                border: 1px solid #555555;
                border-radius: 3px;
                text-align: center;
                color: #FFFFFF;
            }
            QProgressBar::chunk {
                background-color: #0078D7;
                border-radius: 2px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # Счётчик и врем
        counter_layout = QHBoxLayout()
        self.counter_label = QLabel("Прогресс: 0% (0/0 шагов)")
        self.counter_label.setStyleSheet("color: #CCCCCC;")
        counter_layout.addWidget(self.counter_label)

        self.time_label = QLabel("Время: 00:00:00")
        self.time_label.setStyleSheet("color: #CCCCCC;")
        self.time_label.setAlignment(Qt.AlignRight)
        counter_layout.addWidget(self.time_label)

        layout.addLayout(counter_layout)

        # Ошибки
        self.errors_label = QLabel("Ошибок: 0")
        self.errors_label.setStyleSheet("color: #FF5555;")
        layout.addWidget(self.errors_label)

    def set_scenario(self, name: str, total_steps: int):
        """Установка нового сценария."""
        self.name_label.setText(f"Сценарий: {name}")
        self.status_label.setText("🟢 ВЫПОЛНЯЕТСЯ")
        self.status_label.setStyleSheet("color: #00AA00; font-weight: bold;")
        self.progress_bar.setValue(0)
        self.counter_label.setText(f"Прогресс: 0% (0/{total_steps} шагов)")
        self.errors_label.setText("Ошибок: 0")
        self.total_steps = total_steps
        self.completed_steps = 0
        self.error_count = 0
        self.start_time = QTime.currentTime()
        self.timer.start(1000)

    def update_progress(self, completed: int, errors: int = 0):
        """Обновление прогресса."""
        self.completed_steps = completed
        self.error_count = errors
        percentage = int((completed / self.total_steps) * 100) if self.total_steps > 0 else 0
        self.progress_bar.setValue(percentage)
        self.counter_label.setText(f"Прогресс: {percentage}% ({completed}/{self.total_steps} шагов)")
        self.errors_label.setText(f"Ошибок: {errors}")

    def set_status(self, status: str):
        """Установка статуса (PASS, FAIL, TIMEOUT, PENDING)."""
        status_map = {
            "PASS": ("✅ ЗАВЕРШЁН", "#00AA00"),
            "FAIL": ("❌ ОШИБКА", "#FF5555"),
            "TIMEOUT": ("⏱ ПРЕВЫШЕНО ВРЕМЯ", "#FFAA00"),
            "PENDING": ("⏹ ОСТАНОВЛЕН", "#FF5555"),
            "RUNNING": ("🟢 ВЫПОЛНЯЕТСЯ", "#00AA00")
        }
        text, color = status_map.get(status, (status, "#CCCCCC"))
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color}; font-weight: bold;")

    def _update_time(self):
        """Обновление времени выполнения."""
        if self.start_time:
            elapsed = self.start_time.secsTo(QTime.currentTime())
            hours = elapsed // 3600
            minutes = (elapsed % 3600) // 60
            seconds = elapsed % 60
            time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            self.time_label.setText(f"Время: {time_str}")

    def reset(self):
        """Сброс виджета."""
        self.timer.stop()
        self.name_label.setText("Сценарий: Не выбран")
        self.status_label.setText("⏹ ОСТАНОВЛЕН")
        self.status_label.setStyleSheet("color: #FF5555; font-weight: bold;")
        self.progress_bar.setValue(0)
        self.counter_label.setText("Прогресс: 0% (0/0 шагов)")
        self.time_label.setText("Время: 00:00:00")
        self.errors_label.setText("Ошибок: 0")
