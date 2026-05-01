# OMEGA_EGTS GUI
import pytest
import json
import tempfile
from pathlib import Path
from PySide6.QtWidgets import QApplication
from gui.overlays.scenario_editor import ScenarioEditorOverlay, JsonSyntaxHighlighter


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


class TestJsonSyntaxHighlighter:
    def test_initializes(self):
        highlighter = JsonSyntaxHighlighter()
        assert highlighter is not None


class TestScenarioEditorOverlay:
    def test_initial_state(self, qtbot):
        dialog = ScenarioEditorOverlay()
        qtbot.addWidget(dialog)
        assert dialog.windowTitle() == "Scenario Editor"

    def test_validate_valid_json(self, qtbot):
        dialog = ScenarioEditorOverlay()
        qtbot.addWidget(dialog)
        dialog._text_edit.setPlainText('{"name": "Test", "version": "1", "steps": []}')
        dialog._on_validate()
        assert "Valid" in dialog._status_label.text()

    def test_validate_invalid_json(self, qtbot):
        dialog = ScenarioEditorOverlay()
        qtbot.addWidget(dialog)
        dialog._text_edit.setPlainText('{invalid}')
        dialog._on_validate()
        assert "JSON Error" in dialog._status_label.text()

    def test_validate_missing_name(self, qtbot):
        dialog = ScenarioEditorOverlay()
        qtbot.addWidget(dialog)
        dialog._text_edit.setPlainText('{"version": "1", "steps": []}')
        dialog._on_validate()
        assert "name" in dialog._status_label.text().lower()

    def test_validate_missing_steps_type(self, qtbot):
        dialog = ScenarioEditorOverlay()
        qtbot.addWidget(dialog)
        dialog._text_edit.setPlainText('{"name": "Test", "steps": [{"unknown": "field"}]}')
        dialog._on_validate()
        assert "type" in dialog._status_label.text().lower()

    def test_save_without_path_opens_dialog(self, qtbot, monkeypatch):
        calls = []
        def fake_get_save(parent, title, dir, filter):
            calls.append((parent, title))
            return ("", "")
        monkeypatch.setattr("PySide6.QtWidgets.QFileDialog.getSaveFileName", fake_get_save)
        dialog = ScenarioEditorOverlay()
        qtbot.addWidget(dialog)
        dialog._text_edit.setPlainText('{"name": "Test"}')
        dialog._save_btn.click()
        assert len(calls) == 1