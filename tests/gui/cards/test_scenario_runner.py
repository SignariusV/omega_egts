# OMEGA_EGTS GUI
import pytest
import json
import tempfile
from pathlib import Path
from PySide6.QtWidgets import QApplication
from gui.dashboard.cards.scenario_runner import ScenarioRunnerCard, StepTableModel
from gui.dashboard.card_base import DisplayState
from gui.utils.scenario_scanner import scan_scenarios, ScenarioInfo


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


class TestStepTableModel:
    def test_initial_row_count(self):
        model = StepTableModel()
        assert model.rowCount() == 0

    def test_set_steps(self):
        model = StepTableModel()
        steps = [{"name": "Step1", "status": "pending", "duration": ""}]
        model.set_steps(steps)
        assert model.rowCount() == 1

    def test_data(self):
        model = StepTableModel()
        steps = [{"name": "Auth", "status": "PASS", "duration": "1.2s"}]
        model.set_steps(steps)
        idx = model.index(0, 0)
        assert model.data(idx) == "Auth"
        idx = model.index(0, 1)
        assert model.data(idx) == "PASS"

    def test_update_step(self):
        model = StepTableModel()
        steps = [{"name": "Step1", "status": "pending", "duration": ""}]
        model.set_steps(steps)
        model.update_step(0, "PASS", "0.5s")
        idx = model.index(0, 1)
        assert model.data(idx) == "PASS"


class TestScenarioScanner:
    def test_scanner_returns_scenarios(self, tmp_path):
        scenario_dir = tmp_path / "test_scenario"
        scenario_dir.mkdir()
        scenario_json = scenario_dir / "scenario.json"
        scenario_json.write_text(json.dumps({"name": "Test Scenario", "version": "1"}))
        result = scan_scenarios(tmp_path)
        assert len(result) == 1
        assert result[0].name == "Test Scenario"

    def test_scanner_empty_dir(self, tmp_path):
        result = scan_scenarios(tmp_path)
        assert result == []

    def test_scanner_missing_json(self, tmp_path):
        scenario_dir = tmp_path / "test_scenario"
        scenario_dir.mkdir()
        result = scan_scenarios(tmp_path)
        assert result == []


class TestScenarioRunnerCard:
    def test_initial_state(self, qtbot):
        card = ScenarioRunnerCard()
        qtbot.addWidget(card)
        assert card.title == "Scenario Runner"
        assert card._running is False

    def test_compact_mode_shows_combo_and_button(self, qtbot):
        card = ScenarioRunnerCard()
        qtbot.addWidget(card)
        card.set_display_state(DisplayState.COMPACT)
        assert card._stack.currentIndex() == 0
        assert card._combo_compact is not None
        assert card._run_btn_compact is not None

    def test_expanded_mode_shows_table(self, qtbot):
        card = ScenarioRunnerCard()
        qtbot.addWidget(card)
        card.set_display_state(DisplayState.EXPANDED)
        assert card._stack.currentIndex() == 1
        assert card._step_table is not None
        assert card._progress_bar is not None

    def test_run_button_emits_signal(self, qtbot):
        card = ScenarioRunnerCard()
        qtbot.addWidget(card)
        emitted = []
        card.run_requested.connect(lambda p: emitted.append(p))
        card._run_btn.click()
        assert len(emitted) == 1

    def test_scenario_started_initializes_table(self, qtbot):
        card = ScenarioRunnerCard()
        qtbot.addWidget(card)
        card.set_display_state(DisplayState.EXPANDED)
        data = {
            "scenario_name": "Test",
            "steps_total": 3,
            "steps": [
                {"name": "Auth", "status": "PENDING", "duration": ""},
                {"name": "Send", "status": "PENDING", "duration": ""},
                {"name": "Verify", "status": "PENDING", "duration": ""},
            ]
        }
        card.on_scenario_started(data)
        assert card._step_model.rowCount() == 3
        assert card._running is True
        assert card._progress_bar.get_value() == 0

    def test_scenario_step_updates_by_index(self, qtbot):
        card = ScenarioRunnerCard()
        qtbot.addWidget(card)
        card.set_display_state(DisplayState.EXPANDED)
        # Сначала инициализируем
        card.on_scenario_started({
            "scenario_name": "Test",
            "steps_total": 2,
            "steps": [
                {"name": "Auth", "status": "PENDING", "duration": ""},
                {"name": "Send", "status": "PENDING", "duration": ""},
            ]
        })
        # Обновляем первый шаг
        card.on_scenario_step({
            "step_index": 0,
            "result": "PASS",
            "duration": 1.2,
            "progress": 50,
        })
        assert card._step_model.rowCount() == 2
        idx = card._step_model.index(0, 1)
        assert card._step_model.data(idx) == "PASS"
        assert card._progress_bar.get_value() == 50

    def test_scenario_stopped_resets_table(self, qtbot):
        card = ScenarioRunnerCard()
        qtbot.addWidget(card)
        card.set_display_state(DisplayState.EXPANDED)
        card.on_scenario_started({
            "scenario_name": "Test",
            "steps_total": 2,
            "steps": [
                {"name": "Auth", "status": "PENDING", "duration": ""},
                {"name": "Send", "status": "PENDING", "duration": ""},
            ]
        })
        card.on_scenario_step({
            "step_index": 0,
            "result": "PASS",
            "duration": 1.0,
            "progress": 50,
        })
        # Останавливаем
        card.on_scenario_stopped()
        assert card._running is False
        assert card._step_model.rowCount() == 2
        # Все шаги снова PENDING
        assert card._step_model.data(card._step_model.index(0, 1)) == "PENDING"
        assert card._step_model.data(card._step_model.index(1, 1)) == "PENDING"

    def test_get_set_state(self, qtbot):
        card = ScenarioRunnerCard()
        qtbot.addWidget(card)
        state = card.get_state()
        assert "selected_index" in state
        card.set_state({"selected_index": 0})