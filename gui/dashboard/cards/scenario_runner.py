# OMEGA_EGTS GUI
import logging
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox,
    QPushButton, QTableView, QHeaderView, QLabel
)
from PySide6.QtCore import Signal, Slot, Qt, QAbstractTableModel, QModelIndex, QTimer
from PySide6.QtGui import QColor
from gui.dashboard.card_base import BaseCard, DisplayState
from gui.utils.scenario_scanner import scan_scenarios, get_default_scenarios_path, ScenarioInfo
from gui.widgets.progress_bar import ProgressBarWidget

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

logger = logging.getLogger(__name__)


STEP_TEXT_COLORS = {
    "PASS": QColor("#4EC9B0"),
    "FAIL": QColor("#F44747"),
    "TIMEOUT": QColor("#DCDCAA"),
    "ERROR": QColor("#F44747"),
    "RUNNING": QColor("#569CD6"),
    "PENDING": QColor("#808080"),
    "CANCELLED": QColor("#808080"),
}

STEP_BG_COLORS = {
    "PASS": QColor(78, 201, 176, 25),
    "FAIL": QColor(244, 71, 71, 25),
    "TIMEOUT": QColor(220, 220, 170, 25),
    "ERROR": QColor(244, 71, 71, 25),
    "RUNNING": QColor(86, 156, 214, 25),
    "PENDING": QColor(128, 128, 128, 10),
    "CANCELLED": QColor(128, 128, 128, 15),
}


