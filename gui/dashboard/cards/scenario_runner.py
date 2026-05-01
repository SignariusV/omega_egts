# OMEGA_EGTS GUI
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox,
    QPushButton, QTableView, QHeaderView, QLabel
)
from PySide6.QtCore import Signal, Slot, Qt, QAbstractTableModel, QModelIndex
from gui.dashboard.card_base import BaseCard, DisplayState
from gui.utils.scenario_scanner import scan_scenarios, get_default_scenarios_path, ScenarioInfo
from gui.widgets.progress_bar import ProgressBarWidget


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
            self.dataChanged.emit(self.index(index, 1), self.index(index, 2))

    def rowCount(self, parent=QModelIndex()):
        return len(self._steps)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        step = self._steps[index.row()]
        col = index.column()
        if col == 0:
            return step.get("name", "")
        elif col == 1:
            return step.get("status", "")
        elif col == 2:
            return step.get("duration", "")
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.COLUMNS[section]
        return None


class ScenarioRunnerCard(BaseCard):
    run_requested = Signal(str)
    stop_requested = Signal()

    def __init__(self, parent=None):
        super().__init__("Scenario Runner", parent)
        self._scenarios: list[ScenarioInfo] = []
        self._selected_path: str = ""
        self._running = False
        self._current_widget = None
        self._build_widgets()
        self._load_scenarios()
        self._show_expanded()

    def _build_widgets(self):
        self._compact_widget = self._create_compact_widget()
        self._expanded_widget = QWidget()
        self._build_expanded_ui()

    def _create_compact_widget(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        self._combo_compact = QComboBox()
        self._combo_compact.setMinimumWidth(150)
        self._run_btn_compact = QPushButton("Run")
        self._run_btn_compact.setFixedWidth(50)
        self._run_btn_compact.clicked.connect(self._on_run_clicked)
        layout.addWidget(self._combo_compact)
        layout.addWidget(self._run_btn_compact)
        layout.addStretch()
        return widget

    def _build_expanded_ui(self):
        layout = QVBoxLayout(self._expanded_widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        toolbar = QHBoxLayout()
        self._combo_expanded = QComboBox()
        self._combo_expanded.setMinimumWidth(200)
        toolbar.addWidget(QLabel("Scenario:"))
        toolbar.addWidget(self._combo_expanded)
        toolbar.addStretch()
        self._run_btn = QPushButton("Run")
        self._run_btn.clicked.connect(self._on_run_clicked)
        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self.stop_requested.emit)
        toolbar.addWidget(self._run_btn)
        toolbar.addWidget(self._stop_btn)
        layout.addLayout(toolbar)

        self._progress_bar = ProgressBarWidget()
        layout.addWidget(self._progress_bar)

        self._step_model = StepTableModel()
        self._step_table = QTableView()
        self._step_table.setModel(self._step_model)
        header = self._step_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._step_table.setMinimumHeight(150)
        layout.addWidget(self._step_table)

    def _load_scenarios(self):
        scenarios_path = get_default_scenarios_path()
        if scenarios_path:
            self._scenarios = scan_scenarios(scenarios_path)
        self._update_combos()

    def _update_combos(self):
        self._combo_compact.clear()
        self._combo_expanded.clear()
        for s in self._scenarios:
            self._combo_compact.addItem(s.name, s.json_file)
            self._combo_expanded.addItem(s.name, s.json_file)

    def _on_run_clicked(self):
        combo = self._combo_expanded if self._display_state == DisplayState.EXPANDED else self._combo_compact
        idx = combo.currentIndex()
        if idx >= 0:
            path = combo.itemData(idx)
            if path:
                self._selected_path = str(path)
                self._running = True
                self._run_btn.setEnabled(False)
                self._run_btn_compact.setEnabled(False)
                self._stop_btn.setEnabled(True)
                self.run_requested.emit(self._selected_path)

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

    @Slot()
    def on_scenario_step(self, data: dict):
        step_name = data.get("step", "")
        status = data.get("status", "")
        duration = data.get("duration", "")
        steps = data.get("steps", [])
        if steps and not self._step_model._steps:
            self._step_model.set_steps(steps)
        for i, step in enumerate(self._step_model._steps):
            if step.get("name") == step_name:
                self._step_model.update_step(i, status, duration)
                break
        progress = data.get("progress", 0)
        if progress:
            self._progress_bar.set_value(progress)
        if status in ("PASS", "FAIL"):
            self._running = False
            self._run_btn.setEnabled(True)
            self._run_btn_compact.setEnabled(True)
            self._stop_btn.setEnabled(False)

    @Slot()
    def on_command_error(self, data: dict):
        self._running = False
        self._run_btn.setEnabled(True)
        self._run_btn_compact.setEnabled(True)
        self._stop_btn.setEnabled(False)

    def get_state(self) -> dict:
        return {
            "selected_index": self._combo_expanded.currentIndex(),
        }

    def set_state(self, state: dict):
        idx = state.get("selected_index", 0)
        if 0 <= idx < self._combo_expanded.count():
            self._combo_expanded.setCurrentIndex(idx)
            self._combo_compact.setCurrentIndex(idx)