class StepTableModel(QAbstractTableModel):
    COLUMNS = ["Step Name", "Status", "Duration"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._steps = []

    def set_steps(self, steps: list[dict]):
        self.beginResetModel()
        self._steps = steps.copy()
        self.endResetModel()

    def update_step(self, index: int, status: str, duration: str = ""):
        if 0 <= index < len(self._steps):
            self._steps[index]["status"] = status
            self._steps[index]["duration"] = duration
            self.dataChanged.emit(self.index(index, 0), self.index(index, 2))

    def rowCount(self, parent=QModelIndex()):
        return len(self._steps)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        step = self._steps[index.row()]
        col = index.column()
        status = step.get("status", "")
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return step.get("name", "")
            elif col == 1:
                return status
            elif col == 2:
                return step.get("duration", "")
        elif role == Qt.ItemDataRole.ForegroundRole:
            if col == 1:
                color = STEP_TEXT_COLORS.get(status)
                if color:
                    return color
        elif role == Qt.ItemDataRole.BackgroundRole:
            color = STEP_BG_COLORS.get(status)
            if color:
                return color
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.COLUMNS[section]
        return None


class ScenarioRunnerCard(BaseCard):
    run_requested = Signal(str)
    stop_requested = Signal()

    def __init__(self, card_id: str = "scenario_runner", parent=None):
        super().__init__("Scenario Runner", card_id=card_id, parent=parent)
        self.icon_path = str(PROJECT_ROOT / "gui" / "resources" / "icons" / "scenario.svg")
        self._scenarios: list[ScenarioInfo] = []
        self._selected_path: str = ""
        self._running = False
        self._steps_total = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timer_tick)
        self._elapsed_seconds = 0
        self._build_widgets()
        self._load_scenarios()
        self.finish_init()

    def _build_widgets(self):
        self._build_compact_ui()
        self._build_expanded_ui()
        self.set_views(self._compact_widget, self._expanded_widget)

    def _build_compact_ui(self):
        self._compact_widget = QWidget()
        layout = QHBoxLayout(self._compact_widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        self._combo_compact = QComboBox()
        self._combo_compact.setMinimumWidth(150)
        self._combo_compact.setToolTip("Select scenario to run")
        layout.addWidget(self._combo_compact)
        self._run_btn_compact = QPushButton("Run")
        self._run_btn_compact.setObjectName("scenarioToggleButton")
        self._run_btn_compact.setProperty("scenarioState", "stopped")
        self._run_btn_compact.setFixedWidth(50)
        self._run_btn_compact.setToolTip("Run selected scenario (F5)")
        self._run_btn_compact.clicked.connect(self._on_toggle_clicked)
        layout.addWidget(self._run_btn_compact)
        layout.addStretch()

    def _build_expanded_ui(self):
        self._expanded_widget = QWidget()
        layout = QVBoxLayout(self._expanded_widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        toolbar = QHBoxLayout()
        self._combo_expanded = QComboBox()
        self._combo_expanded.setMinimumWidth(200)
        self._combo_expanded.setToolTip("Select scenario to execute")
        toolbar.addWidget(QLabel("Scenario:"))
        toolbar.addWidget(self._combo_expanded)
        toolbar.addStretch()
        self._run_btn = QPushButton("Run")
        self._run_btn.setObjectName("scenarioToggleButton")
        self._run_btn.setProperty("scenarioState", "stopped")
        self._run_btn.setToolTip("Run selected scenario (F5)")
        self._run_btn.clicked.connect(self._on_toggle_clicked)
        toolbar.addWidget(self._run_btn)
        layout.addLayout(toolbar)

        self._progress_bar = ProgressBarWidget()
        self._progress_bar.setToolTip("Scenario execution progress")
        layout.addWidget(self._progress_bar)

        self._step_model = StepTableModel()
        self._step_table = QTableView()
        self._step_table.setModel(self._step_model)
        self._step_table.setToolTip("Scenario steps execution status")
        header = self._step_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._step_table.setMinimumHeight(150)
        layout.addWidget(self._step_table)

    def _load_scenarios(self):
        scenarios_path = get_default_scenarios_path()
        if scenarios_path:
            self._scenarios = scan_scenarios(scenarios_path)
        self._combo_compact.clear()
        self._combo_expanded.clear()
        for s in self._scenarios:
            self._combo_compact.addItem(s.name, s.json_file)
            self._combo_expanded.addItem(s.name, s.json_file)
        self._combo_compact.currentIndexChanged.connect(self._combo_expanded.setCurrentIndex)
        self._combo_expanded.currentIndexChanged.connect(self._combo_compact.setCurrentIndex)

    def _on_toggle_clicked(self):
        if self._running:
            self.stop_requested.emit()
        else:
            combo = self._combo_expanded if self._display_state == DisplayState.EXPANDED else self._combo_compact
            idx = combo.currentIndex()
            if idx >= 0:
                path = combo.itemData(idx)
                if path:
                    self._selected_path = str(path)
                    self.run_requested.emit(self._selected_path)

    def _update_button_state(self, running: bool):
        state = "running" if running else "stopped"
        text = "Stop" if running else "Run"
        tooltip = "Stop running scenario" if running else "Run selected scenario (F5)"

        self._run_btn.setText(text)
        self._run_btn.setProperty("scenarioState", state)
        self._run_btn.setToolTip(tooltip)
        self._run_btn.setEnabled(True)
        self._run_btn.style().unpolish(self._run_btn)
        self._run_btn.style().polish(self._run_btn)

        self._run_btn_compact.setText(text)
        self._run_btn_compact.setProperty("scenarioState", state)
        self._run_btn_compact.setToolTip(tooltip)
        self._run_btn_compact.setEnabled(True)
        self._run_btn_compact.style().unpolish(self._run_btn_compact)
        self._run_btn_compact.style().polish(self._run_btn_compact)

    def update_content_visibility(self, state: DisplayState):
        super().update_content_visibility(state)

    @Slot(dict)
    def on_scenario_started(self, data: dict):
        """Инициализировать таблицу и прогресс при старте сценария."""
        self._running = True
        self._steps_total = data.get("steps_total", 0)
        steps = data.get("steps", [])
        self._step_model.set_steps(steps)
        self._progress_bar.set_segments(self._steps_total)
        self._progress_bar.set_value(0)
        self._update_button_state(True)
        # Запуск таймера
        self._elapsed_seconds = 0
        self._timer.start(1000)

    @Slot(dict)
    def on_scenario_step(self, data: dict):
        """Обновить шаг и прогресс."""
        step_index = data.get("step_index", 0)
        status = data.get("result", "")
        duration = data.get("duration", 0.0)
        steps = data.get("steps", [])

        if steps:
            self._step_model.set_steps(steps)
        else:
            self._step_model.update_step(step_index, status, f"{duration:.2f}s")

        # Подсветка сегмента прогресса
        self._progress_bar.set_step_status(step_index, status)

        # Обновление прогресса
        progress = data.get("progress", 0)
        self._progress_bar.set_value(progress)

        # Если сценарий завершился
        if status in ("PASS", "FAIL", "ERROR", "TIMEOUT", "CANCELLED"):
            self._running = False
            self._update_button_state(False)
            self._timer.stop()

    @Slot(dict)
    def on_scenario_finished(self, data: dict):
        """Финальное состояние сценария."""
        self._running = False
        self._update_button_state(False)
        self._timer.stop()

    @Slot()
    def on_command_error(self, data: dict):
        self._running = False
        self._update_button_state(False)
        self._timer.stop()

    def on_scenario_stopped(self):
        """Call when scenario execution is stopped."""
        self._running = False
        self._update_button_state(False)
        self._progress_bar.reset()
        self._timer.stop()

    def _on_timer_tick(self):
        """Обновить duration текущего RUNNING шага каждую секунду."""
        self._elapsed_seconds += 1
        for i, step in enumerate(self._step_model._steps):
            if step.get("status") == "PENDING":
                # Обновляем первый PENDING шаг как RUNNING
                self._step_model.update_step(i, "RUNNING", f"{self._elapsed_seconds}s")
                self._progress_bar.set_step_status(i, "RUNNING")
                break
            elif step.get("status") == "RUNNING":
                # Обновляем duration текущего RUNNING
                self._step_model.update_step(i, "RUNNING", f"{self._elapsed_seconds}s")
                break

    def get_state(self) -> dict:
        return {
            "selected_index": self._combo_expanded.currentIndex(),
        }

    def set_state(self, state: dict):
        idx = state.get("selected_index", 0)
        if 0 <= idx < self._combo_expanded.count():
            self._combo_expanded.setCurrentIndex(idx)
            self._combo_compact.setCurrentIndex(idx)
